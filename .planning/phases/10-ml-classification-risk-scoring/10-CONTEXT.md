# Phase 10: ML Classification + Risk Scoring - Context

**Gathered:** 2026-04-28 (seed scope; awaiting `/gsd:discuss-phase 10` refinement and `/gsd:research-phase 10` to resolve open blockers)
**Status:** Awaiting research (BERT model selection + training data sourcing are open blockers per STATE.md)

<domain>
## Phase Boundary

**In scope:** Notices uploaded via any channel (manual, Phase 14 portal, Phase 15 Gmail) are automatically classified into 40+ types across 5 authorities (GST, IT, MCA, RBI, SEBI), structured fields are extracted via NER, and every notice receives an XGBoost risk score with SHAP explanations. Critical-risk notices auto-escalate. ML inference runs in a dedicated 2GB Celery worker without measurable v1.0 regression.

**Specifically:**

1. BERT-based notice classifier (>92% accuracy on held-out test set) with confidence score per prediction
2. Low-confidence (<0.75) routes to human review queue instead of auto-assigning
3. spaCy NER for notice number, date, authority, deadline, penalty, legal sections
4. Regex-first extraction for GSTIN/PAN/CIN/DIN/section references (well-defined formats)
5. XGBoost risk scoring (0-100) with Critical/High/Medium/Low tier labels
6. SHAP explanations: top 3 risk factors displayed as readable phrases
7. Auto-escalation to Compliance Head for Critical-risk notices
8. Daily risk score recalculation as deadlines approach
9. Dedicated 2GB `compliance` Celery worker; no v1.0 latency regression
10. Training pipeline producing reproducible model artifacts

**Out of scope (explicitly):**

- Active learning / online retraining — v2.1 (need labeled feedback corpus first)
- Multi-language model variants (Hindi, regional) — v3.0 (English-only Indian compliance text in v2.0)
- Generative response drafting using classifier outputs — Phase 12 owns LLM response drafting
- Government portal-specific extractors — Phase 14 owns portal integration
- Regulation library lookups from extracted legal sections — Phase 12 owns regulation library
- Custom fine-tuned LLM for extraction — too costly; use spaCy NER + regex
- Bill classification — Phase 15 owns bill detection (separate from compliance notices)
- Visual layout extraction (e.g., header/footer detection) — text-only classification

</domain>

<decisions>
## Implementation Decisions (proposed seed; refine via `/gsd:discuss-phase 10`)

### Notice Classification (BERT)

- **D-01:** Base model — `ai4bharat/indic-bert` (preferred for Indian compliance text including Hinglish in legal sections), with `bert-base-uncased` as fallback if indic-bert underperforms on validation. Final choice empirically validated during `/gsd:research-phase 10` against a 200-notice held-out set.
- **D-02:** Multi-class single-label classification — one primary notice type per document. 40+ classes mapped to authority-specific taxonomies (e.g., GST: DRC-01, ASMT-10, GSTR-3A, ITC-04; IT: u/s 143(2), 142(1), 156, 245; MCA: SCN under §454, etc.). Authority pre-routing first (5-way), then type classifier within authority.
- **D-03:** Two-stage classifier — Stage 1 predicts authority (5 classes, simpler ~98% target). Stage 2 picks notice type within authority (8-15 classes per authority). Improves per-authority accuracy and surfaces calibrated per-stage confidence.
- **D-04:** Confidence threshold for auto-routing — 0.75 per CLASS-04 requirement. Below threshold → routed to `notice_review_queue` table; user assigns correct class; that label feeds the next training cycle.
- **D-05:** Fine-tuning strategy — last 2 transformer layers + classification head unfrozen; first 10 frozen. Reduces overfitting on small Indian compliance corpora. AdamW, lr=2e-5, weight_decay=0.01, 5 epochs with early stopping on val_f1.
- **D-06:** Inference framework — Hugging Face transformers + torch in eval mode; quantize to int8 via `torch.quantization` after training to halve memory and 2-3× speedup. ONNX runtime export deferred until profiling shows torch CPU inference >500ms p95.
- **D-07:** Calibration — Platt scaling on validation set after training to ensure raw confidence ≈ true accuracy at threshold. Critical for the 0.75 cutoff to be meaningful.

### NER (spaCy + Regex)

