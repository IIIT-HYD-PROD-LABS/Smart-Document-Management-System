"""Document API routes - Upload, search, filter, detail, delete."""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.utils.rate_limiter import limiter
from app.database import get_db
from app.models.user import User
from app.models.document import Document, DocumentCategory, DocumentStatus
from app.schemas.document import (
    DocumentResponse, DocumentListResponse, DocumentUploadResponse,
    DocumentStats,
)
from app.utils.security import get_current_user
from app.services.storage_service import save_file, delete_file

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_document(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document file for async OCR + ML classification."""
    from app.tasks.document_tasks import process_document_task

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )

    # Validate file type
    ext = Path(file.filename).suffix.lstrip(".").lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '.{ext}' not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}",
        )

    # Read file bytes
    file_bytes = await file.read()
    file_size = len(file_bytes)

    # Validate file size
    if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB",
        )

    # Save file to storage
    file_path, s3_url = save_file(file_bytes, file.filename)

    # Create document record with PENDING status
    doc = Document(
        user_id=current_user.id,
        filename=os.path.basename(file_path) if file_path else file.filename,
        original_filename=file.filename,
        file_type=ext,
        file_size=file_size,
        file_path=file_path,
        s3_url=s3_url,
        status=DocumentStatus.PENDING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Dispatch async processing
    task = process_document_task.delay(doc.id)
    doc.celery_task_id = task.id
    db.commit()

    return DocumentUploadResponse(
        id=doc.id,
        filename=doc.original_filename,
        status="pending",
        task_id=task.id,
        message="Document uploaded. Processing started.",
    )


@router.get("/{document_id}/status")
def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get processing status of a document."""
    from celery.result import AsyncResult
    from app.tasks import celery_app

    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    result = {
        "document_id": doc.id,
        "status": doc.status.value,
        "category": doc.category.value if doc.category else None,
        "confidence_score": doc.confidence_score,
    }

    # If still processing, check Celery task for progress
    if doc.celery_task_id and doc.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
        task_result = AsyncResult(doc.celery_task_id, app=celery_app)
        if task_result.state == "PROGRESS":
            result["progress"] = task_result.info
        elif task_result.state == "PENDING":
            result["progress"] = {"stage": "queued", "progress": 0}

    return result


@router.get("/search", response_model=DocumentListResponse)
def search_documents(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    category: str | None = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search documents by extracted text content."""
    query = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.status == DocumentStatus.COMPLETED,
    )

    # Text search using ILIKE (case-insensitive)
    search_term = f"%{q}%"
    query = query.filter(
        or_(
            Document.extracted_text.ilike(search_term),
            Document.original_filename.ilike(search_term),
        )
    )

    # Category filter (ignore invalid categories silently)
    if category and category.lower() in {c.value for c in DocumentCategory}:
        query = query.filter(Document.category == DocumentCategory(category.lower()))

    total = query.count()
    documents = (
        query
        .order_by(Document.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/category/{category}", response_model=DocumentListResponse)
def get_documents_by_category(
    category: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all documents filtered by category."""
    try:
        cat_enum = DocumentCategory(category.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category '{category}'. Valid: {[c.value for c in DocumentCategory]}",
        )

    query = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.category == cat_enum,
    )

    total = query.count()
    documents = (
        query
        .order_by(Document.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats", response_model=DocumentStats)
def get_document_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get document statistics for the dashboard."""
    user_docs = db.query(Document).filter(Document.user_id == current_user.id)

    total = user_docs.count()

    # Category counts
    category_counts = {}
    for cat in DocumentCategory:
        count = user_docs.filter(Document.category == cat).count()
        if count > 0:
            category_counts[cat.value] = count

    # Recent uploads (last 5)
    recent = (
        user_docs
        .order_by(Document.created_at.desc())
        .limit(5)
        .all()
    )

    # Status counts
    processing = user_docs.filter(Document.status == DocumentStatus.PROCESSING).count()
    completed = user_docs.filter(Document.status == DocumentStatus.COMPLETED).count()
    failed = user_docs.filter(Document.status == DocumentStatus.FAILED).count()

    return DocumentStats(
        total_documents=total,
        category_counts=category_counts,
        recent_uploads=[DocumentResponse.model_validate(d) for d in recent],
        processing_count=processing,
        completed_count=completed,
        failed_count=failed,
    )


@router.get("/all", response_model=DocumentListResponse)
def get_all_documents(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all documents for the current user."""
    query = db.query(Document).filter(Document.user_id == current_user.id)

    total = query.count()
    documents = (
        query
        .order_by(Document.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single document by ID."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentResponse.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document and its associated file."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Delete from storage
    delete_file(doc.file_path, doc.s3_url)

    # Delete from database
    db.delete(doc)
    db.commit()
