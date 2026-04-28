"""Phase 10 — Compliance ML pipeline.

Module skeleton for BERT notice classifier, spaCy NER, XGBoost risk scorer,
and auto-escalation logic. Inference runs in the dedicated compliance Celery
worker (queue=compliance, 2GB ceiling) per CLASS-07 zero-regression guard.

See `.planning/phases/10-ml-classification-risk-scoring/10-CONTEXT.md` for
the 32 implementation decisions driving this module.
"""
