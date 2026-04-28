# Phase 10 — Research Draft

**Drafted:** 2026-04-28 (initial; refine empirically during `/gsd:research-phase 10`)
**Status:** Draft — empirical validation of model selection still required

This document is the starting point for `/gsd:research-phase 10`. It pre-populates research findings, library choices, and known unknowns so the research agent can focus on empirical validation rather than discovery.

---

## 1. BERT Base Model Selection (CONTEXT D-01)

**UPDATE 2026-04-28:** Added Candidate D (`law-ai/InLegalBERT`) after web research revealed an Indian-legal-domain pre-trained BERT from IIT Kharagpur. **This is now the primary recommendation** — likely supersedes Candidates A-C empirically. Final pick must still be empirically validated on a 200-notice held-out set.

Four candidates evaluated below. **Final pick must be empirically validated** on a held-out test set of at least 200 manually labeled Indian compliance notices stratified across the 5 authorities.

### Candidate A — `ai4bharat/indic-bert`

- **Architecture:** ALBERT-base (12 layers, 768 hidden, 12 attention heads, ~33M params after embedding sharing)
- **Pretraining corpus:** 9 billion tokens across 12 Indian languages including code-mixed Hinglish
- **Strengths:** Best for compliance text containing Hinglish (e.g. "ITC reverse karna hai under Section 17(5)"), small footprint (~130MB), fast CPU inference (~30ms p95 on a single notice)
- **Weaknesses:** Older architecture (2020); pure-English IT/RBI notices may underperform vs. larger English-only models
- **License:** MIT
- **HF identifier:** `ai4bharat/indic-bert`

### Candidate B — `bert-base-uncased`

- **Architecture:** BERT-base (12 layers, 768 hidden, 110M params)
- **Pretraining corpus:** English Wikipedia + BookCorpus (3.3B tokens)
- **Strengths:** Industry-standard baseline; abundant fine-tuning literature; excellent on pure-English legal text; HuggingFace ecosystem mature
- **Weaknesses:** Cannot handle Hinglish/Hindi snippets common in GST notices; ~440MB on disk; slower inference (~80ms p95) than indic-bert
- **License:** Apache-2.0
- **HF identifier:** `bert-base-uncased`

### Candidate C — `nlpaueb/legal-bert-base-uncased`

- **Architecture:** BERT-base (same as B)
- **Pretraining corpus:** EU/US legal text (~12GB) — court opinions, contracts, legislation
- **Strengths:** Domain-adapted to legal vocabulary (terms like "show cause", "penalty under section", "appellate authority" are in distribution); 5-15% accuracy lift on Western legal-text benchmarks
- **Weaknesses:** No Indian regulatory corpus in pretraining; unclear if EU/US legal vocabulary transfers to Indian compliance jargon (CBDT/CBIC/RBI Master Directions); same memory footprint as B
- **License:** CC-BY-SA-4.0
- **HF identifier:** `nlpaueb/legal-bert-base-uncased`

### Candidate D — `law-ai/InLegalBERT` ⭐ **PRIMARY RECOMMENDATION**

- **Architecture:** BERT-base (12 layers, 768 hidden, 12 attention heads, ~110M params — same as B/C)
- **Pretraining corpus:** ~5.4 million Indian legal documents from the Supreme Court and many High Courts of India (1950-2019), all legal domains. Curated by IIT Kharagpur Department of Computer Science and Technology.
- **Strengths:** **Already domain-adapted to Indian legal English** — the pretraining corpus contains the exact statutory citation patterns, authority references, and procedural language found in Indian compliance notices. Same tokenizer as legal-bert (preserves comparison validity). Well-documented evaluation on Indian legal benchmarks. IIT Kharagpur reputation lends academic credibility for IIIT Hyderabad project.
- **Weaknesses:** Trained on court documents (judgments + appeals) not directly on regulatory NOTICES — domain shift from court → regulator language is small but non-zero. Pretraining cutoff at 2019 (no recent CBDT/CBIC circulars).
- **License:** Check repo card; appears permissive for research and commercial.
- **HF identifier:** `law-ai/InLegalBERT`
- **Why this changes the bake-off:** The pretraining corpus is 100× more relevant than indic-bert for Indian compliance text. Hypothesis: InLegalBERT wins on all 5 authorities, especially IT/MCA where statutory citations dominate. May obviate the need to maintain separate per-authority models.