- **D-08:** Two-layer extraction — regex first (deterministic, 100% precision on well-defined patterns), spaCy NER second (catches edge cases). Output is union with regex hits taking precedence on conflict.
- **D-09:** Regex patterns (CLASS-06): `GSTIN` (15-char with state code + PAN check), `PAN` (10-char alphanumeric), `CIN` (21-char), `DIN` (8-digit), `section_reference` (`u/s \d+\([0-9a-z]+\)`, `Section \d+`, `Rule \d+`). All compiled at module load.
- **D-10:** Custom spaCy entities for compliance domain: `NOTICE_NUMBER`, `DEADLINE_DATE`, `PENALTY_AMOUNT`, `TAX_DEMAND`, `LEGAL_SECTION`, `ASSESSMENT_YEAR`, `FINANCIAL_YEAR`. Trained on 500+ annotated notices (annotation effort during `/gsd:research-phase`).
- **D-11:** Date normalization — all extracted dates converted to ISO 8601 via `dateparser` library; ambiguous dates (e.g., "12/05/2026") resolved using DD/MM/YYYY for Indian notices.
- **D-12:** Currency parsing — Indian numbering (lakhs, crores, "₹5,00,000") via `babel.numbers` + custom Indian-format parser. All amounts stored as Decimal INR.

### Risk Scoring (XGBoost)

- **D-13:** Features (numeric + one-hot encoded):
  - `penalty_amount` (log-transformed; absolute INR value)
  - `tax_demand_amount` (log-transformed)
  - `total_liability` (log-transformed)
  - `days_to_deadline` (clipped to [0, 365]; negative = overdue)
  - `authority_severity_weight` (lookup: GST=0.7, IT=0.8, MCA=0.6, RBI=0.95, SEBI=0.9)
  - `notice_type_severity` (per-type weight from canonical severity table)
  - `is_critical_section` (boolean: `u/s 271(1)(c)`, `Section 132`, `Penalty under §454`)
  - `client_appeal_history_count` (past notices for this client that went to appeal)
  - `days_since_received`
  - `has_show_cause_chain` (boolean: parent_notice_id set with type=SCN)
- **D-14:** Risk tiers (default thresholds, configurable per client via Phase 9 D-17):
  - Critical: score ≥ 85
  - High: 60 ≤ score < 85
  - Medium: 30 ≤ score < 60
  - Low: score < 30
- **D-15:** SHAP — TreeExplainer (XGBoost native, fast). Top 3 features by absolute SHAP impact rendered as natural-language phrases (e.g., "Penalty above ₹10 lakh contributes +18 points", "Deadline within 5 days contributes +12 points").
- **D-16:** Daily recalculation — APScheduler job at 02:00 IST iterates over open notices and refreshes `risk_score` + `risk_tier`. Triggers re-escalation if a Medium notice crosses to Critical due to deadline proximity.
- **D-17:** Training data — initially synthetic with sampled real penalty distributions; bootstrap with hand-labeled severity from compliance team. Active-learning loop adds reviewer-overridden tiers as training signal.

### Auto-Escalation

- **D-18:** Critical risk → emit `NOTICE_ESCALATION` event → Phase 11 alert pipeline notifies Compliance Head (configurable per client D-17 from Phase 9). Auto-assigns notice to Compliance Head's queue; logs escalation in NoticeActivity (mutable timeline) + audit_log (immutable).
- **D-19:** Escalation cool-down — 24-hour minimum between re-escalations on the same notice to prevent storm if score oscillates near the 85 threshold.
- **D-20:** Escalation chain configurable per client (uses Phase 9 D-17 config_overrides). Default: Compliance Head → CFO → External Counsel (if configured).

### Infrastructure (INFRA-01)

- **D-21:** Dedicated `compliance-worker` Celery service in docker-compose with `--max-memory-per-child=2GB --concurrency=2 --queues=compliance`. v1.0 worker stays on `default` queue with 512MB ceiling. Hard isolation prevents BERT/XGBoost loads from starving v1.0 OCR throughput.
- **D-22:** Model artifacts on disk — `backend/models/compliance/{authority_classifier,type_classifier,ner_pipeline,risk_xgboost,calibrator}.pkl`. Loaded lazily on first inference per worker process; held in module-level cache. Total RAM budget ~1.4GB for all models combined.
- **D-23:** Inference pipeline order: `extract_text` (v1.0 OCR) → `regex_extract` → `ner_extract` → `authority_classify` → `type_classify(authority)` → `feature_engineer` → `risk_score` → `escalation_check` → `persist`. All stages chained in a single Celery task to avoid serialization overhead.
- **D-24:** Performance regression budget: 0% on v1.0 doc upload latency. Verified via dedicated benchmark in CI (run before/after Phase 10 merge; fail PR if v1.0 doc upload p95 latency increases).

