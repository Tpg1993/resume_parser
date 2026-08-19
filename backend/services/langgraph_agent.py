import os
import json
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv

load_dotenv()

class AgentState(TypedDict):
    parsed_markdown: str
    job_description: str
    company_name: str
    hiring_manager: str
    
    # New Fields
    extracted_profile: dict
    ats_score: int
    missing_keywords: List[str]
    match_tier: str
    projected_score: int
    
    cover_letter: str
    cover_letter_data: dict
    suggestions: List[Dict[str, Any]]
    status: str
    error: str

async def call_sarvam_ai(prompt: str, temperature: float = 0.2, retries: int = 3) -> str:
    """
    Helper function to interface with Sarvam AI's LLM endpoints with exponential backoff.
    """
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key or api_key == "your_sarvam_api_key_here":
        raise ValueError("SARVAM_API_KEY is missing or invalid in .env")

    # Sarvam AI uses an OpenAI-compatible /chat/completions endpoint
    url = "https://api.sarvam.ai/v1/chat/completions" 
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}" 
    }
    
    model_name = os.getenv("SARVAM_MODEL", "sarvam-30b")
    
    payload = {
        "model": model_name, 
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 4000
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        last_exception = None
        for attempt in range(retries):
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                # Robustly extract the generated text based on common LLM API schemas
                extracted_text = None
                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    if isinstance(choice, dict) and "message" in choice:
                        msg = choice["message"]
                        extracted_text = msg.get("content") or msg.get("text")
                        if not extracted_text:
                            # Fallback: grab any long string inside message
                            for k, v in msg.items():
                                if isinstance(v, str) and len(v) > 5 and k not in ["role"]:
                                    extracted_text = v
                                    break
                    elif isinstance(choice, dict) and "text" in choice:
                        extracted_text = choice["text"]
                    elif isinstance(choice, str):
                        extracted_text = choice
                        
                if not extracted_text:
                    if "output" in data:
                        extracted_text = data["output"]
                    elif "text" in data:
                        extracted_text = data["text"]
                    elif "results" in data and len(data["results"]) > 0:
                        val = data["results"][0]
                        extracted_text = val.get("text") if isinstance(val, dict) else str(val)
                
                if not extracted_text:
                    pass  # LLM returned empty — handled by caller fallback logic
                    
                return extracted_text
                
            except httpx.HTTPStatusError as e:
                last_exception = e
                # Retry on 429 Too Many Requests or 5xx Server Errors
                if e.response.status_code in [429, 500, 502, 503, 504]:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise Exception(f"HTTP Error {e.response.status_code} communicating with Sarvam AI: {e.response.text}")
            except Exception as e:
                last_exception = e
                await asyncio.sleep(2 ** attempt)
                continue
                
        raise Exception(f"Failed to communicate with Sarvam AI after {retries} attempts. Last error: {str(last_exception)}")

def truncate_markdown(markdown: str, max_chars: int = 24000) -> str:
    """Helper to ensure we don't blow the context window"""
    if len(markdown) <= max_chars:
        return markdown
    # Brutal but effective truncation if it's too long, prioritizing the top
    return markdown[:max_chars] + "\n\n... [TRUNCATED DUE TO LENGTH]"

import re

def is_placeholder(val: Any, field_type: str = "name") -> bool:
    if not val or not isinstance(val, str):
        return True
    val_clean = val.strip().lower()
    if not val_clean or val_clean in {"none", "null", "n/a", "unknown", "candidate", "name"}:
        return True
    if field_type == "name":
        placeholders = {
            "full name", "candidate name", "candidate's name", "your name", "candidate", 
            "john doe", "jane doe", "[candidate name]", "[full name]", "[name]", "<name>"
        }
        if val_clean in placeholders or "candidate name" in val_clean or "full name" in val_clean:
            return True
    elif field_type == "contact":
        placeholders = {
            "email | phone", "contact info", "contact details", "[contact info]",
            "email | phone | location", "email | phone | location | linkedin",
            "your contact", "<contact info>", "[email | phone]"
        }
        if val_clean in placeholders or "email | phone" in val_clean or "contact info" in val_clean:
            return True
    return False

def extract_candidate_info_from_markdown(md_text: str) -> dict:
    if not md_text:
        return {'name': None, 'contact_info': None}
        
    lines = [l.strip() for l in md_text.split('\n') if l.strip()]
    top_lines = lines[:20]
    
    # 1. Emails
    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', md_text)
    
    # 2. Phones
    phones = re.findall(r'\(?\+?\d{1,3}\)?[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}', md_text)
    
    # 3. LinkedIn
    linkedins = re.findall(r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+', md_text, re.IGNORECASE)
    
    # 4. Locations (look at individual lines or line segments)
    locations = []
    for line in top_lines:
        for segment in re.split(r'[\|\:\-•]', line):
            seg = segment.strip()
            if re.match(r'^[A-Z][a-zA-Z\s]{1,30},\s*(?:[A-Z]{2}|[A-Z][a-zA-Z\s]{1,20})$', seg):
                locations.append(seg)

    candidate_name = None
    ignore_words = {'resume', 'curriculum', 'vitae', 'summary', 'experience', 'education', 'skills', 'profile', 'work', 'history', 'projects', 'contact', 'overview', 'page'}
    
    for line in top_lines:
        clean_line = re.sub(r'^[#*_\-\s]+', '', line).strip()
        words = clean_line.lower().split()
        if not words:
            continue
        if set(words) & ignore_words:
            continue
        if re.search(r'@|http|\.com|\.org|\d{5}', clean_line):
            continue
            
        parts = re.split(r'[\|\:\-•,]', clean_line)
        possible_name = parts[0].strip()
        
        name_words = possible_name.split()
        if 1 <= len(name_words) <= 4 and all(w.replace('.', '').replace("'", '').replace('-', '').isalpha() for w in name_words):
            if possible_name.lower() not in ignore_words and len(possible_name) > 1:
                candidate_name = possible_name
                break

    contact_parts = []
    if emails:
        contact_parts.append(emails[0])
    if phones:
        contact_parts.append(phones[0])
    if locations:
        loc = locations[0].strip()
        if not emails or loc.lower() not in emails[0].lower():
            contact_parts.append(loc)
    if linkedins:
        contact_parts.append(linkedins[0])

    return {
        'name': candidate_name,
        'contact_info': ' | '.join(contact_parts) if contact_parts else None
    }

async def extract_profile_node(state: AgentState) -> AgentState:
    """
    Extracts a structured representation of the candidate from the raw markdown.
    """
    truncated_md = truncate_markdown(state['parsed_markdown'])
    prompt = f"""
    You are an expert Resume Parser. Your task is to accurately extract the candidate's professional profile from the following OCR/Parsed Markdown of their resume.

    RAW RESUME MARKDOWN:
    {truncated_md}

    Extract the information into a strict JSON object with these exact keys:
    - "name": Candidate's full name (extract the real name from the resume header, NOT a placeholder)
    - "contact_info": Phone, email, location, linkedin (combine the real details into one string)
    - "summary": A brief professional summary based on the resume (max 2 sentences)
    - "skills": A list of all skills found (strings)
    - "experience": A list of job roles. Each should have "job_title", "company", "duration", and "responsibilities" (list of strings).
    - "education": A list of degrees/institutions.

    CRITICAL RULES:
    1. Respond ONLY with valid JSON. Do not include markdown formatting like ```json or any other text.
    2. Do NOT hallucinate or output placeholder values like 'Full Name' or 'Candidate Name'. Extract the actual text from the top of the resume.
    """
    try:
        response_text = await call_sarvam_ai(prompt, temperature=0.1)
        clean_text = str(response_text)
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].strip()
            
        start = clean_text.find('{')
        end = clean_text.rfind('}')
        if start != -1 and end != -1 and end >= start:
            clean_text = clean_text[start:end+1]
            
        profile_data = json.loads(clean_text, strict=False)
        state['extracted_profile'] = profile_data
    except Exception as e:
        # Graceful fallback: empty profile
        state['extracted_profile'] = {"error": "Failed to extract profile", "details": str(e)}

    # Verify candidate name and contact info with python fallback extraction
    fallback = extract_candidate_info_from_markdown(state['parsed_markdown'])
    
    current_name = state['extracted_profile'].get('name')
    if is_placeholder(current_name, "name"):
        if fallback.get('name'):
            state['extracted_profile']['name'] = fallback['name']

    current_contact = state['extracted_profile'].get('contact_info')
    if is_placeholder(current_contact, "contact"):
        if fallback.get('contact_info'):
            state['extracted_profile']['contact_info'] = fallback['contact_info']

    return state

async def ats_score_node(state: AgentState) -> AgentState:
    """
    Generates an ATS score, missing keywords, and match tier based on the JD.
    """
    if not state.get('job_description'):
        state['ats_score'] = 0
        state['missing_keywords'] = []
        state['match_tier'] = "Unknown"
        return state

    truncated_md = truncate_markdown(state['parsed_markdown'])
    prompt = f"""
    You are an expert ATS (Applicant Tracking System) Scanner.
    
    JOB DESCRIPTION:
    {state['job_description']}
    
    CANDIDATE RESUME (EXTRACTED SKILLS & EXPERIENCE):
    {json.dumps(state.get('extracted_profile', {}), indent=2)}
    
    (RAW RESUME FALLBACK):
    {truncated_md[:5000]} 

    Analyze the candidate's fit for the Job Description.
    Respond EXACTLY with a JSON object matching this schema:
    {{
        "ats_score": number (0-100, representing match percentage),
        "missing_keywords": [array of top 5-7 critical skills/keywords in the JD that are MISSING or weakly represented in the resume],
        "match_tier": string ("Weak", "Fair", or "Strong" based on the score. Weak < 50, Fair 50-75, Strong > 75)
    }}

    Respond with ONLY the raw JSON.
    """
    try:
        response_text = await call_sarvam_ai(prompt, temperature=0.1)
        clean_text = str(response_text)
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].strip()
            
        start = clean_text.find('{')
        end = clean_text.rfind('}')
        if start != -1 and end != -1 and end >= start:
            clean_text = clean_text[start:end+1]
            
        ats_data = json.loads(clean_text, strict=False)
        state['ats_score'] = int(ats_data.get('ats_score', 0))
        state['missing_keywords'] = ats_data.get('missing_keywords', [])
        state['match_tier'] = ats_data.get('match_tier', "Unknown")
    except Exception as e:
        state['ats_score'] = 0
        state['missing_keywords'] = ["Error calculating ATS score"]
        state['match_tier'] = "Error"
        
    return state

