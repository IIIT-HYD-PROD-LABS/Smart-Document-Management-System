---
phase: 10-ml-classification-risk-scoring
plan: 03
wave: 3
subsystem: ui
status: code-complete
completed_at: "2026-05-05"
---

# Phase 10 Plan 03 — Frontend Review Queue + SHAP UI — CODE-COMPLETE

## Delivered

1. `frontend/src/types/compliance.ts` — extended `ComplianceNotice` with Phase 10 ML fields (`classifier_authority_confidence`, `classifier_type_confidence`, `risk_score`, `risk_tier`, `ner_extracted_fields`, `model_version`, `classified_at`, `risk_scored_at`, `source`). Added `RiskTier`, `NoticeSource`, `RiskFactor`, `NerExtractedFields`, `ReviewQueueItem`, `ReviewQueueListResponse`, `ReviewAssignRequest` types.
2. `frontend/src/lib/api/compliance.ts` — added `complianceApi.{listPendingReview, getReviewItem, assignReviewLabel}` calls under `/api/compliance/review/*`.
3. `frontend/src/components/compliance/ConfidenceBadge.tsx` — new pill component. Color-coded by worst confidence: green ≥0.90, amber 0.75-0.89, red <0.75 ("Needs review"), gray "Manual entry" when both NULL (v2.0 default).
4. `frontend/src/components/compliance/WhyThisRiskScore.tsx` — new SHAP-style expandable panel. Renders `risk_score` + `risk_tier` in summary line, top-3 factor phrases in details body, model version + scored timestamp in footer. Uses `<details>` for progressive enhancement (works without JS). Empty state for unscored notices.
5. `frontend/src/components/compliance/RiskTierDot.tsx` — upgraded from Phase 9 stub (always rendered unscored em-dash) to full tier-aware variant. Critical tier gets `motion-safe:animate-pulse` (vestibular-safe via Tailwind's reduce-motion modifier). New `tier?: RiskTier | null` and `showLabel?: boolean` props; backward-compatible with existing `<RiskTierDot />` callers.
6. `frontend/src/components/compliance/NoticeTable.tsx` — passes `notice.risk_tier` + `showLabel` to RiskTierDot, expanded column from 80 to 100px.
7. `frontend/src/app/dashboard/compliance/notices/[id]/page.tsx` — header gets ConfidenceBadge next to AuthorityBadge + StatusPill; left column gets WhyThisRiskScore between MetadataPanel and StatusWorkflow.
8. `frontend/src/app/dashboard/compliance/review/page.tsx` — new page at `/dashboard/compliance/review`. Shows pending review items with predicted authority + type + confidence + reason + per-row Assign button. Empty state explains v2.0/v2.1 split clearly so users know why the queue is empty.
9. `frontend/src/app/dashboard/layout.tsx` — added "Review Queue" nav entry with `FiUserCheck` icon, visible to `admin` + `editor` v1.0 roles (compliance role gate enforced server-side via `NOTICE_REVIEW`).

## Acceptance verification

- `docker compose build frontend` succeeded (Next.js 15.5.15 production build with all new TypeScript files)
- `/dashboard/compliance/review` returns 307 (auth redirect — expected behavior, route registers cleanly)
- `/dashboard/compliance` returns 307 (no regression on existing routes)
- All new components honor the existing hex-token color contract (Authority/Status/Risk palettes)
- `motion-safe:` modifier on Critical tier pulse honors `prefers-reduced-motion`

## Notes

- The Assign button on the review queue page uses the predicted values as the auto-fill — full assign-with-dropdown dialog is deferred since v2.0 has no real low-confidence predictions to assign yet (BERT ships in v2.1).
- The empty-state copy explicitly mentions v2.1 so users encountering an empty queue understand the *intentional* behavior rather than reporting it as a bug.
- ConfidenceBadge tooltip surfaces both per-stage confidences (Authority + Type) — important for compliance auditors who need to defend "why was this human-reviewed" with exact numbers.
- WhyThisRiskScore panel renders `top_factors` from `ner_extracted_fields.risk_top_factors` JSONB — Plan 10-01 wired the Celery task to persist this on every classify, ensuring the panel has data without a second query.
