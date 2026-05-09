from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from epilepsy_extraction.schemas.contracts import FieldFamily
from epilepsy_extraction.schemas.extraction import FinalExtraction


@dataclass(frozen=True)
class AggregationResult:
    final: FinalExtraction
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    any_invalid: bool = False


_SHARED_KEYS = frozenset(
    {"citations", "confidence", "warnings", "status_annotation", "evidence_grade",
     "normalization_applied", "normalized_unit", "monthly_rate"}
)


def aggregate_field_results(
    field_results: dict[FieldFamily, dict[str, Any]],
) -> AggregationResult:
    """Merge per-family extraction results into a single FinalExtraction.

    Logs conflicts without resolving them through inference. Does not create
    new clinical claims from missing data.
    """
    merged: dict[str, Any] = {}
    citations: list[dict[str, Any]] = []
    confidence: dict[str, float] = {}
    warnings: list[str] = []
    conflicts: list[dict[str, Any]] = []
    any_invalid = False

    for family, data in field_results.items():
        if not data:
            any_invalid = True
            continue
        if isinstance(data.get("citations"), list):
            citations.extend(data["citations"])
        if isinstance(data.get("confidence"), dict):
            confidence.update(data["confidence"])
        if isinstance(data.get("warnings"), list):
            warnings.extend(str(w) for w in data["warnings"])
        for k, v in data.items():
            if k in _SHARED_KEYS:
                continue
            if v is None:
                continue
            if k in merged and merged[k] != v:
                conflicts.append({"field": k, "family": family.value, "existing": merged[k], "new": v})
            else:
                merged[k] = v

    return AggregationResult(
        final=FinalExtraction(
            seizure_frequency=merged.get("seizure_frequency", {}),
            current_medications=merged.get("current_medications", []),
            investigations=merged.get("investigations", []),
            seizure_types=merged.get("seizure_types", []),
            seizure_features=merged.get("seizure_features", []),
            seizure_pattern_modifiers=merged.get("seizure_pattern_modifiers", []),
            epilepsy_type=merged.get("epilepsy_type"),
            epilepsy_syndrome=merged.get("epilepsy_syndrome"),
            citations=citations,
            confidence=confidence,
            warnings=warnings,
        ),
        conflicts=conflicts,
        warnings=warnings,
        any_invalid=any_invalid,
    )
