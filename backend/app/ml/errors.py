"""Typed errors for the ML text-extraction / classification pipeline."""


class ExtractionEngineError(Exception):
    """Operational failure of an extraction engine (tesseract unavailable,
    model artifacts missing, decode failure, corrupt container).

    Distinct from a genuinely text-free-but-successfully-processed input,
    which returns an empty string and never raises. The task layer treats
    this as retryable/FAILED rather than committing a COMPLETED row with
    silently-empty content.
    """

    def __init__(self, reason: str, *, retryable: bool = True):
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable
