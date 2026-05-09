from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from .contracts import SCHEMA_VERSION, SupportAssessment, empty_field_coverage


FINAL_EXTRACTION_REQUIRED_KEYS: tuple[str, ...] = (
    "seizure_frequency",
    "current_medications",
    "investigations",
    "seizure_types",
    "seizure_features",
    "seizure_pattern_modifiers",
    "epilepsy_type",
    "epilepsy_syndrome",
    "citations",
    "confidence",
    "warnings",
)


@dataclass(frozen=True)
class EvidenceSpan:
    quote: str
    section: str | None = None
    span_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None


@dataclass(frozen=True)
class Prediction:
    label: str
    evidence: list[EvidenceSpan] = field(default_factory=list)
    confidence: float = 0.0
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

    @property
    def row_id(self) -> str:
        return str(self.source_row_index)


@dataclass(frozen=True)
class ExtractedItem:
    value: str
    normalized_value: str | None = None
    status: str | None = None
    evidence: EvidenceSpan | None = None
    confidence: float = 0.0
    support: SupportAssessment | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FinalExtraction:
    seizure_frequency: dict[str, Any] = field(default_factory=dict)
    current_medications: list[dict[str, Any]] = field(default_factory=list)
    investigations: list[dict[str, Any]] = field(default_factory=list)
    seizure_types: list[dict[str, Any]] = field(default_factory=list)
    seizure_features: list[dict[str, Any]] = field(default_factory=list)
    seizure_pattern_modifiers: list[dict[str, Any]] = field(default_factory=list)
    epilepsy_type: dict[str, Any] | None = None
    epilepsy_syndrome: dict[str, Any] | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    confidence: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExtractionPayload:
    pipeline_id: str
    final: FinalExtraction
    schema_version: str = SCHEMA_VERSION
    field_coverage: dict[str, str] = field(default_factory=empty_field_coverage)
    artifacts: dict[str, Any] = field(default_factory=dict)
    invalid_output: bool = False
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        validate_final_payload_keys(self.final)
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def missing_final_payload_keys(final: FinalExtraction | Mapping[str, Any]) -> list[str]:
    if isinstance(final, FinalExtraction):
        keys = final.to_dict().keys()
    else:
        keys = final.keys()
    return [key for key in FINAL_EXTRACTION_REQUIRED_KEYS if key not in keys]


def validate_final_payload_keys(final: FinalExtraction | Mapping[str, Any]) -> None:
    missing = missing_final_payload_keys(final)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Final extraction payload missing required keys: {joined}")


def write_extraction_payload(payload: ExtractionPayload, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload.to_json(), encoding="utf-8")
    return output_path


def read_extraction_payload(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_final_payload_keys(data["final"])
    return data
