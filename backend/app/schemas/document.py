"""Pydantic schemas for Document request/response models."""

from datetime import datetime
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    category: str
    confidence_score: float
    extracted_text: str | None
    extracted_metadata: dict | None = None
    ai_summary: str | None = None
    ai_extracted_fields: dict | None = None
    ai_extraction_status: str | None = None
    ai_provider: str | None = None
    highlighted_text: list | None = None
    status: str
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
    page: int = 1
    per_page: int = 20


class DocumentUploadResponse(BaseModel):
    id: int
    filename: str
    status: str
    message: str = "Document uploaded successfully. Processing started."
    task_id: str | None = None


class DocumentStats(BaseModel):
    total_documents: int
    category_counts: dict[str, int]
    recent_uploads: list[DocumentResponse]
    processing_count: int
    completed_count: int
    failed_count: int
