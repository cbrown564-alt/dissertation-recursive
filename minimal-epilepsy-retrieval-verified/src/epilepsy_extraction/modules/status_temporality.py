from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_HISTORICAL_RE = re.compile(
    r"\b(previously|historically|used to|in the past|was|had|former|prior|old history|"
    r"no longer|discontinued|stopped|ceased|resolved|previous|past)\b",
    re.IGNORECASE,
)
_CURRENT_RE = re.compile(
    r"\b(currently|now|present|ongoing|active|continues|still|at present|"
    r"current|remains|persisting|continues to|on-going)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StatusAnnotation:
    status: str
    confidence: float
    evidence_phrase: str | None = None


def infer_status(context: str) -> StatusAnnotation:
    """Infer current/historical/unknown from context phrasing."""
    hist = _HISTORICAL_RE.findall(context)
    curr = _CURRENT_RE.findall(context)
    if curr and not hist:
        return StatusAnnotation("current", 0.8, curr[0])
    if hist and not curr:
        return StatusAnnotation("historical", 0.8, hist[0])
    if hist and curr:
        return StatusAnnotation("current", 0.6, None)
    return StatusAnnotation("unknown", 0.5, None)


def annotate_status(
    extraction_data: dict[str, Any],
    context: str,
) -> tuple[dict[str, Any], StatusAnnotation]:
    """Return (unchanged extraction_data, annotation).

    The annotation is stored separately in artifacts, not inside FinalExtraction.
    """
    annotation = infer_status(context)
    return extraction_data, annotation
