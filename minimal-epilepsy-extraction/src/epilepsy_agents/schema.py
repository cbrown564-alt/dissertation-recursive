from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceSpan:
    text: str
    start: int | None = None
    end: int | None = None
    source: str = "letter"


@dataclass(frozen=True)
class Prediction:
    label: str
    evidence: list[EvidenceSpan] = field(default_factory=list)
    confidence: float = 0.0
    analysis: str = ""
    parsed_monthly_rate: float | None = None
    pragmatic_class: str | None = None
    purist_class: str | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GoldRecord:
    source_row_index: int
    letter: str
    gold_label: str
    gold_evidence: str
    row_ok: bool
    raw: dict[str, Any]
