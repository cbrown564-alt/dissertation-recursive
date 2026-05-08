"""Locked M-C3 broader-field subset and evaluation rules."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any


MC3_LOCKED_DECISION: dict[str, Any] = {
    "version": "2026-04-28",
    "phase": "M-C3",
    "adjudicationSource": {
        "runId": "20260427T062644Z_h008_single_broad_field_llm_n50",
        "scoringPath": "docs/adjudication/h008_tier1a_adjudication_25rows_scoring.csv",
        "sampleSize": 25,
    },
    "comparisonSubset": {
        "scoredFields": ["current_medications", "investigations"],
        "shadowFields": ["seizure_types"],
        "anchorFieldHandledElsewhere": ["seizure_frequency"],
        "contractCoreFields": [
            "seizure_frequency",
            "current_medications",
            "seizure_types",
            "investigations",
            "epilepsy_type",
            "epilepsy_syndrome",
        ],
    },
    "fieldDecisions": {
        "current_medications": {
            "status": "include",
            "rationale": (
                "Best adjudicated Tier 1a field. Values were correct for 56/56 items, "
                "status for 55/56, and evidence was exact-span for 54/56."
            ),
            "scoringDimensions": [
                "value_correct",
                "status_correct",
                "evidence_supported",
            ],
            "normalizationPolicy": {
                "drug_name": "lexical_normalization_allowed",
                "dose_text": "preserve_surface_form",
                "status_labels": ["current", "previous", "planned", "uncertain"],
            },
            "acceptanceRule": (
                "A medication counts as supported only when the value is correct, the "
                "status is correct, and the evidence grade is exact_span or overlapping_span."
            ),
        },
        "investigations": {
            "status": "include",
            "rationale": (
                "Useful but not yet clean. Errors cluster around result/status handling, "
                "especially non-diagnostic EEGs mapped to normal and broad other buckets."
            ),
            "scoringDimensions": [
                "value_correct",
                "status_correct",
                "normalization_correct",
                "evidence_supported",
            ],
            "normalizationPolicy": {
                "investigation_type_labels": ["EEG", "MRI", "CT", "genetic_test", "video_EEG", "other"],
                "result_labels": ["normal", "abnormal", "non_diagnostic", "pending", "not_stated"],
                "status_labels": ["completed", "planned", "historical", "uncertain"],
                "specialRules": [
                    "Do not collapse non-diagnostic EEG language into normal.",
                    "Use planned when the test is ordered but not yet performed.",
                    "Use pending when the test is done but the result is not yet known.",
                    "Use not_stated when the investigation is mentioned without an interpretable result.",
                ],
            },
            "acceptanceRule": (
                "An investigation counts as supported only when value/status are correct, "
                "result normalization is correct, and the evidence grade is exact_span or overlapping_span."
            ),
        },
        "seizure_types": {
            "status": "core_field_excluded_from_locked_aggregate",
            "rationale": (
                "Seizure type is part of the canonical evaluation contract, but the first locked "
                "M-C3 aggregate excludes it because clean normalization is too inconsistent. The "
                "prompt often emits diagnoses, triggers, or postictal features instead of "
                "normalized seizure types."
            ),
            "nextRepresentation": "seizure_type_mentions",
            "interimPolicy": (
                "Keep seizure-type outputs in every broader-field artifact and score them in "
                "matched adjudication tables, but do not include them in the first locked M-C3 "
                "aggregate until the representation is narrowed."
            ),
        },
        "seizure_frequency": {
            "status": "anchor_task_elsewhere",
            "rationale": (
                "Joint-prompt broader-field extraction weakens seizure-frequency output. Phase B "
                "h003/h004/h006/h007 remain the canonical anchor-task comparison set."
            ),
            "interimPolicy": (
                "Report h008 seizure frequency as a tradeoff/failure mode, not as the Phase C score target."
            ),
        },
    },
    "evidencePolicy": {
        "supportedGrades": ["exact_span", "overlapping_span"],
        "separateReportingOnly": ["section_level"],
        "unsupportedGrades": ["wrong_temporal_status", "unsupported", "missing_evidence"],
    },
    "nextImplementationStep": (
        "Use h008 as the default broader-field generation harness for M-C3 prompt/schema iterations, "
        "score only current_medications and investigations in the locked comparison, and keep seizure "
        "types as an unscored shadow field until a narrower taxonomy is implemented."
    ),
}


def scored_field_keys() -> list[str]:
    """Return the locked list of scored broader fields for M-C3."""
    subset = MC3_LOCKED_DECISION["comparisonSubset"]
    return list(subset["scoredFields"])


def shadow_field_keys() -> list[str]:
    """Return broader fields kept visible but excluded from the first M-C3 score."""
    subset = MC3_LOCKED_DECISION["comparisonSubset"]
    return list(subset["shadowFields"])


def score_adjudication_csv(path: str | Path) -> dict[str, Any]:
    """Score a completed M-C3 adjudication worksheet under the locked policy.

    The scorer deliberately uses the human adjudication columns rather than raw
    model evidence text. It can therefore be safely reported in project-state
    artifacts without introducing real-text leakage risks.
    """
    rows = _load_scoring_rows(path)
    return score_adjudication_rows(rows)


def score_adjudication_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Score adjudication rows under the locked M-C3 field policy."""
    scored_fields = scored_field_keys()
    shadow_fields = shadow_field_keys()
    fields = {
        field: _score_field([row for row in rows if row.get("field") == field], field)
        for field in scored_fields
    }
    shadow = {
        field: _shadow_field_summary([row for row in rows if row.get("field") == field])
        for field in shadow_fields
    }
    overall_total = sum(field["totalItems"] for field in fields.values())
    overall_supported = sum(field["lockedSupportedItems"] for field in fields.values())
    overall_value_correct = sum(field["valueCorrect"] for field in fields.values())
    overall_status_correct = sum(field["statusCorrect"] for field in fields.values())
    overall_normalization_correct = sum(field["normalizationCorrect"] for field in fields.values())
    source_rows = {
        _to_int(row.get("source_row_index"))
        for row in rows
        if row.get("source_row_index")
    }
    source_rows.discard(None)
    return {
        "version": MC3_LOCKED_DECISION["version"],
        "phase": MC3_LOCKED_DECISION["phase"],
        "scoredFields": scored_fields,
        "shadowFields": shadow_fields,
        "sourceRowCount": len(source_rows),
        "totalScoredItems": overall_total,
        "overall": {
            "valueAccuracy": _rate(overall_value_correct, overall_total),
            "statusAccuracy": _rate(overall_status_correct, overall_total),
            "normalizationAccuracy": _rate(overall_normalization_correct, overall_total),
            "lockedEvidenceSupportRate": _rate(overall_supported, overall_total),
            "lockedSupportedItems": overall_supported,
        },
        "fields": fields,
        "shadow": shadow,
    }


