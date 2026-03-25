"""Document API routes - Upload, search, filter, detail, delete."""

import mimetypes
import os
from pathlib import Path
from datetime import datetime, date, timedelta, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path as PathParam, Request, Response, UploadFile, File, Query, status
from pydantic import BaseModel, Field, model_validator
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
from app.models.document_version import DocumentVersion
from app.schemas.document import (
    DocumentResponse, DocumentListResponse, DocumentUploadResponse,
    DocumentStats, DocumentTrends, TrendPoint,
    DocumentVersionResponse, DocumentVersionListResponse, RollbackRequest,
)
from app.schemas.sharing import ShareDocumentRequest, DocumentPermissionResponse
from app.utils.security import get_current_user, require_editor
from app.services.audit_service import log_audit_event
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
    background_tasks: BackgroundTasks = BackgroundTasks(),
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

    # Strip null bytes from filename FIRST to prevent null-byte injection
    # before any path/extension logic operates on the name.
    file.filename = file.filename.replace("\x00", "")

    # Validate file type
    ext = Path(file.filename).suffix.lstrip(".").lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '.{ext}' not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}",
        )

    # Read file bytes with streaming size check to prevent memory exhaustion
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    chunks = []
    total_read = 0
    while True:
        chunk = await file.read(1024 * 1024)  # 1MB chunks
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB",
            )
        chunks.append(chunk)
    file_bytes = b"".join(chunks)
    file_size = total_read

    # Validate file content matches declared type (magic bytes)
    from app.services.storage_service import validate_magic_bytes
    if not validate_magic_bytes(file_bytes, ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File content does not match declared type '.{ext}'",
        )

    # Check for existing document with same original_filename for this user (version control).
    # Use with_for_update() to acquire a row-level lock, preventing race conditions
    # when two concurrent uploads target the same filename.
    existing_doc = db.query(Document).filter(
        Document.original_filename == file.filename,
        Document.user_id == current_user.id,
        Document.status != DocumentStatus.FAILED,
    ).with_for_update().first()

    # Save file to storage
    try:
        file_path, s3_url = save_file(file_bytes, file.filename)
    except Exception as e:
        logger.error("file_storage_failed", filename=file.filename, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File storage is temporarily unavailable. Please try again later.",
        )

    if existing_doc:
        # Snapshot current document state as a version record
        version = DocumentVersion(
            document_id=existing_doc.id,
            version_number=existing_doc.current_version,
            filename=existing_doc.filename,
            original_filename=existing_doc.original_filename,
            file_type=existing_doc.file_type,
            file_size=existing_doc.file_size,
            file_path=existing_doc.file_path,
            s3_url=existing_doc.s3_url,
            extracted_text=existing_doc.extracted_text,
            extracted_metadata=existing_doc.extracted_metadata,
            category=existing_doc.category.value if existing_doc.category else None,
            confidence_score=existing_doc.confidence_score,
            ai_summary=existing_doc.ai_summary,
            ai_extracted_fields=existing_doc.ai_extracted_fields,
            status=existing_doc.status.value if existing_doc.status else None,
            highlighted_text=existing_doc.highlighted_text,
            created_by=current_user.id,
            change_reason="New version uploaded",
        )
        db.add(version)

        # Update the document in-place with new file data
        existing_doc.filename = os.path.basename(file_path) if file_path else file.filename
        existing_doc.file_type = ext
        existing_doc.file_size = file_size
        existing_doc.file_path = file_path
        existing_doc.s3_url = s3_url
        existing_doc.status = DocumentStatus.PENDING
        existing_doc.current_version = existing_doc.current_version + 1
        existing_doc.extracted_text = None
        existing_doc.extracted_metadata = None
        existing_doc.ai_summary = None
        existing_doc.ai_extracted_fields = None
        existing_doc.ai_extraction_status = None
        existing_doc.ai_provider = None
        existing_doc.ai_error = None
        existing_doc.highlighted_text = None

        doc = existing_doc
        try:
            db.commit()
        except (IntegrityError, OperationalError):
            db.rollback()
            # Clean up the orphaned file that was already saved to storage
            delete_file(file_path, s3_url)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Concurrent upload conflict. Please retry.")
        db.refresh(doc)
    else:
        # Create new document record with PENDING status
        doc = Document(
            user_id=current_user.id,
            filename=os.path.basename(file_path) if file_path else file.filename,
            original_filename=file.filename,
            file_type=ext,
            file_size=file_size,
            file_path=file_path,
            s3_url=s3_url,
            status=DocumentStatus.PENDING,
            current_version=1,
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

    background_tasks.add_task(
        log_audit_event, user_id=current_user.id, action="upload",
        resource_type="document", resource_id=doc.id,
        details={"filename": file.filename, "version": doc.current_version},
        ip_address=request.client.host if request.client else None,
    )

    return DocumentUploadResponse(
        id=doc.id,
        filename=doc.original_filename,
        status="pending",
        task_id=task.id,
        message="Document uploaded. Processing started.",
        version=doc.current_version,
    )


@router.get("/shared-with-me", response_model=DocumentListResponse)
@limiter.limit("30/minute")
def get_shared_documents(
    request: Request,
    response: Response,
    page: int = Query(1, ge=1, le=10000),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get documents shared with the current user (excluding deactivated owners)."""
    query = (
        db.query(Document)
        .join(DocumentPermission, DocumentPermission.document_id == Document.id)
        .join(User, Document.user_id == User.id)
        .filter(
            DocumentPermission.user_id == current_user.id,
            User.is_active == True,  # noqa: E712
        )
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
    amount_min: float | None = Query(None, ge=0, le=1e15, description="Minimum document amount"),
    amount_max: float | None = Query(None, ge=0, le=1e15, description="Maximum document amount"),
    page: int = Query(1, ge=1, le=10000),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search documents by extracted text content using PostgreSQL FTS."""
    # Validate filter consistency
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from must not be after date_to",
        )
    if amount_min is not None and amount_max is not None and amount_min > amount_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="amount_min must not exceed amount_max",
        )

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
    page: int = Query(1, ge=1, le=10000),
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
    # Single GROUP BY instead of one COUNT per category (was N+1)
    cat_rows = (
        db.query(Document.category, func.count(Document.id))
        .filter(Document.user_id == current_user.id)
        .group_by(Document.category)
        .all()
    )
    category_counts = {cat.value: count for cat, count in cat_rows if count > 0}
    total = sum(category_counts.values())

    # Recent uploads (last 5)
    recent = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .limit(5)
        .all()
    )

    # Single GROUP BY instead of separate COUNT per status (was N+1)
    status_rows = (
        db.query(Document.status, func.count(Document.id))
        .filter(Document.user_id == current_user.id)
        .group_by(Document.status)
        .all()
    )
    status_counts = {s.value: count for s, count in status_rows}

    return DocumentStats(
        total_documents=total,
        category_counts=category_counts,
        recent_uploads=[DocumentResponse.model_validate(d) for d in recent],
        processing_count=status_counts.get(DocumentStatus.PROCESSING.value, 0),
        completed_count=status_counts.get(DocumentStatus.COMPLETED.value, 0),
        failed_count=status_counts.get(DocumentStatus.FAILED.value, 0),
    )


