"""Google Drive document import.

Uses the same GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET as Gmail OAuth, with
drive.readonly scope. Import reuses the v1.0 storage + Celery document
pipeline so files land in DMS and can be attached to compliance notices.
"""
from __future__ import annotations

import logging
import mimetypes
import os
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.utils.security import require_editor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["google-drive"])

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"

ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "image/webp",
    "image/gif",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.google-apps.document",  # export as PDF
}


class DriveAuthUrlResponse(BaseModel):
    authorize_url: str


class DriveFileItem(BaseModel):
    id: str
    name: str
    mime_type: str
    size: Optional[int] = None
    modified_time: Optional[str] = None
    web_view_link: Optional[str] = None


class DriveListResponse(BaseModel):
    files: list[DriveFileItem]
    next_page_token: Optional[str] = None


class DriveImportRequest(BaseModel):
    access_token: str = Field(..., min_length=10)
    file_ids: list[str] = Field(..., min_length=1, max_length=25)
    create_notices: bool = False


class DriveImportResult(BaseModel):
    file_id: str
    name: str
    status: str
    document_id: Optional[int] = None
    notice_id: Optional[int] = None
    error: Optional[str] = None


class DriveImportResponse(BaseModel):
    results: list[DriveImportResult]
    summary: dict


def _redirect_uri() -> str:
    base = (settings.BACKEND_URL or "http://localhost:8000").rstrip("/")
    return f"{base}/api/drive/oauth/callback"


@router.get("/oauth/authorize", response_model=DriveAuthUrlResponse)
async def drive_authorize(
    current_user: User = Depends(require_editor),
):
    """Return Google OAuth URL for Drive readonly access."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured (GOOGLE_CLIENT_ID missing)",
        )
    # State carries user+client for CSRF; short-lived opaque random would be
    # better with Redis, but this matches the Gmail flow's signed-state style
    # used elsewhere. Frontend only needs the authorize URL.
    import secrets

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": DRIVE_SCOPE,
        "access_type": "online",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return DriveAuthUrlResponse(authorize_url=f"{AUTH_URL}?{urlencode(params)}")


@router.get("/oauth/callback")
async def drive_oauth_callback(code: str = "", state: str = "", error: str = ""):
    """Exchange code for access token and bounce to the frontend with it.

    Access token is returned in the fragment/query for a one-shot import
    session. It is short-lived and never stored server-side.
    """
    from fastapi.responses import RedirectResponse

    frontend = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
    dest = f"{frontend}/dashboard/upload"
    if error or not code:
        return RedirectResponse(f"{dest}?drive_error={error or 'missing_code'}")

    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return RedirectResponse(f"{dest}?drive_error=oauth_not_configured")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": _redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        logger.warning("drive token exchange failed: %s", resp.text[:200])
        return RedirectResponse(f"{dest}?drive_error=token_exchange_failed")

    data = resp.json()
    access_token = data.get("access_token", "")
    if not access_token:
        return RedirectResponse(f"{dest}?drive_error=no_access_token")

    # Put token in query for the SPA to pick up and clear. Prefer sessionStorage
    # on the client immediately after load.
    return RedirectResponse(f"{dest}?drive_token={access_token}")


@router.get("/files", response_model=DriveListResponse)
async def list_drive_files(
    access_token: str,
    q: str = "",
    page_token: str = "",
    current_user: User = Depends(require_editor),
):
    """List PDF/image/docx files from the user's Drive (token from OAuth)."""
    query_parts = [
        "trashed = false",
        "("
        "mimeType = 'application/pdf' or "
        "mimeType contains 'image/' or "
        "mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or "
        "mimeType = 'application/vnd.google-apps.document'"
        ")",
    ]
    if q.strip():
        safe = q.strip().replace("'", "\\'")
        query_parts.append(f"name contains '{safe}'")

    params: dict = {
        "pageSize": 25,
        "fields": "nextPageToken, files(id,name,mimeType,size,modifiedTime,webViewLink)",
        "q": " and ".join(query_parts),
        "orderBy": "modifiedTime desc",
    }
    if page_token:
        params["pageToken"] = page_token

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            DRIVE_FILES_URL,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="Drive token expired; reconnect")
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Drive list failed: {resp.text[:200]}",
        )
    payload = resp.json()
    files = [
        DriveFileItem(
            id=f["id"],
            name=f.get("name") or "untitled",
            mime_type=f.get("mimeType") or "application/octet-stream",
            size=int(f["size"]) if f.get("size") else None,
            modified_time=f.get("modifiedTime"),
            web_view_link=f.get("webViewLink"),
        )
        for f in payload.get("files", [])
    ]
    return DriveListResponse(
        files=files,
        next_page_token=payload.get("nextPageToken"),
    )


