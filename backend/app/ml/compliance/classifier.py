"""BERT notice classifier — two-stage (authority → type) per CONTEXT D-03.

Stage 1: 5-way authority classifier (GST, IT, MCA, RBI, SEBI). Simpler task,
target ~98% accuracy.

Stage 2: per-authority type classifier (8-15 classes per authority).

Both stages share the same base model (D-01: ai4bharat/indic-bert preferred,
empirically validated during /gsd:research-phase 10).

Inference runs in compliance Celery worker only. Models loaded lazily and held
in module-level cache. CLASS-04: confidence below 0.75 → human review queue.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# NOTE: Heavy imports (torch, transformers) are deferred to first inference call
# to keep the v1.0 worker startup fast. The compliance worker will pre-load on
# first task arrival and cache for subsequent calls.

Authority = Literal["GST", "IT", "MCA", "RBI", "SEBI"]

MODEL_DIR = Path("/app/models/compliance")
AUTHORITY_MODEL_PATH = MODEL_DIR / "authority_classifier"
TYPE_MODEL_PATH = MODEL_DIR / "type_classifier"

# Confidence threshold per CLASS-04 — below this routes to human review queue.
CONFIDENCE_THRESHOLD = 0.75


@dataclass
class ClassificationResult:
    authority: Authority
    authority_confidence: float
    notice_type: str
    type_confidence: float
    needs_review: bool
    model_version: str


# Module-level cache for loaded models (per-worker-process)
_authority_model = None
_authority_tokenizer = None
_type_models: dict[Authority, object] = {}


def classify(text: str) -> ClassificationResult:
    """Classify a notice's text in two stages: authority then type.

    Returns ClassificationResult with both confidences and a needs_review flag
    set when EITHER stage's confidence is below CONFIDENCE_THRESHOLD.

    NOTE: This is a Phase 10 Wave 0 skeleton. Implementation lands in Plan 10-XX
    after /gsd:research-phase 10 picks the BERT base model and produces the
    fine-tuned weights.
    """
    raise NotImplementedError(
        "BERT classifier not yet trained. "
        "Run /gsd:research-phase 10 to select base model, then /gsd:plan-phase 10."
    )


def warm_up() -> None:
    """Pre-load both models on worker startup to avoid first-request latency.

    Called from celery worker_process_init signal in compliance worker only.
    """
    raise NotImplementedError("Pending Phase 10 plan execution.")
