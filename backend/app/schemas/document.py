"""Pydantic schemas for Document request/response models."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, model_validator


class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    category: str
    confidence_score: float
    extracted_text: str | None = None
    extracted_metadata: dict | None = None
    ai_summary: str | None = None
    ai_extracted_fields: dict | None = None
    ai_extraction_status: str | None = None
    ai_provider: str | None = None
    highlighted_text: list | None = None
    status: str
    current_version: int = 1
    total_versions: int = 1
    created_at: datetime
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def compute_total_versions(cls, data: Any) -> Any:
        """Compute total_versions from the ORM relationship if available."""
        # When data is an ORM model (from model_validate), pull version count
        if hasattr(data, "versions") and not isinstance(data, dict):
            versions = data.versions
            if versions is not None:
                # +1 to include the current (un-snapshotted) version
                data = {
                    **{k: getattr(data, k) for k in data.__table__.columns.keys()},
                    "total_versions": len(versions) + 1,
                }
        elif isinstance(data, dict) and "total_versions" not in data:
            data["total_versions"] = 1
        return data

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
    version: int | None = None


class DocumentStats(BaseModel):
    total_documents: int
    category_counts: dict[str, int]
    recent_uploads: list[DocumentResponse]
    processing_count: int
    completed_count: int
    failed_count: int


class TrendPoint(BaseModel):
    month: str
    count: int


class DocumentTrends(BaseModel):
    trends: list[TrendPoint]


class DocumentVersionResponse(BaseModel):
    id: int
    version_number: int
    original_filename: str
    file_type: str
    file_size: int
    category: str | None = None
    created_by: int | None = None
    created_at: datetime
    change_reason: str | None = None
    is_current: bool = False

    class Config:
        from_attributes = True


class DocumentVersionListResponse(BaseModel):
    versions: list[DocumentVersionResponse]
    document_id: int
    current_version: int
    total: int


class RollbackRequest(BaseModel):
    version_number: int = Field(..., ge=1, le=2_000_000_000)
    reason: str | None = Field(None, max_length=500)