async def analyze_node(state: AgentState) -> AgentState:
    """
    The main analysis node that generates specific diff suggestions.
    Uses a plain-text delimiter format (NOT JSON) to avoid all quote/escape parsing issues.
    """
    import re as _re

    missing_kw = ", ".join(state.get('missing_keywords', []))

    prompt = f"""
    You are an expert ATS-friendly Resume Writer.

    JOB DESCRIPTION:
    {state['job_description']}

    EXTRACTED CANDIDATE PROFILE:
    {json.dumps(state.get('extracted_profile', {}), indent=2)}

    ATS GAP ANALYSIS:
    - Match Score: {state.get('ats_score', 0)}/100
    - Missing Keywords to Add: {missing_kw}

    CURRENT RESUME (Markdown):
    {truncate_markdown(state['parsed_markdown'])}

    Suggest specific modifications to tailor this resume to the JD. Focus HEAVILY on incorporating the missing keywords.

    OUTPUT FORMAT — Use EXACTLY this delimiter structure. Do NOT use JSON or markdown. Plain text only.

    PROJECTED_SCORE: <integer 0-100>

    [SUGGESTION]
    SECTION: <Experience, Skills, or Summary>
    ROLE: <exact job title if Experience section, else null>
    COMPANY: <exact company name if Experience section, else null>
    ORIGINAL_START
    <The exact original text from the resume to replace. Write the word NULL if this is a brand new addition.>
    ORIGINAL_END
    SUGGESTED_START
    <The complete replacement text with missing keywords and quantifiable metrics.>
    SUGGESTED_END
    REASONING_START
    <Why this change improves the ATS match and which specific keywords it addresses.>
    REASONING_END
    [/SUGGESTION]

    RULES:
    1. Use EXACTLY the delimiters shown above. Do not rename or modify them.
    2. Provide between 1 and 5 [SUGGESTION] blocks. Prioritize the highest-impact changes.
    3. Do NOT touch the Education section. Focus only on Experience, Skills, and Summary.
    4. Do not add any text outside of the PROJECTED_SCORE line and the [SUGGESTION] blocks.
    """

    def _parse_delimiter_response(text: str, fallback_score: int):
        """Parse the custom delimiter format. Returns (proj_score, suggestions_list)."""
        suggestions = []

        score_m = _re.search(r'PROJECTED_SCORE\s*:\s*(\d+)', text)
        proj_score = int(score_m.group(1)) if score_m else fallback_score

        blocks = _re.findall(r'\[SUGGESTION\](.*?)\[/SUGGESTION\]', text, _re.DOTALL)
        for block in blocks:
            # Single-line fields: do NOT use DOTALL so .+ stops at newline
            def _line(pattern, b=block):
                m = _re.search(pattern, b)
                return m.group(1).strip() if m else None

            # Multi-line block fields: use DOTALL to capture across newlines
            def _block(pattern, b=block):
                m = _re.search(pattern, b, _re.DOTALL)
                return m.group(1).strip() if m else None

            def _null_or(val):
                if val is None:
                    return None
                return None if val.strip().lower() in ('null', 'none', '') else val.strip()

            suggestions.append({
                "section":   _line(r'SECTION\s*:\s*([^\n]+)') or 'General',
                "role":      _null_or(_line(r'ROLE\s*:\s*([^\n]+)')),
                "company":   _null_or(_line(r'COMPANY\s*:\s*([^\n]+)')),
                "original":  _null_or(_block(r'ORIGINAL_START\s*(.*?)\s*ORIGINAL_END')),
                "suggested": _block(r'SUGGESTED_START\s*(.*?)\s*SUGGESTED_END'),
                "reasoning": _block(r'REASONING_START\s*(.*?)\s*REASONING_END'),
            })

        return proj_score, suggestions

    try:
        response_text = await call_sarvam_ai(prompt, temperature=0.3)

        if not response_text:
            state['suggestions'] = [{
                "section": "API Issue", "role": None, "company": None,
                "original": None, "suggested": "No text generated by the AI.",
                "reasoning": "The AI returned an empty response."
            }]
            state['projected_score'] = state.get('ats_score', 0)
            state['status'] = "success"
            state['error'] = ""
            return state

        text = str(response_text)

        # --- Primary: delimiter-based parse ---
        proj_score, suggestions = _parse_delimiter_response(text, state.get('ats_score', 0))

        # --- Fallback: if LLM ignored instructions and returned JSON, try JSON parse ---
        if not suggestions:
            try:
                clean = _re.sub(r'```(?:json)?\s*', '', text).strip()
                s = clean.find('{')
                e = clean.rfind('}')
                if s != -1 and e > s:
                    clean = clean[s:e+1]
                parsed = None
                try:
                    parsed = json.loads(clean, strict=False)
                except Exception:
                    try:
                        from json_repair import repair_json
                        r = repair_json(clean, return_objects=True)
                        if isinstance(r, dict):
                            parsed = r
                    except Exception:
                        pass
                if parsed and parsed.get('suggestions'):
                    proj_score = int(parsed.get('projected_score', proj_score))
                    suggestions = parsed['suggestions']
            except Exception:
                pass

        if not suggestions:
            raise ValueError(
                f"Could not extract any suggestions from LLM response. "
                f"Raw (first 400 chars): {text[:400]}"
            )

        state['projected_score'] = proj_score
        state['suggestions'] = suggestions
        state['status'] = "success"
        state['error'] = ""

    except Exception as e:
        state['suggestions'] = [{
            "section":   "Processing Note",
            "role":      None,
            "company":   None,
            "original":  None,
            "suggested": "The AI returned suggestions but could not be parsed. Please try again.",
            "reasoning": f"Parse error: {str(e)}"
        }]
        state['status'] = "success"
        state['error'] = ""

    return state

