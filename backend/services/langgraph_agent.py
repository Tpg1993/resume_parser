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
    - "name": Candidate's full name (or null if not found)
    - "contact_info": Phone, email, location, linkedin (combine into one string)
    - "summary": A brief professional summary based on the resume (max 2 sentences)
    - "skills": A list of all skills found (strings)
    - "experience": A list of job roles. Each should have "job_title", "company", "duration", and "responsibilities" (list of strings).
    - "education": A list of degrees/institutions.

    CRITICAL RULES:
    1. Respond ONLY with valid JSON. Do not include markdown formatting like ```json or any other text.
    2. Do NOT hallucinate. Only extract what is present.
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
    The main analysis node that generates specific diff suggestions using the extracted context.
    """
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
    
    Suggest specific modifications to tailor this resume to the JD. Focus HEAVILY on incorporating the missing keywords and addressing the ATS Gap Analysis.
    Output your suggestions strictly in a JSON format matching this EXACT schema:
    {{
      "projected_score": number (0-100, estimating the NEW ATS score if all these suggestions are applied),
      "suggestions": [
        {{
          "section": "The section of the resume (e.g. Experience, Skills, Summary)",
          "original": "The exact original text to replace (or null if new addition). Make sure this text actually exists in the resume.",
          "suggested": "The proposed new text. Include quantifiable metrics and the missing keywords where appropriate.",
          "reasoning": "Why this change helps match the JD (mention specific keywords addressed)."
        }}
      ]
    }}
    
    CRITICAL RULES:
    1. Output strictly valid JSON matching the schema above.
    2. Respond with ONLY the raw JSON object, starting with {{ and ending with }}.  
    3. Do not place markdown blocks inside the JSON fields.
    4. Ensure string values avoid unescaped inline newlines when possible. Use \\n.
    5. Provide EXACTLY 1 to 5 suggestions. Prioritize the highest-impact changes.
    6. Do NOT suggest any modifications or changes to the Education section whatsoever. Focus purely on Experience, Skills, and Summary.
    """
    
    try:
        response_text = await call_sarvam_ai(prompt, temperature=0.3)
        
        if not response_text:
            response_text = '[{"section": "API Issue", "original": null, "suggested": "No text generated by the AI.", "reasoning": "The AI model returned an empty response."}]'
            
        clean_text = str(response_text)
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].strip()
        
        start = clean_text.find('{')
        end = clean_text.rfind('}')
        if start != -1 and end != -1 and end > start:
            clean_text = clean_text[start:end+1]
        else:
            clean_text = clean_text.strip()
            
        parsed_json = json.loads(clean_text, strict=False)
        
        state['projected_score'] = parsed_json.get('projected_score', state.get('ats_score', 0))
        suggestions_json = parsed_json.get('suggestions', [])
        
        state['suggestions'] = suggestions_json if isinstance(suggestions_json, list) else [suggestions_json]
        state['status'] = "success"
        state['error'] = ""
    except json.JSONDecodeError as jde:
        state['suggestions'] = [{"section": "Parse Error", "original": None, "suggested": response_text, "reasoning": f"Could not parse structured JSON. Error: {str(jde)}"}]
        state['status'] = "success"
        state['error'] = ""
    except Exception as e:
        state['suggestions'] = []
        state['status'] = "failed"
        state['error'] = str(e)
        
    return state

async def generate_cover_letter_node(state: AgentState) -> AgentState:
    """
    Node to generate a tailored cover letter payload.
    """
    prompt = f"""
    You are an expert Career Coach and Executive Resume Writer.
    
    CANDIDATE PROFILE (Extracted):
    {json.dumps(state.get('extracted_profile', {}), indent=2)}
    
    TARGET JOB DESCRIPTION:
    {state['job_description']}
    
    TARGET COMPANY:
    {state['company_name']}
    
    HIRING MANAGER:
    {state['hiring_manager']}
    
    Task: Write a highly professional Cover Letter for this candidate. 
    
    RULES & FORMATTING:
    1. Do not hallucinate skills. Use exactly what is found in the candidate profile.
    2. Respond STRICTLY with a valid JSON object representing the cover letter pieces, matching this EXACT schema:
       {{
         "candidate_name": "Full Name",
         "candidate_title": "Current or Target Title (e.g. Senior Engineer)",
         "contact_info": "email | phone | location | linkedin (combine the ones you find)",
         "greeting": "Dear [Hiring Manager Name/Hiring Manager] and the [Company Name] Hiring Team,",
         "body_paragraphs": [
           "Paragraph 1...",
           "Paragraph 2...",
           "Paragraph 3..."
         ],
         "sign_off": "Sincerely,\\n[Candidate Name]"
       }}
    3. Ensure no conversational fluff outside of the JSON block. THE ENTIRE BODY MUST BE EXTREMELY CONCISE (max 150-200 words). It MUST perfectly fit onto a single page without bleeding over.
    4. Focus heavily on actionable impact. You MUST highlight key metrics, strong verbs, and main technologies by wrapping them in double asterisks (e.g., **decreased latency by 40%**). Ensure absolutely EVERY SINGLE paragraph has at least 2 or 3 of these bolded highlights. Do not leave any paragraph bare.
    """
    
    try:
        response_text = await call_sarvam_ai(prompt, temperature=0.6)
        
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
        state['cover_letter_data'] = cl_data
    except Exception as e:
        state['cover_letter_data'] = {"error": f"Error generating cover letter: {str(e)}"}
        
    return state

def should_generate_cover_letter(state: AgentState) -> str:
    if state.get("company_name"):
        return "cover_letter"
    return END

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