def _load_scoring_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _score_field(rows: list[dict[str, str]], field: str) -> dict[str, Any]:
    total = len(rows)
    value_correct = sum(_is_yes(row.get("value_correct")) for row in rows)
    status_correct = sum(_is_yes(row.get("status_correct")) for row in rows)
    normalization_correct = sum(_is_yes(row.get("normalization_correct")) for row in rows)
    partial_value = sum(_is_partial(row.get("value_correct")) for row in rows)
    partial_normalization = sum(_is_partial(row.get("normalization_correct")) for row in rows)
    supported = sum(_locked_supported(row, field) for row in rows)
    grade_counts = Counter(row.get("evidence_grade", "") or "blank" for row in rows)
    return {
        "totalItems": total,
        "valueCorrect": value_correct,
        "valuePartial": partial_value,
        "valueAccuracy": _rate(value_correct, total),
        "valueCorrectOrPartialRate": _rate(value_correct + partial_value, total),
        "statusCorrect": status_correct,
        "statusAccuracy": _rate(status_correct, total),
        "normalizationCorrect": normalization_correct,
        "normalizationPartial": partial_normalization,
        "normalizationAccuracy": _rate(normalization_correct, total),
        "normalizationCorrectOrPartialRate": _rate(normalization_correct + partial_normalization, total),
        "lockedSupportedItems": supported,
        "lockedEvidenceSupportRate": _rate(supported, total),
        "evidenceGradeCounts": dict(sorted(grade_counts.items())),
        "acceptanceRule": MC3_LOCKED_DECISION["fieldDecisions"][field]["acceptanceRule"],
    }


def _shadow_field_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    total = len(rows)
    value_correct = sum(_is_yes(row.get("value_correct")) for row in rows)
    partial_value = sum(_is_partial(row.get("value_correct")) for row in rows)
    normalization_correct = sum(_is_yes(row.get("normalization_correct")) for row in rows)
    return {
        "totalItems": total,
        "valueAccuracy": _rate(value_correct, total),
        "valueCorrectOrPartialRate": _rate(value_correct + partial_value, total),
        "normalizationAccuracy": _rate(normalization_correct, total),
        "scored": False,
    }


def _locked_supported(row: dict[str, str], field: str) -> bool:
    grade = (row.get("evidence_grade") or "").strip()
    if grade not in MC3_LOCKED_DECISION["evidencePolicy"]["supportedGrades"]:
        return False
    if not (_is_yes(row.get("value_correct")) and _is_yes(row.get("status_correct"))):
        return False
    if field == "investigations" and not _is_yes(row.get("normalization_correct")):
        return False
    return True


def _is_yes(value: str | None) -> bool:
    return (value or "").strip().upper() == "Y"


def _is_partial(value: str | None) -> bool:
    return (value or "").strip().upper() == "P"


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 3)


def _to_int(value: str | None) -> int | None:
    try:
        return int(value or "")
    except ValueError:
        return None
