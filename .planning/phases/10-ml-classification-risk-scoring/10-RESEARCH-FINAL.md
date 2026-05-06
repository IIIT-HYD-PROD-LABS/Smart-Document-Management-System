# Phase 10 — Research Final (decisions committed)

**Finalized:** 2026-05-05
**Supersedes:** 10-RESEARCH.md (which captured the candidate space and the empirical bake-off design)
**Status:** Decisions locked for v2.0 ship; empirical model bake-off + active learning deferred to v2.1

This document closes out the Phase 10 research blockers listed in `STATE.md`.
Decisions here are binding for v2.0 (Phase 10 plans 10-01 through 10-03);
v2.1 is the slot for the BERT empirical bake-off and active-learning loop.

---

## 1. Blocker resolutions

### 1.1 BERT base model selection

**Decision:** `law-ai/InLegalBERT` is the binding choice for v2.0 fine-tuning, with
`ai4bharat/indic-bert` as a documented fallback if Hinglish coverage proves
critical. The empirical 4-way bake-off described in `10-RESEARCH.md §1` is
**deferred to v2.1** because it requires 200+ hand-labeled real Indian compliance
notices we do not have today.

**Why InLegalBERT:**
1. Pre-trained on 5.4M Indian Supreme Court + High Court documents (1950-2019).
   The corpus *contains* the statutory citation patterns, authority references,
   and procedural language that appear in compliance notices. None of the other
   candidates have this much Indian-legal exposure.
2. Same architecture (BERT-base, 110M params) as legal-bert and bert-base-uncased
   so the v2.1 bake-off can be apples-to-apples by swapping the base model only.
3. IIT Kharagpur provenance lends academic legitimacy that compliance customers
   (CA firms, CFOs) can defend in audit conversations.

**v2.0 ship without fine-tuned BERT — what compensates:**
- Rule-based risk scorer (`risk_scorer.py` model_version `rules-v1.0`) ships today
  with the same SHAP-style explanation surface BERT would produce.
- Manual authority/type entry at upload remains authoritative; the review queue
  table is in place so when BERT lands every low-confidence prediction has a
  destination.
- `classify_and_score_notice` Celery task gracefully degrades:
  `bert_classification = None` is documented behavior, not an error.

**v2.1 trigger:** when the labeled corpus reaches 200+ hand-validated notices
across the 5 authorities, run the bake-off described in `10-RESEARCH.md §1`
with InLegalBERT as the new primary candidate.

### 1.2 Training data sourcing

**Decision (committed for v2.0):**

| Source | Volume target | Status |
|--------|--------------|--------|
| SEBI Adjudication Orders (sebi.gov.in/enforcement/orders) | 3000-5000 orders | ✅ Scraper exists (`backend/app/ml/datasets/scrape_sebi.py`); execution deferred to v2.1 fine-tune sprint |
| RBI Enforcement Orders (rbi.org.in) | 500-1000 orders | Scraper TBD in v2.1 |
| LLM-template synthetic generation (40 types × 50 examples) | ~2000 notices | Generator TBD in v2.1 |
| Hand-labeled real anonymized client notices | 50/authority × 5 = 250 | Compliance team capacity TBD |

**Why this works:**
- SEBI alone provides high-volume, structured, public, no-PII data with full
  notice text + party + date + sections + penalty. Five thousand SEBI orders is
  enough to fine-tune Stage 1 (authority classifier — the SEBI bucket alone
  validates the 5-way classifier).
- RBI orders provide the high-severity end of the risk-tier distribution that
  synthetic data tends to under-sample.
- LLM-template synthetic fills the GST/IT/MCA gap where real notices are
  inaccessible (PII-bearing, addressed to specific assessees).
- Hand-labeled real notices (50 per authority) form the held-out test set —
  *never* used for hyperparameter tuning per RESEARCH §1 step 4.

**v2.1 split:** 70/15/15 stratified by class on the combined corpus, with the
held-out test set drawn exclusively from hand-labeled real notices.

### 1.3 Compliance team labeling capacity

**Decision:** **Out of scope for v2.0.** Hand-labeling is an active-learning
cost that compounds over time. v2.0 ships with rule-based scoring + the
notice review queue infrastructure; every reviewer decision the queue captures
is a labeled training example. v2.1 retrains BERT after 30 days of queue
operation produces the first labeled batch.

If the user wants a fixed labeling sprint (e.g., 1 reviewer × 1 week × 50
notices/day = 250 hand-labeled), that's a v2.1 work item; **the v2.0 ship
does not block on it**.

### 1.4 Severity weight calibration

