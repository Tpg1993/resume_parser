import os
import uuid
import tempfile
from docling.document_converter import DocumentConverter

def parse_pdf_from_buffer(content: bytes) -> str:
    """
    Saves the uploaded PDF to a temporary file, processes it with Docling 
    to extract layout-aware markdown, and cleans up the temporary file.
    """
    # Use system temp dir to GUARANTEE there are no spaces in the absolute path. 
    # "resume parser" has a space and Docling internals crash with Errno 22 on unescaped spaces in Windows!
    sys_temp = tempfile.gettempdir()
    temp_path = os.path.join(sys_temp, f"docling_doc_{uuid.uuid4().hex}.pdf")
    
    try:
        # Save exact file buffer securely into memory
        with open(temp_path, "wb") as buffer:
            buffer.write(content)
        
        # Convert PDF to structured document and export as markdown
        converter = DocumentConverter()
        result = converter.convert(temp_path)
        return result.document.export_to_markdown()
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
