"""Document API routes - Upload, search, filter, detail, delete."""

import mimetypes
import os
from pathlib import Path
from datetime import datetime, date, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, Float
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.config import settings
from app.utils.rate_limiter import limiter
from app.database import get_db
from app.models.user import User
from app.models.document import Document, DocumentCategory, DocumentStatus
from app.models.document_permission import DocumentPermission
from app.schemas.document import (
    DocumentResponse, DocumentListResponse, DocumentUploadResponse,
    DocumentStats,
)
from app.schemas.sharing import ShareDocumentRequest, DocumentPermissionResponse
from app.utils.security import get_current_user, require_editor
from app.services.storage_service import save_file, delete_file

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/api/documents", tags=["Documents"])


def _get_accessible_document(document_id: int, user: User, db: Session, require_edit: bool = False) -> Document:
    """Get a document if the user is owner, admin, or has shared access."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Owner always has access
    if doc.user_id == user.id:
        return doc

    # Admin has access to all documents
    if user.role == "admin":
        return doc

    # Check shared permissions
    perm = db.query(DocumentPermission).filter(
        DocumentPermission.document_id == document_id,
        DocumentPermission.user_id == user.id,
    ).first()

    if not perm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if require_edit and perm.permission != "edit":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Edit permission required")

    return doc


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_document(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor),
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
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to save document record")
    db.refresh(doc)

    # Dispatch async processing
    try:
        task = process_document_task.delay(doc.id)
        doc.celery_task_id = task.id
        db.commit()
    except Exception as e:
        logger.error("celery_dispatch_failed", document_id=doc.id, error=str(e))
        doc.status = DocumentStatus.FAILED
        doc.extracted_text = "Processing queue unavailable. Please retry later."
        try:
            db.commit()
        except (IntegrityError, OperationalError):
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document saved but processing queue is unavailable. Please retry later.",
        )

    return DocumentUploadResponse(
        id=doc.id,
        filename=doc.original_filename,
        status="pending",
        task_id=task.id,
        message="Document uploaded. Processing started.",
    )


@router.get("/shared-with-me", response_model=DocumentListResponse)
@limiter.limit("30/minute")
def get_shared_documents(
    request: Request,
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get documents shared with the current user."""
    query = (
        db.query(Document)
        .join(DocumentPermission, DocumentPermission.document_id == Document.id)
        .filter(DocumentPermission.user_id == current_user.id)
    )
    total = query.count()
    documents = (
        query.order_by(Document.created_at.desc())
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


@router.get("/search", response_model=DocumentListResponse)
@limiter.limit("30/minute")
def search_documents(
    request: Request,
    response: Response,
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    category: str | None = Query(None, description="Filter by category"),
    date_from: date | None = Query(None, description="Filter by start date (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Filter by end date inclusive (YYYY-MM-DD)"),
    amount_min: float | None = Query(None, description="Minimum document amount"),
    amount_max: float | None = Query(None, description="Maximum document amount"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search documents by extracted text content using PostgreSQL FTS."""
    query = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.status == DocumentStatus.COMPLETED,
    )

    # Build search filter: OR-combine FTS + trigram for queries > 2 chars.
    # Very short queries (1-2 chars) use ILIKE only — trigram requires min 3-char input.
    # OR-combine ensures typos hit via trigram even when FTS (stemmed) misses.
    if len(q) <= 2:
        # Short queries: ILIKE only (trigram unreliable below 3 chars)
        # Escape SQL LIKE wildcards to prevent pattern injection
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_term = f"%{escaped}%"
        query = query.filter(
            or_(
                Document.extracted_text.ilike(search_term),
                Document.original_filename.ilike(search_term),
            )
        )
        rank_expr = None
    else:
        search_query = func.plainto_tsquery("english", q)
        rank_expr = func.ts_rank(Document.search_vector, search_query)
        # Escape LIKE wildcards for filename search
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        filename_term = f"%{escaped}%"
        query = query.filter(
            or_(
                Document.search_vector.op("@@")(search_query),    # FTS: stemmed exact match
                Document.extracted_text.op("%")(q),               # trigram: typo tolerance
                Document.original_filename.ilike(filename_term),  # filename match
            )
        )

    # Category filter (ignore invalid categories silently)
    if category and category.lower() in {c.value for c in DocumentCategory}:
        query = query.filter(Document.category == DocumentCategory(category.lower()))

    # Date filters (Pydantic auto-validates YYYY-MM-DD format, returns 422 on bad input)
    if date_from:
        query = query.filter(Document.created_at >= datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc))
    if date_to:
        # +1 day for inclusive end boundary (include all of date_to, not just midnight)
        query = query.filter(Document.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc))

    # Amount filters with NULL guard + safe numeric cast
    # Column is JSON (not JSONB), so use json_extract_path_text for ->> equivalent
    # Use ~ regex operator (boolean) instead of regexp_matches (set-returning)
    if amount_min is not None or amount_max is not None:
        amount_text = func.json_extract_path_text(Document.extracted_metadata, 'amount')
        amount_is_numeric = amount_text.op('~')(r'^-?\d+\.?\d*$')
        if amount_min is not None:
            query = query.filter(
                Document.extracted_metadata.isnot(None),
                amount_is_numeric,
                amount_text.cast(Float) >= amount_min,
            )
        if amount_max is not None:
            query = query.filter(
                Document.extracted_metadata.isnot(None),
                amount_is_numeric,
                amount_text.cast(Float) <= amount_max,
            )

    total = query.count()

    # Order by ts_rank for FTS/trigram queries; by created_at for short fallback queries
    if rank_expr is not None:
        documents = (
            query
            .order_by(rank_expr.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
    else:
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
@limiter.limit("30/minute")
def get_documents_by_category(
    request: Request,
    response: Response,
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
@limiter.limit("20/minute")
def get_document_stats(
    request: Request,
    response: Response,
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
@limiter.limit("30/minute")
def get_all_documents(
    request: Request,
    response: Response,
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


@router.post("/batch-delete", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def batch_delete_documents(
    request: Request,
    response: Response,
    ids: list[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """Delete multiple documents at once."""
    if not ids or len(ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide 1-100 document IDs.",
        )
    docs = db.query(Document).filter(
        Document.id.in_(ids),
        Document.user_id == current_user.id,
    ).all()
    deleted = []
    for doc in docs:
        delete_file(doc.file_path, doc.s3_url)
        db.delete(doc)
        deleted.append(doc.id)
    db.commit()
    return {"deleted": deleted, "count": len(deleted)}


@router.get("/{document_id}/status")
@limiter.limit("30/minute")
def get_document_status(
    request: Request,
    response: Response,
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


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the file for a specific document (authenticated)."""
    from app.services.storage_service import get_presigned_url, _validate_path_inside_upload_dir

    doc = _get_accessible_document(document_id, current_user, db)

    if doc.s3_url and settings.USE_S3:
        s3_key = doc.s3_url.split(".amazonaws.com/")[-1]
        url = get_presigned_url(s3_key)
        if not url:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate download URL")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=url)

    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in storage")

    try:
        real_path = _validate_path_inside_upload_dir(doc.file_path)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    media_type = mimetypes.guess_type(doc.original_filename)[0] or "application/octet-stream"
    return FileResponse(path=real_path, filename=doc.original_filename, media_type=media_type)


@router.put("/{document_id}/highlights")
def save_highlights(
    document_id: int,
    highlights: list[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """Save user-highlighted text selections for a document."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc.highlighted_text = highlights
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to save highlights")

    return {"detail": "Highlights saved", "count": len(highlights)}


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single document by ID."""
    doc = _get_accessible_document(document_id, current_user, db)
    return DocumentResponse.model_validate(doc)


@router.post("/{document_id}/share")
def share_document(
    document_id: int,
    payload: ShareDocumentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """Share a document with another user by email."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()
    if not doc and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not doc:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    target_user = db.query(User).filter(User.email == payload.email).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target_user.id == doc.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot share with document owner")

    existing = db.query(DocumentPermission).filter(
        DocumentPermission.document_id == document_id,
        DocumentPermission.user_id == target_user.id,
    ).first()

    if existing:
        existing.permission = payload.permission
        db.commit()
        return {"detail": "Permission updated", "permission_id": existing.id}

    perm = DocumentPermission(
        document_id=document_id,
        user_id=target_user.id,
        permission=payload.permission,
        granted_by=current_user.id,
    )
    db.add(perm)
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Permission already exists")
    db.refresh(perm)
    return {"detail": "Document shared", "permission_id": perm.id}


@router.get("/{document_id}/permissions", response_model=list[DocumentPermissionResponse])
def get_document_permissions(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List who has access to a document."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()
    if not doc and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    perms = db.query(DocumentPermission).filter(
        DocumentPermission.document_id == document_id,
    ).all()

    result = []
    for p in perms:
        user = db.query(User).filter(User.id == p.user_id).first()
        result.append(DocumentPermissionResponse(
            id=p.id,
            document_id=p.document_id,
            user_id=p.user_id,
            user_email=user.email if user else "",
            user_name=user.full_name or user.username if user else "",
            permission=p.permission,
            granted_by=p.granted_by,
            created_at=p.created_at,
        ))
    return result


@router.delete("/{document_id}/share/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(
    document_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """Revoke a document share."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()
    if not doc and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    perm = db.query(DocumentPermission).filter(
        DocumentPermission.id == permission_id,
        DocumentPermission.document_id == document_id,
    ).first()
    if not perm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")

    db.delete(perm)
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to revoke permission")


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def delete_document(
    request: Request,
    response: Response,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor),
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