**Decision (committed for v2.0):** Use the placeholder values currently in
`risk_scorer.AUTHORITY_SEVERITY` as the v2.0 ship values. They reflect the
common-sense ranking (RBI > SEBI > IT > GST > MCA based on enforcement teeth
and average penalty magnitude in 2024-2026 enforcement actions).

**v2.1 trigger:** A CA / CFO domain expert reviews + ratifies the values, and
they become editable per-client via Phase 9's `config_overrides` JSONB column.
This is configurable at the data layer today; v2.1 just adds a UI surface.

Current values:

```python
AUTHORITY_SEVERITY = {
    "GST": 0.7,   # Frequent but lower-severity per-notice; volume drives total exposure
    "IT": 0.8,    # Higher per-notice severity; section 271(1)(c) penalties compound
    "MCA": 0.6,   # Procedural-heavy; SCN under §454 has bounded penalty caps
    "RBI": 0.95,  # Banking enforcement is the highest-stakes regulatory action
    "SEBI": 0.9,  # Securities enforcement is publicly disclosed; reputational impact
}
```

---

## 2. v2.0 → v2.1 split

**v2.0 ships now:**
1. Rule-based risk scorer (working, tested) — `model_version="rules-v1.0"`
2. Regex extraction (working, tested) — GSTIN/PAN/CIN/DIN/section
3. Notice review queue infrastructure — table, ORM, router, service hooks
4. Auto-escalation on Critical tier — escalation.py implemented + audit logged
5. Frontend review queue page + confidence/SHAP UI on detail page
6. Source provenance column (`source` ∈ {manual, portal, gmail, imap}) ready
   for Phase 14 + Phase 15 to populate

**v2.1 deferred (depends on labeled data):**
1. InLegalBERT fine-tuning (authority + type stages)
2. spaCy custom NER training (NOTICE_NUMBER, DEADLINE_DATE, PENALTY_AMOUNT,
   TAX_DEMAND, LEGAL_SECTION, ASSESSMENT_YEAR, FINANCIAL_YEAR)
3. SEBI + RBI scraper execution + synthetic generator + augmentation pipeline
4. Active-learning retrain triggered by N reviewer overrides
5. Empirical 4-way model bake-off (InLegalBERT vs indic-bert vs legal-bert vs
   bert-base-uncased)

**Why the v2.0/v2.1 split is correct:**
- v2.0 satisfies CLASS-04 (low-confidence routing) infrastructurally — the
  *target* of low-confidence routing exists even before BERT does.
- RISK-01..RISK-05 (risk scoring + tier + SHAP + escalation + daily refresh)
  are 100% deliverable today via the rule-based scorer.
- INFRA-01 (dedicated 2GB compliance worker) is in place.
- The CLASS-01 92% accuracy target is genuinely blocked on labeled data; v2.0
  honestly admits this rather than shipping a low-quality model that fails
  the success criterion in the field.

CLASS-01..03, CLASS-05..08 are explicitly v2.1; their requirement IDs remain
on the ROADMAP but are decoupled from v2.0's ship gate.

---

## 3. Library versions (locked)

```
torch==2.8.0                  # CPU wheel; required by transformers 5.x
transformers==5.7.0           # InLegalBERT compatible; AutoModelForSequenceClassification stable
spacy==3.7.5                  # en_core_web_lg compatible
xgboost==2.1.3                # Native Python API; SHAP TreeExplainer compatible
shap==0.46.0                  # NumPy 1.26 / 2.x both supported
dateparser==1.2.0             # DD/MM/YYYY parse for Indian notices
Babel==2.16.0                 # Indian numbering (lakhs, crores) parser
beautifulsoup4==4.12.3        # SEBI scraper
lxml==6.1.0                   # SEBI scraper backend
```

All present in `backend/requirements.txt` — Phase 10 Wave 0 setup verified.

---

## 4. Open items deferred to v2.1 explicitly

These are tracked here so v2.1 planning can pick them up without re-discovering:

1. Annotation tooling — Prodigy (paid ~₹30k/yr) vs doccano (free, OSS); v2.1
   pick: doccano unless reviewer throughput < 30 docs/hour, then revisit.
2. Active learning trigger — retrain on N=50 reviewer overrides OR weekly cron,
   whichever fires first.
3. Production GPU plan — CPU is sufficient at <500 notices/day. v2.1 adds
   benchmarking; v3.0 adds GPU when sustained throughput crosses 1000/day.
4. Calibration (Platt scaling) — applied after BERT fine-tune in v2.1 only;
   the rule-based scorer needs no calibration (its outputs are not
   probabilities).
5. ONNX runtime export — only if v2.1 profiling shows torch CPU inference
   >500ms p95.

---

*Phase 10 research finalized 2026-05-05.*
*Research blockers in STATE.md are now closed; v2.0 plan is unblocked.*