def _import_one_file_sync(
    *,
    access_token: str,
    file_id: str,
    user_id: int,
    client_id: int,
    create_notice: bool,
) -> DriveImportResult:
    """Download one Drive file and persist via storage_service + Document."""
    import httpx as _httpx
    from app.database import SessionLocal
    from app.models.document import Document, DocumentCategory, DocumentStatus
    from app.services.storage_service import save_file

    headers = {"Authorization": f"Bearer {access_token}"}
    with _httpx.Client(timeout=60.0) as client:
        meta_resp = client.get(
            f"{DRIVE_FILES_URL}/{file_id}",
            params={"fields": "id,name,mimeType,size"},
            headers=headers,
        )
        if meta_resp.status_code != 200:
            return DriveImportResult(
                file_id=file_id,
                name=file_id,
                status="failed",
                error=f"meta {meta_resp.status_code}",
            )
        meta = meta_resp.json()
        name = meta.get("name") or f"drive-{file_id}"
        mime = meta.get("mimeType") or "application/octet-stream"

        if mime == "application/vnd.google-apps.document":
            dl = client.get(
                f"{DRIVE_FILES_URL}/{file_id}/export",
                params={"mimeType": "application/pdf"},
                headers=headers,
            )
            if not name.lower().endswith(".pdf"):
                name = f"{name}.pdf"
            mime = "application/pdf"
        else:
            if mime not in ALLOWED_MIME and not mime.startswith("image/"):
                return DriveImportResult(
                    file_id=file_id,
                    name=name,
                    status="failed",
                    error=f"unsupported mime {mime}",
                )
            dl = client.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                params={"alt": "media"},
                headers=headers,
            )
        if dl.status_code != 200:
            return DriveImportResult(
                file_id=file_id,
                name=name,
                status="failed",
                error=f"download {dl.status_code}",
            )
        content = dl.content

    if not content:
        return DriveImportResult(
            file_id=file_id, name=name, status="failed", error="empty file"
        )

    db = SessionLocal()
    try:
        file_path, s3_url = save_file(content, name)
        file_type = (os.path.splitext(name)[1] or "").lstrip(".").lower() or "bin"
        if mime == "application/pdf":
            file_type = "pdf"
        doc = Document(
            user_id=user_id,
            filename=os.path.basename(file_path) if file_path else name,
            original_filename=name,
            file_type=file_type,
            file_size=len(content),
            file_path=file_path if not s3_url else None,
            s3_url=s3_url,
            category=DocumentCategory.UNKNOWN,
            status=DocumentStatus.PENDING,
            source="google_drive",
        )
        db.add(doc)
        db.flush()
        notice_id = None
        if create_notice:
            from app.compliance.models.notice import ComplianceNotice
            from app.compliance.services.notice_service import process_notice_intake

            notice = ComplianceNotice(
                client_id=client_id,
                notice_number=f"DRIVE-{file_id[:8]}",
                authority="GST",
                status="received",
                source="portal",
                document_id=doc.id,
                created_by_user_id=user_id,
            )
            db.add(notice)
            db.flush()
            doc.notice_id = notice.id
            notice_id = notice.id
            process_notice_intake(int(notice.id), notice.response_deadline)

        db.commit()
        db.refresh(doc)
        try:
            from app.tasks.document_tasks import process_document_task

            process_document_task.delay(doc.id)
        except Exception as e:  # noqa: BLE001
            logger.warning("drive import celery delay failed: %s", e)

        return DriveImportResult(
            file_id=file_id,
            name=name,
            status="imported",
            document_id=doc.id,
            notice_id=notice_id,
        )
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.exception("drive import failed for %s", file_id)
        return DriveImportResult(
            file_id=file_id,
            name=name if "name" in locals() else file_id,
            status="failed",
            error=type(e).__name__,
        )
    finally:
        db.close()


@router.post("/import", response_model=DriveImportResponse)
async def import_drive_files(
    body: DriveImportRequest,
    current_user: User = Depends(require_editor),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    """Import selected Drive files into the document pipeline.

    Optional notice stubs require ``X-Client-Id`` plus create_notices=true.
    """
    import asyncio

    client_id = 0
    if x_client_id and x_client_id != "*":
        try:
            client_id = int(x_client_id)
        except ValueError:
            client_id = 0

    create_notices = bool(body.create_notices and client_id > 0)

    loop = asyncio.get_running_loop()
    results: list[DriveImportResult] = []
    uid = int(getattr(current_user, "id"))
    for fid in body.file_ids:
        result = await loop.run_in_executor(
            None,
            lambda file_id=fid: _import_one_file_sync(
                access_token=body.access_token,
                file_id=file_id,
                user_id=uid,
                client_id=client_id,
                create_notice=create_notices,
            ),
        )
        results.append(result)

    ok = sum(1 for r in results if r.status == "imported")
    return DriveImportResponse(
        results=results,
        summary={"ok": ok, "failed": len(results) - ok},
    )
