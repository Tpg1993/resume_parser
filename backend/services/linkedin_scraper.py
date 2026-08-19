import re
import httpx
from bs4 import BeautifulSoup
from services.langgraph_agent import call_sarvam_ai

def extract_linkedin_job_id(url: str) -> str:
    """
    Helper to extract the numeric job ID from a LinkedIn URL.
    """
    job_id = None
    # 1. Match currentJobId parameter
    m = re.search(r'currentJobId=(\d+)', url)
    if m:
        job_id = m.group(1)
    else:
        # 2. Match standard job view paths: /jobs/view/123456789/
        # or /jobs/view/title-slug-123456789/
        m = re.search(r'/jobs/view/(?:[^/]+/)?(\d+)', url)
        if m:
            job_id = m.group(1)
        else:
            # 3. Match any sequence of 9 to 11 digits in the URL
            m = re.search(r'\b(\d{9,11})\b', url)
            if m:
                job_id = m.group(1)
    return job_id

def scrape_linkedin_guest_api(job_id: str) -> dict:
    """
    Queries LinkedIn's public SEO guest API endpoint for job post details.
    """
    api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPost/{job_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    with httpx.Client(follow_redirects=True, headers=headers, timeout=15.0) as client:
        response = client.get(api_url)
        if response.status_code != 200:
            raise Exception(f"LinkedIn Guest API returned HTTP {response.status_code}")
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Title
        title_tag = soup.find("h2", class_=re.compile("top-card-layout__title|topcard__title"))
        title = title_tag.get_text(strip=True) if title_tag else "LinkedIn Job"
        
        # Company
        company_tag = soup.find("a", class_=re.compile("topcard__org-name-link|top-card-layout__company-name"))
        if not company_tag:
            company_tag = soup.find("span", class_="topcard__flavor")
        company = company_tag.get_text(strip=True) if company_tag else ""
        
        # Job Description HTML
        desc_tag = soup.find("div", class_=re.compile("description__text|show-more-less-html__markup"))
        if desc_tag:
            for tag in desc_tag.find_all(["button", "script", "style"]):
                tag.decompose()
            description = desc_tag.get_text("\n", strip=True)
        else:
            description = soup.get_text("\n", strip=True)
            
        return {
            "title": title,
            "company": company,
            "description": description,
            "source": "linkedin_guest_api"
        }

def scrape_general_url(url: str) -> dict:
    """
    Fallback BeautifulSoup-based scraper for any general URL or blocked LinkedIn guest requests.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    with httpx.Client(follow_redirects=True, headers=headers, timeout=15.0) as client:
        response = client.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch job page URL: HTTP {response.status_code}")
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Clean page elements
        for tag in soup(["script", "style", "nav", "header", "footer", "form", "button"]):
            tag.decompose()
            
        title = soup.title.string.strip() if soup.title else "Job Posting"
        
        body = soup.body if soup.body else soup
        description = body.get_text("\n", strip=True)
        
        company = ""
        # Simple heuristics for company name
        title_clean = title.split("|")[0].split("-")[0].strip()
        if " at " in title_clean:
            parts = title_clean.split(" at ")
            if len(parts) > 1:
                company = parts[-1].strip()
                title_clean = parts[0].strip()
                
        return {
            "title": title_clean,
            "company": company,
            "description": description,
            "source": "general_web_scrape"
        }

async def fetch_and_condense_job(url: str) -> dict:
    """
    Scrapes a job posting from the given URL and condenses its contents using the LLM to save tokens.
    """
    # 1. Scrape raw details
    job_id = extract_linkedin_job_id(url) if "linkedin.com" in url else None
    
    raw_data = None
    error_msg = None
    
    if job_id:
        try:
            raw_data = scrape_linkedin_guest_api(job_id)
        except Exception as e:
            error_msg = f"LinkedIn guest API failed: {str(e)}. Attempting general scrape fallback."
            print(error_msg)
            
    if not raw_data:
        try:
            raw_data = scrape_general_url(url)
        except Exception as e:
            raise Exception(f"Failed to scrape URL: {str(e)}")
            
    # 2. Condense the description using LLM
    raw_desc = raw_data.get("description", "")
    
    # Pre-clean text to avoid wasting context space
    # Remove consecutive spaces and newlines
    raw_desc = re.sub(r'\n+', '\n', raw_desc)
    raw_desc = re.sub(r' +', ' ', raw_desc)
    # Truncate to reasonable limits
    raw_desc = raw_desc[:12000]
    
    prompt = f"""
    You are an expert Job Description Condenser.
    Your task is to take the raw text of a job posting and extract ONLY the essential details and requirements, keeping it as short as possible to save tokens for subsequent analysis.

    TARGETS:
    - Target Company Name (from headers/context if available)
    - Target Job Title
    - Core Requirements: Critical skills, experience level, tools, technologies, and certifications.
    - Principal Responsibilities.

    EXCLUDE:
    - Company history, mission statements, benefits, perks.
    - DEI statements, employment disclaimers, or general application instructions.

    RAW JOB DESCRIPTION:
    {raw_desc}

    OUTPUT FORMAT:
    Respond STRICTLY with a JSON object. Do not include markdown formatting like ```json or any other text.
    {{
        "title": "Clean Job Title",
        "company": "Clean Company Name (or empty string if not found)",
        "essential_requirements": [
            "Bullet list of essential requirements..."
        ],
        "core_responsibilities": [
            "Bullet list of key responsibilities..."
        ]
    }}
    """
    
    condensed_text = await call_sarvam_ai(prompt, temperature=0.1)
    
    # Parse JSON output robustly
    clean_text = str(condensed_text)
    if "```json" in clean_text:
        clean_text = clean_text.split("```json")[1].split("```")[0].strip()
    elif "```" in clean_text:
        clean_text = clean_text.split("```")[1].strip()
        
    start = clean_text.find('{')
    end = clean_text.rfind('}')
    if start != -1 and end != -1 and end >= start:
        clean_text = clean_text[start:end+1]
        
    try:
        import json
        structured_data = json.loads(clean_text, strict=False)
    except Exception as e:
        # Fallback parsing
        structured_data = {
            "title": raw_data.get("title", "Job Posting"),
            "company": raw_data.get("company", ""),
            "essential_requirements": [clean_text[:500]],
            "core_responsibilities": []
        }
        
    # Combine title/company fallback
    final_title = structured_data.get("title") or raw_data.get("title") or "Job Posting"
    final_company = structured_data.get("company") or raw_data.get("company") or ""
    
    # Build text representation of requirements
    reqs_str = "\n".join(f"- {r}" for r in structured_data.get("essential_requirements", []))
    resp_str = "\n".join(f"- {r}" for r in structured_data.get("core_responsibilities", []))
    
    condensed_jd_text = f"Job Title: {final_title}\nCompany: {final_company}\n\nEssential Requirements:\n{reqs_str}\n\nCore Responsibilities:\n{resp_str}"
    
    return {
        "title": final_title,
        "company": final_company,
        "condensed_jd": condensed_jd_text,
        "original_length": len(raw_data.get("description", "")),
        "condensed_length": len(condensed_jd_text),
        "source": raw_data.get("source")
    }