async def generate_cover_letter_node(state: AgentState) -> AgentState:
    """
    Node to generate a tailored cover letter payload.
    """
    profile = state.get('extracted_profile', {})
    fallback_info = extract_candidate_info_from_markdown(state.get('parsed_markdown', ''))
    
    cand_name = profile.get('name')
    if is_placeholder(cand_name, "name"):
        cand_name = fallback_info.get('name') or "Candidate Name"
        
    cand_contact = profile.get('contact_info')
    if is_placeholder(cand_contact, "contact"):
        cand_contact = fallback_info.get('contact_info') or ""

    header_text = truncate_markdown(state.get('parsed_markdown', ''))[:3000]

    hm_val = (state.get('hiring_manager') or '').strip()
    comp_val = (state.get('company_name') or '').strip()
    
    greeting_guidance = f"Dear {hm_val} and the {comp_val} Hiring Team," if (hm_val and hm_val.lower() != 'hiring manager') else (f"Dear {comp_val} Hiring Team," if comp_val else "Dear Hiring Manager,")

    prompt = f"""
    You are an expert Executive Resume Writer and Career Coach.
    
    CANDIDATE NAME: {cand_name}
    CANDIDATE CONTACT DETAILS: {cand_contact}
    
    RAW RESUME HEADER:
    {header_text}
    
    CANDIDATE PROFILE (Extracted):
    {json.dumps(profile, indent=2)}
    
    TARGET JOB DESCRIPTION:
    {state['job_description']}
    
    TARGET COMPANY:
    {comp_val}
    
    HIRING MANAGER:
    {hm_val}
    
    Task: Author a compelling, executive-level Cover Letter tailored specifically to this candidate and job. 
    
    RULES & FORMATTING:
    1. Do not hallucinate. Rely strictly on facts and skills in the candidate profile.
    2. Respond STRICTLY with a valid JSON object matching this EXACT schema:
       {{
         "candidate_name": "{cand_name}",
         "candidate_title": "Current or Target Professional Title",
         "contact_info": "{cand_contact}",
         "greeting": "{greeting_guidance}",
         "body_paragraphs": [
           "Paragraph 1 (Opening motivation & alignment with company mission)...",
           "Paragraph 2 (Key achievements, core metrics, and domain leadership)...",
           "Paragraph 3 (Technical stack alignment & value delivery)..."
         ],
         "sign_off": "Sincerely,\\n{cand_name}"
       }}
    3. CRITICAL REQUIREMENT FOR CANDIDATE DETAILS: Use the exact candidate name '{cand_name}' and contact info '{cand_contact}'. DO NOT output placeholders like 'Full Name' or 'Candidate Name' or 'email | phone'.
    4. Total body text must be 150-200 words max so it fits elegantly on 1 page.
    5. MANDATORY METRIC & KEYWORD BOLDING: You MUST format key achievements, quantitative metrics (e.g. **7+ years**, **40% efficiency boost**), and core tech stack names (e.g. **Python**, **LangGraph**, **Azure**) using double asterisks `**...**`. EVERY paragraph MUST contain at least 2 to 4 bolded elements.
    """
    
    try:
        response_text = await call_sarvam_ai(prompt, temperature=0.5)
        
        clean_text = str(response_text)
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].strip()
            
        start = clean_text.find('{')
        end = clean_text.rfind('}')
        if start != -1 and end != -1 and end >= start:
            clean_text = clean_text[start:end+1]
        else:
            clean_text = clean_text.strip()
            
        cl_data = json.loads(clean_text, strict=False)
        
        # Post-process & guarantee candidate name and contact info are NEVER placeholder/blank
        if is_placeholder(cl_data.get("candidate_name"), "name"):
            cl_data["candidate_name"] = cand_name
            
        if is_placeholder(cl_data.get("contact_info"), "contact"):
            cl_data["contact_info"] = cand_contact
            
        sign_off = cl_data.get("sign_off", "")
        if not sign_off or is_placeholder(sign_off, "name") or "[Candidate Name]" in sign_off or "[Candidate Full Name]" in sign_off or "[Full Name]" in sign_off:
            cl_data["sign_off"] = f"Sincerely,\n{cl_data['candidate_name']}"
            
        state['cover_letter_data'] = cl_data
    except Exception as e:
        state['cover_letter_data'] = {"error": f"Error generating cover letter: {str(e)}"}
        
    return state

