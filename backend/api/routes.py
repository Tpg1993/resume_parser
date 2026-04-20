from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from typing import Optional
import io
import base64
import datetime
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from services.docling_parser import parse_pdf_from_buffer
from services.langgraph_agent import run_agent

router = APIRouter()

def create_cover_letter_docx(cl_data: dict, company_name: str, hm_name: str) -> str:
    from docx.shared import Pt, Inches
    from docx.oxml.shared import OxmlElement
    from docx.oxml.ns import qn
    import re
    
    doc = Document()
    
    # Optimize fonts and margins for 1-page fit
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(10.5)
    
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)
    
    def set_bottom_border(paragraph):
        pPr = paragraph._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '12') # thickness
        bottom.set(qn('w:space'), '4')
        bottom.set(qn('w:color'), 'auto')
        pBdr.append(bottom)
        pPr.append(pBdr)

    def add_markdown_paragraph(doc, text):
        p = doc.add_paragraph()
        parts = re.split(r'(\*\*.*?\*\*)', text)
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                p.add_run(part[2:-2]).bold = True
            else:
                p.add_run(part)
        return p

    name = cl_data.get("candidate_name", "Candidate Name")
    doc.add_heading(name, level=1)
    
    title = cl_data.get("candidate_title", "")
    if title:
        p_title = doc.add_paragraph()
        p_title.add_run(title).italic = True
        p_title.paragraph_format.space_after = Pt(4)
        
    p_contact = doc.add_paragraph(cl_data.get("contact_info", ""))
    p_contact.paragraph_format.space_after = Pt(16)
    set_bottom_border(p_contact)
    
    # Date (Right aligned)
    day = datetime.datetime.today().day
    suffix = 'th' if 11 <= day <= 13 else {1:'st',2:'nd',3:'rd'}.get(day % 10, 'th')
    formatted_date = datetime.datetime.today().strftime(f'%d{suffix} %B %Y')
    
    p_date = doc.add_paragraph(formatted_date)
    p_date.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_date.paragraph_format.space_after = Pt(16)
    
    hm_text = hm_name if hm_name else "Hiring Manager"
    p_hm = doc.add_paragraph()
    p_hm.add_run(hm_text).bold = True
    p_hm.paragraph_format.space_after = Pt(0)
        
    if company_name:
        p_comp = doc.add_paragraph(f"Hiring Manager, {company_name}")
        p_comp.paragraph_format.space_after = Pt(16)
    else:
        doc.paragraphs[-1].paragraph_format.space_after = Pt(16)
    
    doc.add_paragraph(cl_data.get("greeting", "Hello,"))
    for p in cl_data.get("body_paragraphs", []):
        add_markdown_paragraph(doc, p)
    doc.add_paragraph()
    doc.add_paragraph(cl_data.get("sign_off", f"Sincerely,\n{name}"))
            
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')

@router.post("/upload")
async def upload_resume(
    resume: UploadFile = File(...), 
    jd: str = Form(...),
    company_name: Optional[str] = Form(None),
    hiring_manager: Optional[str] = Form(None)
):
    """
    Endpoint to process an uploaded PDF resume, Job Description, Company Name, and HM.
    """
    if not resume.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        content = await resume.read()
        parsed_markdown = parse_pdf_from_buffer(content)
        
        agent_result = await run_agent(parsed_markdown, jd, company_name or "", hiring_manager or "")
        
        if agent_result.get("status") == "failed":
            raise Exception(f"Agent failed: {agent_result.get('error')}")
            
        cover_letter_docx = None
        cl_data = agent_result.get("cover_letter_data", {})
        if cl_data and not cl_data.get("error"):
            cover_letter_docx = create_cover_letter_docx(cl_data, company_name or "", hiring_manager or "")
            
        return {
            "status": "success",
            "filename": resume.filename,
            "parsed_content": parsed_markdown,
            "suggestions": agent_result.get("suggestions", []),
            "ats_score": agent_result.get("ats_score", 0),
            "projected_score": agent_result.get("projected_score", 0),
            "missing_keywords": agent_result.get("missing_keywords", []),
            "match_tier": agent_result.get("match_tier", "Unknown"),
            "cover_letter_docx": cover_letter_docx
        }
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}\n\nTraceback:\n{error_detail}")
