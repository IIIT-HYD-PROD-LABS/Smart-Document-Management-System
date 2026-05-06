"""Phase 13 unified search — query compliance_notices + documents in one go.

Per RESEARCH-FINAL §1: v2.0 ships PostgreSQL-FTS only. The contract
is identical to the v2.1 Elasticsearch backend so the swap will be a
single-file replacement, not a schema or call-site refactor.

The query uses raw SQL with `to_tsquery` because SQLAlchemy doesn't
have a clean expression-API path for `ts_rank` joined to a UNION ALL.

**Tenancy contract (CRIT-1 second hardening pass):**
  - `compliance_notices` is RLS-scoped (Phase 9 migrations 0015 + 0018 + 0019).
    The per-statement RLS listener enforces tenant isolation even on raw SQL.
  - `documents` has NO compliance RLS — Phase 6 RBAC scopes documents by
    `user_id` at the application layer + sharing via `document_permissions`.
    The unified search MUST therefore add explicit `user_id` predicates to
    the documents leg of the UNION; relying on RLS alone is incorrect.
    Earlier code claimed RLS-only safety; that claim was false and produced
    a cross-user leak. Fixed in this pass: the documents leg now requires
    the document to be either owned by the requester OR shared with them
    via `document_permissions`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


EntityType = Literal["notice", "document"]


@dataclass
class UnifiedSearchHit:
    entity_type: EntityType
    entity_id: int
    rank: float
    title: str
    snippet: str
    metadata: dict


def _normalize_query(q: str) -> Optional[str]:
    """Convert user input into a `tsquery`-safe expression.

    Strips non-word characters and joins remaining terms with `&` so that
    `"DRC-01 GST 2026"` becomes `'DRC' & '01' & 'GST' & '2026'`. Returns
    None if the query is empty after normalization (caller short-circuits).
    """
    tokens = re.findall(r"[A-Za-z0-9]+", q)
    if not tokens:
        return None
    # Lowercase + escape single-quote (defence in depth though
    # SQLAlchemy parameter binding handles escaping for us)
    return " & ".join(t.lower() for t in tokens)


def search(
    db: Session,
    *,
    query: str,
    user_id: int,
    entity_types: Iterable[EntityType] = ("notice", "document"),
    page: int = 1,
    page_size: int = 25,
) -> list[UnifiedSearchHit]:
    """Run unified FTS across compliance_notices + documents.

    Both tables maintain a `search_vector` TSVECTOR column with the same
    `english` configuration. We rank with `ts_rank_cd` (cover density)
    so multi-word matches close together rank higher.

    Tenant isolation:
      - notices: enforced via RLS on `compliance_notices` (Phase 9). Even
        raw SQL respects the per-statement listener.
      - documents: enforced via explicit `(user_id = :user_id OR EXISTS
        document_permissions row)` predicate on the documents leg.
        `documents` is NOT under compliance RLS, so application-layer
        scoping is mandatory.

    `user_id` is required (no default) so callers cannot accidentally
    omit the document scope.
    """
    types = set(entity_types)
    tsquery = _normalize_query(query)
    if tsquery is None:
        return []

    page_size = max(1, min(50, page_size))
    offset = max(0, (page - 1) * page_size)

    parts: list[str] = []
    if "notice" in types:
        parts.append(
            """
            SELECT
                'notice'::text AS entity_type,
                n.id AS entity_id,
                ts_rank_cd(n.search_vector, query, 32) AS rank,
                n.notice_number AS title,
                ts_headline('english',
                    COALESCE(n.notice_number, '') || ' ' || COALESCE(n.authority, ''),
                    query, 'MaxFragments=1, MaxWords=20, MinWords=5'
                ) AS snippet,
                jsonb_build_object(
                    'authority', n.authority,
                    'status', n.status,
                    'risk_tier', n.risk_tier,
                    'received_date', n.received_date,
                    'response_deadline', n.response_deadline,
                    'client_id', n.client_id
                ) AS metadata
            FROM compliance_notices n,
                 to_tsquery('english', :tsquery) query
            WHERE n.search_vector @@ query
            """
        )
    if "document" in types:
        # CRIT-1: documents has no RLS. Scope to (a) the requester's own
        # documents OR (b) documents shared with them via document_permissions.
        parts.append(
            """
            SELECT
                'document'::text AS entity_type,
                d.id AS entity_id,
                ts_rank_cd(d.search_vector, query, 32) AS rank,
                d.original_filename AS title,
                ts_headline('english',
                    COALESCE(d.extracted_text, '')::text,
                    query, 'MaxFragments=1, MaxWords=30, MinWords=5'
                ) AS snippet,
                jsonb_build_object(
                    'category', d.category,
                    'file_type', d.file_type,
                    'created_at', d.created_at,
                    'user_id', d.user_id
                ) AS metadata
            FROM documents d,
                 to_tsquery('english', :tsquery) query
            WHERE d.search_vector @@ query
              AND d.status = 'completed'
              AND (
                d.user_id = :user_id
                OR EXISTS (
                    SELECT 1 FROM document_permissions dp
                    WHERE dp.document_id = d.id
                      AND dp.user_id = :user_id
                )
              )
            """
        )

    if not parts:
        return []

    sql = (
        " UNION ALL ".join(parts)
        + " ORDER BY rank DESC LIMIT :limit OFFSET :offset"
    )
    rows = db.execute(
        text(sql),
        {
            "tsquery": tsquery,
            "user_id": user_id,
            "limit": page_size,
            "offset": offset,
        },
    ).fetchall()

    return [
        UnifiedSearchHit(
            entity_type=row.entity_type,
            entity_id=int(row.entity_id),
            rank=float(row.rank or 0.0),
            title=row.title or "",
            snippet=row.snippet or "",
            metadata=dict(row.metadata) if row.metadata else {},
        )
        for row in rows
    ]
