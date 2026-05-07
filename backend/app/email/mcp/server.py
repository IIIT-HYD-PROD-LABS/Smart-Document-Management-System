"""FastMCP server with 6 Gmail tools — Phase 15 EMAIL-02.

In-memory transport per reconciliation #1 (D-38). Tool bodies live in tools.py
so the @mcp.tool decorator surface stays focused on schema + docstring.
"""
from __future__ import annotations

from fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP(
    "Smart-Docs Gmail Tools",
    instructions=(
        "Read-only Gmail tools for internal compliance and response-drafting agents. "
        "All invocations are audit-logged with PII redaction. "
        "Label modifications are restricted to system-managed labels."
    ),
)


class _BaseArgs(BaseModel):
    user_id: int = Field(description="Originating user id (for RLS context)")
    client_id: int = Field(description="Originating client id (for RLS context)")


class GmailSearchArgs(_BaseArgs):
    query: str = Field(description="Gmail search query (e.g. 'from:gst.gov.in newer_than:7d')")
    max_results: int = Field(default=50, ge=1, le=500)


class GmailReadMessageArgs(_BaseArgs):
    message_id: str = Field(description="Gmail message id")


class GmailListAttachmentsArgs(_BaseArgs):
    message_id: str = Field(description="Gmail message id")


class GmailGetAttachmentArgs(_BaseArgs):
    message_id: str = Field(description="Gmail message id")
    attachment_id: str = Field(description="Gmail attachment id")


class GmailListLabelsArgs(_BaseArgs):
    pass


class GmailModifyLabelsArgs(_BaseArgs):
    message_id: str = Field(description="Gmail message id")
    add_labels: list[str] = Field(default_factory=list)
    remove_labels: list[str] = Field(default_factory=list)


@mcp.tool
def gmail_search(args: GmailSearchArgs) -> dict:
    """Search Gmail messages matching a Gmail-syntax query. Returns message IDs only.

    Body content is NOT returned; use gmail_read_message to fetch a specific message.
    """
    from app.email.mcp.tools import gmail_search_impl
    return gmail_search_impl(args)


@mcp.tool
def gmail_read_message(args: GmailReadMessageArgs) -> dict:
    """Fetch the full body, headers, and attachment metadata for a single Gmail message.

    Returns: {sender, subject, date, body, attachments: [{id, filename, size, mime_type}]}
    """
    from app.email.mcp.tools import gmail_read_message_impl
    return gmail_read_message_impl(args)


@mcp.tool
def gmail_list_attachments(args: GmailListAttachmentsArgs) -> dict:
    """List attachment metadata for a message WITHOUT fetching body. Lower quota cost than read_message."""
    from app.email.mcp.tools import gmail_list_attachments_impl
    return gmail_list_attachments_impl(args)


@mcp.tool
def gmail_get_attachment(args: GmailGetAttachmentArgs) -> dict:
    """Fetch a single attachment as base64-encoded bytes. Use sparingly — quota cost = 20 units."""
    from app.email.mcp.tools import gmail_get_attachment_impl
    return gmail_get_attachment_impl(args)


@mcp.tool
def gmail_list_labels(args: GmailListLabelsArgs) -> dict:
    """List all Gmail labels (system + user-defined) for the connected account."""
    from app.email.mcp.tools import gmail_list_labels_impl
    return gmail_list_labels_impl(args)


@mcp.tool
def gmail_modify_labels(args: GmailModifyLabelsArgs) -> dict:
    """Add or remove labels on a message. RESTRICTED to system-managed labels:
    dms-ingested, dms-bill-flagged, dms-compliance-flagged. All other labels rejected.
    """
    from app.email.mcp.tools import gmail_modify_labels_impl
    return gmail_modify_labels_impl(args)