def should_generate_cover_letter(state: AgentState) -> str:
    return "cover_letter"

# Build the LangGraph Workflow
workflow = StateGraph(AgentState)

# Nodes
workflow.add_node("extract_profile", extract_profile_node)
workflow.add_node("ats_score", ats_score_node)
workflow.add_node("analyze", analyze_node)
workflow.add_node("cover_letter", generate_cover_letter_node)

# Edges 
workflow.add_edge(START, "extract_profile")
workflow.add_edge("extract_profile", "ats_score")
workflow.add_edge("ats_score", "analyze")
workflow.add_conditional_edges("analyze", should_generate_cover_letter, {"cover_letter": "cover_letter", END: END})
workflow.add_edge("cover_letter", END)

# Compile LangGraph app
agent_app = workflow.compile()

async def run_agent(parsed_markdown: str, job_description: str, company_name: str = "", hiring_manager: str = ""):
    """
    Entrypoint function to run the compiled LangGraph agent.
    """
    hm = hiring_manager.strip() if hiring_manager.strip() else "Hiring Manager"
    initial_state = AgentState(
        parsed_markdown=parsed_markdown,
        job_description=job_description,
        company_name=company_name,
        hiring_manager=hm,
        extracted_profile={},
        ats_score=0,
        missing_keywords=[],
        match_tier="",
        projected_score=0,
        cover_letter="",
        cover_letter_data={},
        suggestions=[],
        status="started",
        error=""
    )
    
    final_state = await agent_app.ainvoke(initial_state)
    return final_state