### Recommended empirical experiment

1. Hand-label 200 notices stratified across 5 authorities × 40 random types.
2. Fine-tune all 4 candidates with identical hyperparameters (D-05): last 2 layers + classifier head unfrozen, AdamW lr=2e-5, 5 epochs, early stop on val_f1.
3. Evaluate on 30-notice held-out per authority. Pick winner by macro-F1, tiebreaker = inference latency.
4. Document results in `10-MODEL-SELECTION.md` so the choice is reproducible.

**Updated hypothesis (2026-04-28):** InLegalBERT wins overall due to Indian-legal pretraining; indic-bert wins specifically on GST notices that contain Hinglish; bert-base-uncased and legal-bert serve as control baselines. If InLegalBERT >= indic-bert + 3% F1 on the held-out set, ship InLegalBERT as the single base model for both Stage 1 (authority) and Stage 2 (type) classifiers.

---

## 2. spaCy NER Strategy (CONTEXT D-08..D-12)

### Base model

`en_core_web_lg` (~700MB) — has built-in DATE, MONEY, ORG, PERSON, GPE entities that we'll extend.

`en_core_web_trf` (transformer-based) is more accurate but adds another ~500MB and 5-10× inference latency. Recommendation: **stick with `en_core_web_lg`** since regex catches the high-precision entities (GSTIN/PAN/CIN/DIN) and spaCy is only the second layer for free-form entities.

### Custom entity training

Plan to annotate 500 notices via Prodigy or doccano (open-source annotation tools).

Annotation budget:
- 500 notices × 7 entity types × ~30 seconds per annotation = ~30 hours
- One compliance-domain reviewer (CA student or junior associate) over 2 weeks part-time

Custom entity types (CONTEXT D-10):
- `NOTICE_NUMBER` — examples: "DRC-01/2026/A1", "Notice No. 143(2)/2026-27"
- `DEADLINE_DATE` — examples: "by 30th April 2026", "within 30 days from receipt"
- `PENALTY_AMOUNT` — examples: "Rs. 5,00,000/-", "₹2 lakhs", "INR 100000"
- `TAX_DEMAND` — same lexical patterns as PENALTY but contextual ("tax demand of...")
- `LEGAL_SECTION` — captured primarily by regex; spaCy catches edge cases like "as per Notification No. 17/2017-CT(R)"
- `ASSESSMENT_YEAR` — examples: "AY 2024-25", "Assessment Year 2025-26"
- `FINANCIAL_YEAR` — examples: "FY 2023-24", "F.Y. 2024-2025"

### Indian date/currency parsing

- **Dates:** `dateparser` library handles "30th April 2026", "30/04/2026", "30.04.26" with `DATE_ORDER='DMY'` setting.
- **Currency:** custom parser handles "Rs.", "₹", "INR", lakhs/crores notation. Babel handles raw numerics. Convert all to Decimal INR.

---

## 3. XGBoost Risk Scoring (CONTEXT D-13..D-17)

### Library & versions

- `xgboost==2.1.3` — latest stable; Python 3.11+ supported
- `shap==0.46.0` — TreeExplainer is XGBoost-native, ~2ms per explanation on a single notice

### Training data sourcing

The risk scorer needs **pairs of (features, labeled_severity)** — but we don't have a historical labeled corpus. Three bootstrap strategies:

