"""DOCX text extraction module."""
import io
import structlog
from docx import Document as DocxDocument

logger = structlog.stdlib.get_logger()


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file, including paragraphs and tables."""
    try:
        doc = DocxDocument(io.BytesIO(file_bytes))
        parts = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                parts.append(text)
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        result = "\n".join(parts)
        logger.info("docx_text_extracted", chars=len(result))
        return result
    except Exception as e:
        logger.error("docx_extraction_failed", error=str(e))
        return ""