@router.get("/stats/trends", response_model=DocumentTrends)
@limiter.limit("20/minute")
def get_document_trends(
    request: Request,
    response: Response,
    months: int = Query(12, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get monthly document upload trends for the dashboard chart."""
    from dateutil.relativedelta import relativedelta

    now = datetime.now(timezone.utc)
    start = (now - relativedelta(months=months - 1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(
            func.date_trunc("month", Document.created_at).label("month"),
            func.count().label("count"),
        )
        .filter(
            Document.user_id == current_user.id,
            Document.created_at >= start,
        )
        .group_by("month")
        .order_by("month")
        .all()
    )

    # Build a lookup from query results
    counts_by_month: dict[str, int] = {}
    for row in rows:
        key = row.month.strftime("%Y-%m")
        counts_by_month[key] = row.count

    # Fill in zero-count months for a contiguous array
    trends: list[TrendPoint] = []
    cursor = start
    while cursor <= now:
        key = cursor.strftime("%Y-%m")
        trends.append(TrendPoint(month=key, count=counts_by_month.get(key, 0)))
        cursor += relativedelta(months=1)

    return DocumentTrends(trends=trends)


@router.get("/all", response_model=DocumentListResponse)
@limiter.limit("30/minute")
def get_all_documents(
    request: Request,
    response: Response,
    page: int = Query(1, ge=1, le=10000),
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """Delete multiple documents at once."""
    if not ids or len(ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide 1-100 document IDs.",
        )
    if any(i < 1 for i in ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All document IDs must be positive integers.",
        )
    docs = db.query(Document).filter(
        Document.id.in_(ids),
        Document.user_id == current_user.id,
    ).all()
    deleted = []
    for doc in docs:
        background_tasks.add_task(
            log_audit_event, user_id=current_user.id, action="delete",
            resource_type="document", resource_id=doc.id,
            details={"filename": doc.original_filename},
            ip_address=request.client.host if request.client else None,
        )
        # Delete version files from storage
        for version in doc.versions:
            delete_file(version.file_path, version.s3_url)
        delete_file(doc.file_path, doc.s3_url)
        db.delete(doc)
        deleted.append(doc.id)
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to delete documents")
    return {"deleted": deleted, "count": len(deleted)}


@router.get("/{document_id}/versions", response_model=DocumentVersionListResponse)
@limiter.limit("30/minute")
def list_document_versions(
    request: Request,
    response: Response,
    document_id: int = PathParam(..., ge=1),
    page: int = Query(1, ge=1, le=10000),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all versions of a document, paginated."""
    doc = _get_accessible_document(document_id, current_user, db)

    query = db.query(DocumentVersion).filter(DocumentVersion.document_id == document_id)
    total = query.count()
    versions = (
        query
        .order_by(DocumentVersion.version_number.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # The versions table stores snapshots of *previous* states, so the live
    # document's current_version is never in this table.  Mark the most recent
    # snapshot (current_version - 1) so the frontend knows which entry
    # represents the state just before the latest upload / rollback.
    latest_snapshot_number = doc.current_version - 1
    version_responses = []
    for v in versions:
        vr = DocumentVersionResponse.model_validate(v)
        vr.is_current = (v.version_number == latest_snapshot_number)
        version_responses.append(vr)

    return DocumentVersionListResponse(
        versions=version_responses,
        document_id=document_id,
        current_version=doc.current_version,
        total=total,
    )


@router.post("/{document_id}/rollback", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def rollback_document(
    request: Request,
    response: Response,
    payload: RollbackRequest,
    background_tasks: BackgroundTasks,
    document_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """Rollback a document to a previous version.

    Snapshots the current state as a new version, then restores the target version.
    """
    doc = _get_accessible_document(document_id, current_user, db, require_edit=True)

    # Find the target version
    target_version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document_id,
        DocumentVersion.version_number == payload.version_number,
    ).first()
    if not target_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {payload.version_number} not found",
        )

    # Snapshot current state as a new version
    snapshot = DocumentVersion(
        document_id=doc.id,
        version_number=doc.current_version,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        file_path=doc.file_path,
        s3_url=doc.s3_url,
        extracted_text=doc.extracted_text,
        extracted_metadata=doc.extracted_metadata,
        category=doc.category.value if doc.category else None,
        confidence_score=doc.confidence_score,
        ai_summary=doc.ai_summary,
        ai_extracted_fields=doc.ai_extracted_fields,
        status=doc.status.value if doc.status else None,
        highlighted_text=doc.highlighted_text,
        created_by=current_user.id,
        change_reason=payload.reason or f"Rolled back to version {payload.version_number}",
    )
    db.add(snapshot)

    # Restore the target version onto the document
    new_version_number = doc.current_version + 1
    doc.filename = target_version.filename
    doc.original_filename = target_version.original_filename
    doc.file_type = target_version.file_type
    doc.file_size = target_version.file_size
    doc.file_path = target_version.file_path
    doc.s3_url = target_version.s3_url
    doc.extracted_text = target_version.extracted_text
    doc.extracted_metadata = target_version.extracted_metadata
    if target_version.category:
        try:
            doc.category = DocumentCategory(target_version.category)
        except ValueError:
            doc.category = DocumentCategory.UNKNOWN
    else:
        doc.category = DocumentCategory.UNKNOWN
    doc.confidence_score = target_version.confidence_score or 0.0
    doc.ai_summary = target_version.ai_summary
    doc.ai_extracted_fields = target_version.ai_extracted_fields
    doc.highlighted_text = target_version.highlighted_text
    # Restore the status from the snapshot if available, otherwise default to COMPLETED
    if target_version.status:
        try:
            doc.status = DocumentStatus(target_version.status)
        except ValueError:
            doc.status = DocumentStatus.COMPLETED
    else:
        doc.status = DocumentStatus.COMPLETED
    doc.current_version = new_version_number

    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to rollback document")
    db.refresh(doc)

    background_tasks.add_task(
        log_audit_event, user_id=current_user.id, action="rollback",
        resource_type="document", resource_id=document_id,
        details={"from_version": doc.current_version, "to_version": payload.version_number},
        ip_address=request.client.host if request.client else None,
    )

    return {
        "detail": f"Document rolled back to version {payload.version_number}",
        "document_id": doc.id,
        "new_version": doc.current_version,
        "restored_from": payload.version_number,
    }


@router.get("/{document_id}/versions/{version_number}/download")
@limiter.limit("30/minute")
def download_document_version(
    request: Request,
    response: Response,
    document_id: int = PathParam(..., ge=1),
    version_number: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a specific version of a document file."""
    from app.services.storage_service import get_presigned_url, _validate_path_inside_upload_dir

    doc = _get_accessible_document(document_id, current_user, db)

    version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document_id,
        DocumentVersion.version_number == version_number,
    ).first()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} not found",
        )

    if version.s3_url and settings.USE_S3:
        s3_key = version.s3_url.split(".amazonaws.com/")[-1]
        url = get_presigned_url(s3_key)
        if not url:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate download URL")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=url)

    if not version.file_path or not os.path.exists(version.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version file not found in storage")

    try:
        real_path = _validate_path_inside_upload_dir(version.file_path)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    media_type = mimetypes.guess_type(version.original_filename)[0] or "application/octet-stream"
    return FileResponse(path=real_path, filename=version.original_filename, media_type=media_type)


@router.get("/{document_id}/status")
@limiter.limit("30/minute")
def get_document_status(
    request: Request,
    response: Response,
    document_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get processing status of a document."""
    from celery.result import AsyncResult
    from app.tasks import celery_app

    doc = _get_accessible_document(document_id, current_user, db)

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
@limiter.limit("30/minute")
def download_document(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    document_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the file for a specific document (authenticated)."""
    from app.services.storage_service import get_presigned_url, _validate_path_inside_upload_dir

    doc = _get_accessible_document(document_id, current_user, db)

    background_tasks.add_task(
        log_audit_event, user_id=current_user.id, action="download",
        resource_type="document", resource_id=document_id,
        details={"filename": doc.original_filename},
        ip_address=request.client.host if request.client else None,
    )

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


@router.get("/{document_id}/preview")
@limiter.limit("30/minute")
def preview_document(
    request: Request,
    response: Response,
    document_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview a document inline (Content-Disposition: inline)."""
    from app.services.storage_service import get_presigned_url, _validate_path_inside_upload_dir

    doc = _get_accessible_document(document_id, current_user, db)

    if doc.s3_url and settings.USE_S3:
        s3_key = doc.s3_url.split(".amazonaws.com/")[-1]
        url = get_presigned_url(s3_key)
        if not url:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate preview URL")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=url)

    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in storage")

    try:
        real_path = _validate_path_inside_upload_dir(doc.file_path)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    media_type = mimetypes.guess_type(doc.original_filename)[0] or "application/octet-stream"
    return FileResponse(path=real_path, media_type=media_type)


class HighlightItem(BaseModel):
    """Schema for a text highlight selection."""
    text: str = Field(..., max_length=5000)
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)

    @model_validator(mode="after")
    def end_must_be_gte_start(self) -> "HighlightItem":
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


@router.put("/{document_id}/highlights")
@limiter.limit("20/minute")
def save_highlights(
    request: Request,
    response: Response,
    highlights: list[HighlightItem],
    document_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """Save user-highlighted text selections for a document."""
    if len(highlights) > 500:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many highlights (max 500)")
    doc = _get_accessible_document(document_id, current_user, db, require_edit=True)

    doc.highlighted_text = [h.model_dump() for h in highlights]
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to save highlights")

    return {"detail": "Highlights saved", "count": len(highlights)}


@router.get("/{document_id}", response_model=DocumentResponse)
@limiter.limit("60/minute")
def get_document(
    request: Request,
    response: Response,
    document_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single document by ID."""
    doc = _get_accessible_document(document_id, current_user, db)
    return DocumentResponse.model_validate(doc)


@router.post("/{document_id}/share")
@limiter.limit("20/minute")
def share_document(
    request: Request,
    response: Response,
    payload: ShareDocumentRequest,
    background_tasks: BackgroundTasks,
    document_id: int = PathParam(..., ge=1),
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

    if not target_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot share with deactivated user")

    if target_user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot share with yourself")

    if target_user.id == doc.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot share with document owner")

    existing = db.query(DocumentPermission).filter(
        DocumentPermission.document_id == document_id,
        DocumentPermission.user_id == target_user.id,
    ).first()

    if existing:
        existing.permission = payload.permission
        try:
            db.commit()
        except (IntegrityError, OperationalError):
            db.rollback()
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to update permission")
        background_tasks.add_task(
            log_audit_event, user_id=current_user.id, action="share",
            resource_type="document", resource_id=document_id,
            details={"shared_with_email": payload.email, "permission": payload.permission},
            ip_address=request.client.host if request.client else None,
        )
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
    background_tasks.add_task(
        log_audit_event, user_id=current_user.id, action="share",
        resource_type="document", resource_id=document_id,
        details={"shared_with_email": payload.email, "permission": payload.permission},
        ip_address=request.client.host if request.client else None,
    )
    return {"detail": "Document shared", "permission_id": perm.id}


@router.get("/{document_id}/permissions", response_model=list[DocumentPermissionResponse])
@limiter.limit("30/minute")
def get_document_permissions(
    request: Request,
    response: Response,
    document_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List who has access to a document."""
    # Validate document exists first (prevents silent empty-list on bogus IDs for admins)
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Only owner or admin may list permissions
    if doc.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Single JOIN instead of one SELECT per permission (was N+1)
    rows = (
        db.query(DocumentPermission, User)
        .join(User, DocumentPermission.user_id == User.id)
        .filter(DocumentPermission.document_id == document_id)
        .all()
    )

    result = []
    for p, user in rows:
        result.append(DocumentPermissionResponse(
            id=p.id,
            document_id=p.document_id,
            user_id=p.user_id,
            user_email=user.email,
            user_name=user.full_name or user.username,
            permission=p.permission,
            granted_by=p.granted_by,
            created_at=p.created_at,
        ))
    return result


@router.delete("/{document_id}/share/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
def revoke_share(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    document_id: int = PathParam(..., ge=1),
    permission_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """Revoke a document share."""
    # Validate document exists first
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Only owner or admin may revoke shares
    if doc.user_id != current_user.id and current_user.role != "admin":
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

    background_tasks.add_task(
        log_audit_event, user_id=current_user.id, action="unshare",
        resource_type="document", resource_id=document_id,
        details={"permission_id": permission_id},
        ip_address=request.client.host if request.client else None,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def delete_document(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    document_id: int = PathParam(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """Delete a document and its associated file."""
    # Only document owner or admin can delete (shared edit users cannot)
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    background_tasks.add_task(
        log_audit_event, user_id=current_user.id, action="delete",
        resource_type="document", resource_id=document_id,
        details={"filename": doc.original_filename},
        ip_address=request.client.host if request.client else None,
    )

    # Delete version files from storage
    for version in doc.versions:
        delete_file(version.file_path, version.s3_url)

    # Delete current file from storage
    delete_file(doc.file_path, doc.s3_url)

    # Delete from database
    db.delete(doc)
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to delete document")