### Training Data (CLASS-08)

- **D-25:** Three sources — (1) synthetic generation via LLM with template + regulator boilerplate (covers 40+ types × 50 examples = 2000 base), (2) public Indian GST council notice samples scraped from gstcouncil.gov.in (~500), (3) compliance team hand-labels 50 real anonymized client notices per authority (~250). Target 5000+ via 2× augmentation (paraphrase + section-shuffling).
- **D-26:** Data quality — every notice in training set hand-validated by at least one compliance-domain reviewer. PII (GSTIN, PAN, names) anonymized. Stored in `backend/app/ml/datasets/compliance/{authority}/{type}/{id}.json` with content + label + provenance.
- **D-27:** Train/validation/test split — 70/15/15 stratified by class. Held-out test set never used for hyperparameter tuning. Re-evaluated after every retrain.
- **D-28:** Retraining cadence — quarterly initially, or on confidence drift detection (rolling avg confidence drops below baseline by >5% over 30 days).

### Frontend (UI hint: yes)

- **D-29:** Notice detail surfaces — confidence badge next to authority/type (e.g., "GST DRC-01 · 91%"), top-3 SHAP phrases as a "Why this risk score?" expandable section.
- **D-30:** Human review queue at `/dashboard/compliance/review` — list of low-confidence classifications with edit-class dropdown, sortable by received-date, scoped by RLS.
- **D-31:** Risk tier visualization reuses Phase 9 `RiskTierDot` atom. Critical tier gets a subtle pulse animation to draw attention without being intrusive.
- **D-32:** Reviewer audit — every reviewer-assigned class is recorded in audit_log (Phase 9 AUDIT-01) with `before` (model prediction) and `after` (reviewer label) values. Feeds active-learning corpus.

### Claude's Discretion

All technical implementation specifics (BERT framework version, XGBoost hyperparameter grid, exact API contract for the review queue, NER training data format) are at Claude's discretion within the constraints above.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — CLASS-01..CLASS-08 (Classification), RISK-01..RISK-05 (Risk Scoring), INFRA-01 (Dedicated ML worker)

### Upstream Phases (dependencies)
- `.planning/phases/09-compliance-foundation/09-CONTEXT.md` — ComplianceNotice schema, NoticeType lookup, audit_log immutability, NoticeActivity timeline, RBAC, RLS context, INFRA-06 PII encryption helper

### Existing Codebase (v1.0 ML — extend, don't duplicate)
- `backend/app/ml/classifier.py` — v1.0 TF-IDF + scikit-learn classifier (model loading pattern reused for BERT)
- `backend/app/ml/text_preprocessor.py` — Text cleanup utilities (reused as input pre-processor)
- `backend/app/ml/pdf_extractor.py` — PDF text extraction
- `backend/app/ml/ocr.py` — OCR + image preprocessing
- `backend/app/ml/datasets/prepare.py` — v1.0 dataset preparation pattern (extend for compliance corpus)
- `backend/app/services/llm/extraction_service.py` — v1.0 LLM extraction (reuse for NER bootstrapping)
- `backend/app/tasks/document_tasks.py` — Celery task pattern for ML inference
- `backend/app/models/compliance/notice.py` (Phase 9) — ComplianceNotice ORM (extended with classifier_confidence, risk_score, risk_tier, ner_extracted_fields columns)
- `backend/app/services/notice_service.py` (Phase 9) — Notice service layer (extended with auto_classify entry point)

### Architecture
- `.planning/codebase/ARCHITECTURE.md` — Layered backend architecture
- `.planning/codebase/CONVENTIONS.md` — Coding conventions (Phase 10 must add ML coding conventions: model versioning, deterministic seeds, reproducible training)
- `.planning/codebase/STACK.md` — Technology stack reference (Phase 10 adds: torch, transformers, spaCy, xgboost, shap)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- v1.0 OCR + PDF extraction pipeline — input layer is identical for compliance notices (no parallel pipeline).
- v1.0 Celery task chain pattern — Phase 10 introduces compliance-specific Celery task `classify_and_score_notice` chained after `process_document`.
- v1.0 LLM extraction service (5-provider fallback) — reused as a fallback when spaCy NER confidence is low for specific entity types (e.g., obscure legal sections).
- Phase 9 `notice_service.transition_status` — auto-classification on `Received → Under Review` calls into ML pipeline before transition fires.
- Phase 9 audit_log immutability — every classifier prediction and risk score change is audit-logged (model version, raw output, processed output).
- Phase 9 INFRA-06 PII encryption — extracted GSTIN/PAN encrypted before persistence in NER output cache.

