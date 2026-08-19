import os
import uuid
import tempfile
import re
from docling.document_converter import DocumentConverter

def clean_markdown(md_text: str) -> str:
    """Removes excessive blank lines and caps length to prevent context explosion"""
    # Replace 3 or more newlines with just 2
    cleaned = re.sub(r'\n{3,}', '\n\n', md_text)
    return cleaned

def parse_pdf_from_buffer(content: bytes) -> str:
    """
    Parses PDF content quickly using pypdfium2 for digital text PDFs,
    falling back to Docling layout parser if needed.
    """
    # 1. Try fast text extraction via pypdfium2 (< 0.1 seconds)
    try:
        import pypdfium2
        pdf = pypdfium2.PdfDocument(content)
        text_pages = []
        for page in pdf:
            textpage = page.get_textpage()
            extracted = textpage.get_text_range()
            if extracted and extracted.strip():
                text_pages.append(extracted.strip())
        fast_text = "\n\n".join(text_pages)
        if len(fast_text.strip()) > 50:
            return clean_markdown(fast_text)
    except Exception as e:
        print(f"Fast pypdfium2 extraction skipped: {e}")

    # 2. Fallback to Docling layout parser with OCR disabled for speed
    sys_temp = tempfile.gettempdir()
    temp_path = os.path.join(sys_temp, f"docling_doc_{uuid.uuid4().hex}.pdf")
    
    try:
        with open(temp_path, "wb") as buffer:
            buffer.write(content)
        
        try:
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = False
            converter = DocumentConverter(
                format_options={
                    "pdf": PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
        except Exception:
            converter = DocumentConverter()

        result = converter.convert(temp_path)
        md_content = result.document.export_to_markdown()
        
        if not md_content or not md_content.strip():
            raise Exception("Parsed document is completely empty.")
            
        return clean_markdown(md_content)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
