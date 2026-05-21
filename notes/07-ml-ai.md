# 07 · ML / AI PIPELINE

> OCR · LinearSVC classifier (85.06%) · BERT + spaCy NER · XGBoost risk scoring
> BYOK LLM: Anthropic · Gemini · OpenAI · Ollama · local regex fallback

## ★ Remember
- 4-stage async pipeline running on Celery
- Tesseract + OpenCV preprocessing
- Local SVC for v1.0 document categories
- BERT + risk_score + SHAP for compliance notices
- BYOK = tenant brings their own LLM API keys

---

## 1. Full pipeline

```
                ┌─────────────┐
   USER ──────► │ /upload     │ ─► Document row PENDING + Celery enqueue
                └─────────────┘
                                                  │
                                                  ▼
┌────────────────────────────────────────────────────────────────┐
│  Celery: process_document_task                                 │
│                                                                │
│  Stage 1 (10%)  read_file        path-traversal-safe FS access │
│  Stage 2 (30%)  extract_text     PDF/DOCX/Image → Tesseract    │
│  Stage 3 (60%)  classify         LinearSVC + TF-IDF            │
│  Stage 4 (80%)  metadata         dateparser · regex            │
│  Stage 5 (90%)  LLM enrichment   multi-provider summary+fields │
│  Stage 6 (100%) commit           UPDATE status='completed'     │
└────────────────────────────────────────────────────────────────┘

For COMPLIANCE notices (compliance_worker · 2 GB RAM):
   BERT (InLegalBERT, deferred)    → authority + notice_type
   spaCy NER                       → entities → ner_extracted_fields
   XGBoost-roadmap risk_scorer     → risk_score + risk_tier + SHAP
   CalibratedClassifier            → confidence → review_queue if low
   Risk tier == 'critical'         → auto-escalation + audit log
```

---

## 2. OCR pipeline

- **PDF** → pdfplumber text first; if empty → image render → OCR
- **DOCX** → python-docx walk + table extraction
- **Image** → OpenCV preprocess → Tesseract

Tesseract preprocessing steps (`backend/app/ml/ocr.py`):

```
upscale_if_small    h < 800px → bicubic
grayscale           cvtColor → BGR2GRAY
deskew              minAreaRect angle correction
threshold           adaptive Gaussian
morphological ops   open/close noise
multi-PSM retry     PSMs 3, 4, 6 → best confidence wins
```

---

## 3. Classifier (v1.0 documents)

- **Model**: `LinearSVC` wrapped in `CalibratedClassifierCV` (for probability calibration)
- **Vectorizer**: TF-IDF (uni- + bi-grams)
- **Categories**: bills · upi · tickets · tax · bank · invoices · unknown
- **Accuracy**: **85.06 %** (exceeds 85 % target)
- **Artifacts**: `/app/models/document_classifier.pkl` + `tfidf_vectorizer.pkl`
- **Loader**: lazy + double-checked locking (`_model_lock`)
- **Threshold**: text < 50 chars → return "unknown" with conf 0
- **Training**: `python -m app.ml.train`, Kaggle datasets via `KAGGLE_USERNAME`/`KAGGLE_KEY`

---

## 4. LLM providers

| Provider | Where |
|----------|-------|
| `ollama` | self-hosted on host · `host.docker.internal:11434` |
| `gemini` | Google AI Studio REST (httpx) |
| `anthropic` | official `anthropic` SDK |
| `openai` | official `openai` SDK |
| `local` | regex-only fallback · zero API cost |

`LLM_PROVIDER` env var selects. Degraded-mode flag set if only regex fallback works.

---

## 5. BYOK AI — Phase 16

```
ai_credentials  (one row per tenant)
   client_id     PK
   provider      'anthropic' | 'gemini'
   key_ciphertext Fernet-encrypted
   model
   created_at / updated_at

Flow:
   /dashboard/settings/ai  → enter key → Test
   POST /api/compliance/ai/test        → provider.test()
   POST /api/compliance/ai/credential  → encrypt + save
   Now: per-notice + per-invoice AI panels light up
```

5 task functions in `backend/app/compliance/services/ai_service.py`:

1. `summarize_notice`
2. `recommend_notice_actions`
3. `summarize_invoice`
4. `recommend_invoice_actions`
5. `suggest_invoice_payment_timing`

Costs go to the tenant's provider account; TaxSync never bills.

---

## 6. Risk scoring (Phase 10)

```
score = (
    authority_severity * 25     # max 25 pts
  + penalty_log_points          # max 30 pts (log10 maps to points)
  + deadline_pressure_points    # max 25 pts (inversely)
  + critical_section_bonus      # 15 pts if regex match
  + risk_tier_chain_bonus       # parent escalation
)

tier:
  >= 85  critical
  >= 60  high
  >= 30  medium
   else  low
```

Hand-crafted rules first (`rules-v1.0`); XGBoost mimic+improve once labeled data lands. SHAP-style explanations come from the explicit weights — top-3 features by absolute contribution rendered as natural-language phrases.

---

## 7. Entity extraction (NER)

- spaCy 3.7.5 small English model
- Custom rule-based section detector (e.g. GST sec 73, sec 74)
- Regex bank: GSTIN · PAN · CIN · INR amounts · dates
- `dateparser` for natural-language deadlines ("within 30 days")
- Output → `compliance_notices.ner_extracted_fields` JSONB
- Surfaced in `NoticeAISection` component

---

## 8. Review queue

- Calibrated confidence < threshold → row inserted into `compliance_review_queue`
- Surfaced at `/dashboard/compliance/review`
- Senior reviewer accepts or overrides classification
- Override re-runs `risk_scorer`
- Activity logged in `compliance_notice_activity`
- Audit entry written (immutable trigger)

---

## 9. AI scope lock (BYOK)

```
SYSTEM:
  You are TaxSync's AI assistant. You may ONLY answer:
    1. Indian regulatory notices (GST/IT/MCA/RBI/SEBI)
    2. Compliance deadlines
    3. Vendor invoices
    4. The 4-stage approval chain
    5. TaxSync workflow questions

  For ANYTHING else (general chat, coding help, jokes, opinions,
  competing products, personal advice, etc.) respond with
  EXACTLY one line:
      OUT_OF_SCOPE
  No prefix, no apology, no quotes — exact 12 characters.

USER:  <prompt>
```

Router catches the `OUT_OF_SCOPE` sentinel and returns HTTP 422 with a friendly toast in the UI.

---

## 10. Perf notes

- v1.0 OCR worker: 1 GB cap, 2 procs, `--max-memory-per-child=512000`
- Compliance worker: 2.5 GB cap (BERT weights ~440 MB)
- HF cache mounted at `/app/models/hf_cache` — survives restart
- Torch **CPU-only** wheel — image stays under 3 GB
- `TOKENIZERS_PARALLELISM=false` avoids fork warnings
- Heavy tasks NEVER block the FastAPI request thread

---

## 11. Model evaluation UI

- `/dashboard/model-evaluation` page
- Live accuracy, confusion matrix, per-category precision / recall
- Pulled from `app/ml/datasets/` + held-out test set
- Manual retrain button (admin only) — runs `python -m app.ml.train`
- Model version tracked in `compliance_notices.model_version`

---

> "Old-school ML for known categories.
> LLM for narrative summary. Never the other way around."

**Why this shape:**
- OCR is sequential per file → CPU bound → fork pool
- Classification is independent of OCR success — feeds on whatever text exists
- LLM is the slowest + least reliable → comes last, soft-fails
- Two queues isolate v1.0 throughput from heavy BERT inference