1. **Synthetic distributions, expert-validated tier.** Domain expert (CA/CFO) reviews 100 example notices and assigns severity tier. We treat their labels as ground truth and train on engineered features.
2. **Penalty-magnitude proxy.** Use absolute penalty + days-to-deadline as a heuristic-derived label initially, then refine with active learning as reviewers override the model.
3. **Hand-crafted scoring rules.** Start with a deterministic rule engine (e.g., `0.4 * authority_severity + 0.3 * normalize(penalty) + 0.3 * deadline_pressure`), then train XGBoost to mimic + improve on it. Avoids cold-start.

**Recommendation:** Strategy 3 first (ships in v1), then Strategy 2 + active learning over 6 months.

### Calibration

Critical for the 85/60/30 thresholds to be meaningful. Use Platt scaling on validation set (sklearn `CalibratedClassifierCV`) — XGBoost outputs are not natively calibrated.

### SHAP rendering as natural language

Top-3 features mapped to phrase templates:

| Feature | Phrase template |
|---------|------------------|
| `log(penalty_amount)` | "Penalty of {amount} contributes +{points} points" |
| `days_to_deadline` (low) | "Deadline within {days} days contributes +{points} points" |
| `days_to_deadline` (negative) | "Notice is overdue by {days} days, contributing +{points} points" |
| `authority_severity_weight` | "{Authority} regulator severity contributes +{points} points" |
| `is_critical_section` | "Cited under {section} (high-severity provision) contributes +{points} points" |
| `client_appeal_history_count` | "Client has {n} prior appeals, contributing +{points} points" |

---

## 4. Training Data Sources (CONTEXT D-25..D-28)

**UPDATE 2026-04-28:** Added Hugging Face Indian-legal datasets after web research; rebalanced
volume estimates based on what's actually publicly accessible. GST/IT/MCA private notices
remain off-limits — only synthetic generation + anonymized hand-labeling closes that gap.

### Public sources (~3000-5000 orders)

- **SEBI Adjudication Orders** ⭐ — public on `sebi.gov.in/enforcement/orders`; **thousands of orders available**, structured (party, date, sections, penalty, full text); license: public records. **Highest-volume reliable source for Phase 10 training data.** Starter scraper at `backend/app/ml/datasets/scrape_sebi.py`.
- **RBI Enforcement Orders** — public on `rbi.org.in`; ~500-1000 enforcement actions against banks/NBFCs available; high-severity examples for risk-tier calibration.
- **GST Council advisories + circulars** — public on `gstcouncil.gov.in`; ~200 advisories. NOT raw notices but use the same statutory citation language; useful for vocabulary adaptation.
- **CBDT press releases + sample assessment orders** — public on `incometaxindia.gov.in`; mostly anonymized samples in tax bulletins. Lower volume but high quality.
- **MCA RoC SCNs under §454** — limited public access; mostly redacted; ~50-100 docs realistic.

### Hugging Face Indian-legal datasets (domain pre-training continuation)

- `ninadn/indian-legal` — Indian legal text corpus (volume varies by snapshot)
- `bharatgenai/BhashaBench-Legal` — Indian legal knowledge benchmark (use for evaluation, not training)
- `ShreyasP123/Legal-Dataset-for-india` — Indian legal documents

### Kaggle adjacent datasets (vocabulary adaptation, not classification)

- `adarshsingh0903/legal-dataset-sc-judgments-india-19502024` — SC judgments 1950-2024
- `akshatgupta7/llm-fine-tuning-dataset-of-indian-legal-texts` — Mixed Indian legal corpus
- `keyushnisar/legal-docu` — Indian Legal Documents LuRA
- `anishparkhe0401/indian-laws` — Indian statutes (use for Phase 12 regulation library, not Phase 10)

### What is NOT available

GST DRC-01/ASMT/REG, IT u/s 143(2)/142(1)/156, and MCA SCN are addressed individually to assessees containing PII (PAN, GSTIN, party names, exact amounts). They are **not published anywhere**. Strategy:
- Scrape SEBI + RBI orders for high-volume real data (~5000 examples).
- Synthetic generation via LLM templates (CONTEXT D-25) for the GST/IT/MCA gap.
- Hand-label 50 anonymized real client notices per authority for the held-out test set.

