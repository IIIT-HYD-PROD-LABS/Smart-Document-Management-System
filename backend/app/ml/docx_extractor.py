"""DOCX text extraction module."""
import io
import zipfile
import structlog
from docx import Document as DocxDocument

MAX_TEXT_LENGTH = 500_000

logger = structlog.stdlib.get_logger()


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file, including paragraphs and tables."""
    try:
        doc = DocxDocument(io.BytesIO(file_bytes))
        parts = []
        total_len = 0
        truncated = False
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                total_len += len(text)
                if total_len > MAX_TEXT_LENGTH:
                    truncated = True
                    break
                parts.append(text)
        if not truncated:
            for table in doc.tables:
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cells:
                        row_text = " | ".join(cells)
                        total_len += len(row_text)
                        if total_len > MAX_TEXT_LENGTH:
                            truncated = True
                            break
                        parts.append(row_text)
                if truncated:
                    break
        result = "\n".join(parts)
        if truncated:
            logger.warning("docx_text_truncated", chars=len(result), limit=MAX_TEXT_LENGTH)
        else:
            logger.info("docx_text_extracted", chars=len(result))
        return result
    except zipfile.BadZipFile as e:
        logger.error("docx_extraction_failed_bad_zip", error=str(e))
        return ""
    except ValueError as e:
        logger.error("docx_extraction_failed_value_error", error=str(e))
        return ""
    except Exception as e:
        logger.error("docx_extraction_failed", error=str(e))
        return ""