### Established Patterns
- FastAPI router → service → ORM layering.
- Celery task naming `app.tasks.<domain>_tasks.<verb>_<entity>` (e.g., `app.tasks.compliance_tasks.classify_and_score_notice`).
- SQLAlchemy ORM with Alembic migrations.
- Pydantic schemas for I/O validation.
- Service-layer is single point of mutation for business state (Phase 9 D-D pattern — must hold for risk_score and classifier_confidence updates).

### Integration Points
- Backend: New `/api/compliance/review/*` route prefix for human review queue; new `notice_review_queue` table; `ComplianceNotice` extended with `classifier_authority_confidence`, `classifier_type_confidence`, `risk_score`, `risk_tier`, `ner_extracted_fields` (JSONB), `model_version`.
- Celery: New `compliance-worker` service in docker-compose with `--queues=compliance` and 2GB memory ceiling. v1.0 worker keeps `default` queue (zero-regression guard).
- Frontend: New `/dashboard/compliance/review` page; notice detail page extended with confidence badge + SHAP "why" panel.
- Existing notice detail page (Phase 9 Plan 07) gets non-destructive additions only.

### Anti-patterns to Avoid
- Do NOT load BERT/XGBoost in the v1.0 default-queue worker — that's why CLASS-07 demands a dedicated worker.
- Do NOT bypass calibration — raw BERT softmax is overconfident and will route too few notices to human review.
- Do NOT cache classifier predictions across model versions — invalidate on `model_version` bump.
- Do NOT train on test set leakage — split before any feature engineering, including label-frequency normalization.
- Do NOT auto-classify notices in `Resolved` or `Dismissed` status — only `Received → Under Review` transition triggers classification.

</code_context>

<specifics>
## Specific Ideas

- The 40+ notice types are the source of truth for classifier output classes — must align exactly with `notice_types` lookup table (Phase 9 Plan 02).
- BERT model selection has empirical risk — `ai4bharat/indic-bert` is preferred for Hinglish but may underperform on pure-English IT notices. Validate during research phase.
- 5000+ training examples is aspirational — v1 may launch with 2000-3000 from synthetic + scraped sources, with active-learning to grow corpus to 5000+ over 6 months post-launch.
- SHAP explanations matter for compliance — auditors will ask "why was this Critical?" and "Penalty above ₹10 lakh contributed +18 points" is a defensible answer.
- Performance regression on v1.0 is the hardest constraint — separate worker is the only safe path.

</specifics>

<deferred>
## Deferred Ideas

- **Active learning loop with online retraining** — v2.1 once we have a labeled feedback corpus from the human review queue.
- **Multi-language NER** (Hindi, regional) — v3.0; English-only in v2.0.
- **Visual layout extraction** (header/footer/signature detection from PDF) — not required for text-based classification; deferred indefinitely.
- **Graph-based notice linking** beyond `parent_notice_id` (e.g., automatic chain detection across received notices) — Phase 12 will own response-time chain construction.
- **Custom fine-tuned LLM for extraction** — too costly for v2.0; spaCy NER + regex is sufficient.
- **GPU inference** — CPU is sufficient at expected v2.0 scale (<500 notices/day); GPU deferred.
- **Real-time inference on dashboard load** — all classification is async on upload; dashboard reads cached results.

</deferred>

---

*Phase: 10-ml-classification-risk-scoring*
*Context seeded: 2026-04-28 — refine via `/gsd:discuss-phase 10` and `/gsd:research-phase 10` (resolves BERT model selection + training data sourcing blockers) before `/gsd:plan-phase 10`*

## Open Blockers (per STATE.md, must be resolved during `/gsd:research-phase 10`)

1. **BERT base model selection** — `bert-base-uncased` vs `ai4bharat/indic-bert` vs `legal-bert` — needs empirical validation on a 200-notice held-out set with stratified sampling across the 5 authorities.
2. **Training data sourcing** — need 300+ real labeled examples per class × 40+ classes = 12,000+ examples target. Synthetic augmentation strategy needed if real data <300 per class.
3. **Compliance team labeling capacity** — who hand-validates? Hours-per-class budget? On-keyboard for 1 sprint or distributed across 3 months?
4. **Severity weight calibration** — `authority_severity_weight` lookup values are placeholder. Needs domain-expert (CA/CFO) review.