### Synthetic generation (~2000 notices)

LLM-template-driven generation:
1. For each (authority, type) pair, write a regulator-style template with placeholders.
2. Sample placeholders from realistic distributions (PAN/GSTIN format, penalty amounts log-normal around ₹50k-₹50L, deadlines 7-90 days out).
3. Add light variation via paraphrase (replace synonymous boilerplate).
4. Generate ~50 examples per (authority, type) cell = 200 cells × 50 = 10,000 raw, filtered to ~2000 high-quality.

### Hand-labeled real notices (~250)

Compliance team (or CA students) hand-label 50 anonymized notices per authority. PII (names, GSTIN, PAN, amounts >₹100k) anonymized via field replacement.

### Augmentation (~2000 → ~5000 effective)

- **Paraphrase via T5 or similar small model** at low temperature
- **Section-shuffling** within structurally-equivalent paragraphs
- **Date/amount perturbation** with realistic distributions

**Total target:** 5000+ effective examples by launch, growing via active-learning on the human review queue.

---

## 5. Library Versions Pin Rationale

| Library | Version | Why |
|---------|---------|-----|
| `torch` | 2.5.1 | Latest stable with Python 3.11; CPU wheel via `--extra-index-url`; needed for transformers |
| `transformers` | 4.46.3 | Compatible with torch 2.5.x; AutoModelForSequenceClassification API stable since 4.30 |
| `spacy` | 3.7.5 | Compatible with `en_core_web_lg` 3.7.1; slot-filling/training APIs unchanged |
| `xgboost` | 2.1.3 | Native Python API; SHAP TreeExplainer compatible |
| `shap` | 0.46.0 | Latest with NumPy 2.x compat (we're on 1.26.2; works either way) |
| `dateparser` | 1.2.0 | Indian date format support, handles "DMY" order |
| `Babel` | 2.16.0 | Indian number parsing via `babel.numbers` |

---

## 6. Open Questions Still to Resolve in `/gsd:research-phase 10`

1. **Empirical model winner**: indic-bert vs bert-base-uncased vs legal-bert (need 200 test labels)
2. **Annotation tooling**: Prodigy (paid, ~₹30k/year) vs doccano (free, OSS)
3. **Compliance team labeling capacity**: who, hours/week, deadline?
4. **Severity weights**: `AUTHORITY_SEVERITY` placeholder values need CA/CFO sign-off
5. **Active learning loop**: when to retrain — on N reviewer overrides, or weekly cron?
6. **Production GPU plan**: CPU is OK at <500 notices/day; GPU may be needed at 1000+/day. When?

These questions are the primary deliverable of `/gsd:research-phase 10`.

---

## 7. Existing v1.0 ML Code to Reuse

- `app/ml/text_preprocessor.py` — text cleanup utilities
- `app/ml/pdf_extractor.py` — PDF→text
- `app/ml/ocr.py` — image preprocessing + Tesseract OCR
- `app/services/llm/extraction_service.py` — fallback for spaCy when NER confidence is low (use sparingly; LLM is expensive)
- `app/tasks/document_tasks.py` — pattern for Celery task structure (compliance_tasks.py mirrors this)

---

## 8. Anti-patterns to Avoid (from CONTEXT)

1. Do NOT load BERT/XGBoost in v1.0 default-queue worker — that's why CLASS-07 demands a dedicated worker (we've added compliance_worker service in docker-compose.yml).
2. Do NOT bypass calibration — raw BERT softmax overconfident, will route too few notices to human review.
3. Do NOT cache classifier predictions across model versions — invalidate on `model_version` bump.
4. Do NOT train on test set leakage — split before any feature engineering, including label-frequency normalization.
5. Do NOT auto-classify Resolved/Dismissed notices — only Received → Under Review transition triggers classification.

---

*Phase 10 research draft seeded: 2026-04-28*
*Next: `/gsd:research-phase 10` to empirically validate model selection and resolve open questions*
