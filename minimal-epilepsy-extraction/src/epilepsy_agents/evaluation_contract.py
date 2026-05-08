"""Canonical field-evaluation contract for broader epilepsy extraction.

The project began with seizure-frequency-only harnesses, then expanded into a
broader clinical extraction task. This module keeps the final evaluation
vocabulary explicit so parser validity, field coverage, support checks, and
human adjudication are not collapsed into one seizure-frequency-era flag.
"""

from __future__ import annotations

from typing import Any


EVALUATION_CONTRACT_VERSION = "2026-05-01"


FIELD_CONTRACT: dict[str, dict[str, Any]] = {
    "epilepsy_classification": {
        "status": "core",
        "source": "Ten_example_Annotation.xlsx + production schema",
        "artifact_keys": ["epilepsy_type", "epilepsy_syndrome"],
        "evaluation": ["parse_validity", "value_correct", "normalization_correct", "evidence_support"],
    },
    "seizure_classification": {
        "status": "core",
        "source": "Ten_example_Annotation.xlsx + broader seizure_types field",
        "artifact_keys": ["seizure_types"],
        "evaluation": ["parse_validity", "value_correct", "normalization_correct", "evidence_support"],
    },
    "current_epilepsy_medication": {
        "status": "core",
        "source": "Ten_example_Annotation.xlsx + M-C3",
        "artifact_keys": ["current_medications"],
        "evaluation": ["parse_validity", "value_correct", "status_correct", "evidence_support"],
    },
    "investigations": {
        "status": "core",
        "source": "M-C3 clinical-rubric extension",
        "artifact_keys": ["investigations"],
        "evaluation": [
            "parse_validity",
            "value_correct",
            "status_correct",
            "normalization_correct",
            "evidence_support",
        ],
    },
    "seizure_frequency": {
        "status": "core_anchor",
        "source": "synthetic gold labels + Ten_example_Annotation.xlsx",
        "artifact_keys": ["seizure_frequency"],
        "evaluation": ["parse_validity", "exact_label", "monthly_tolerance", "class_f1", "evidence_support"],
    },
    "seizure_freedom": {
        "status": "core_future",
        "source": "Ten_example_Annotation.xlsx",
        "artifact_keys": [],
        "evaluation": ["value_correct", "temporal_bucket_correct", "evidence_support"],
    },
    "most_recent_seizure": {
        "status": "core_future",
        "source": "Ten_example_Annotation.xlsx",
        "artifact_keys": [],
        "evaluation": ["value_correct", "temporal_bucket_correct", "evidence_support"],
    },
    "rescue_medication": {
        "status": "core_future",
        "source": "Ten_example_Annotation.xlsx",
        "artifact_keys": [],
        "evaluation": ["value_correct", "status_correct", "evidence_support"],
    },
    "other_therapies": {
        "status": "core_future",
        "source": "Ten_example_Annotation.xlsx",
        "artifact_keys": [],
        "evaluation": ["value_correct", "status_correct", "evidence_support"],
    },
    "comorbidities": {
        "status": "core_future",
        "source": "Ten_example_Annotation.xlsx",
        "artifact_keys": [],
        "evaluation": ["value_correct", "evidence_support"],
    },
    "associated_symptoms": {
        "status": "core_future",
        "source": "Ten_example_Annotation.xlsx",
        "artifact_keys": [],
        "evaluation": ["value_correct", "evidence_support"],
    },
}


def build_row_validity(result: dict[str, Any]) -> dict[str, Any]:
    """Return component validity flags for one normalized pipeline result.

    ``invalid_output`` is retained as a legacy all-core flag, but downstream
    reporting should use the component rates below.
    """
    metadata = result.get("metadata", {})
    calls = metadata.get("calls") if isinstance(metadata.get("calls"), dict) else metadata

    sf_invalid = _call_invalid(calls.get("sf_call") if isinstance(calls, dict) else None)
    if sf_invalid is None:
        sf_invalid = bool(result.get("invalid_output", False)) and not _has_broader_payload(result)

    broader_invalid = _call_invalid(calls.get("broader_call") if isinstance(calls, dict) else None)
    if broader_invalid is None:
        broader_invalid = bool(result.get("invalid_output", False)) and not _has_broader_payload(result)

    classification_call = calls.get("classification_call") if isinstance(calls, dict) else None
    classification_invalid = _call_invalid(classification_call)
    classification_present = bool(result.get("epilepsy_type") or result.get("epilepsy_syndrome"))
    if classification_invalid is None and isinstance(calls, dict) and "optional_invalid_output" in calls:
        classification_invalid = bool(calls["optional_invalid_output"])

    current_medications_invalid = bool(broader_invalid)
    seizure_types_invalid = bool(broader_invalid)
    investigations_invalid = bool(broader_invalid)
    epilepsy_classification_invalid = (
        bool(classification_invalid) if classification_invalid is not None else None
    )

    implemented_core = {
        "seizure_frequency": True,
        "current_epilepsy_medication": True,
        "seizure_classification": True,
        "investigations": True,
        "epilepsy_classification": classification_present or classification_invalid is not None,
    }
    implemented_count = sum(1 for value in implemented_core.values() if value)

    return {
        "contract_version": EVALUATION_CONTRACT_VERSION,
        "legacy_invalid_output": bool(result.get("invalid_output", False)),
        "component_invalid": {
            "seizure_frequency": bool(sf_invalid),
            "current_epilepsy_medication": current_medications_invalid,
            "seizure_classification": seizure_types_invalid,
            "investigations": investigations_invalid,
            "epilepsy_classification": epilepsy_classification_invalid,
        },
        "field_implemented": implemented_core,
        "implemented_core_field_count": implemented_count,
        "implemented_core_field_rate": round(implemented_count / len(implemented_core), 3),
        "broader_fields_invalid": any(
            [current_medications_invalid, seizure_types_invalid, investigations_invalid]
        ),
        "full_contract_invalid": any(
            value is True
            for value in [
                sf_invalid,
                current_medications_invalid,
                seizure_types_invalid,
                investigations_invalid,
                epilepsy_classification_invalid,
            ]
        ),
        "notes": _validity_notes(implemented_core),
    }


def summarize_validity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize component validity for broader-run artifacts."""
    n = len(rows)
    if not n:
        return {"contract_version": EVALUATION_CONTRACT_VERSION, "n": 0}

    validities = [row.get("validity", {}) for row in rows]
    component_keys = [
        "seizure_frequency",
        "current_epilepsy_medication",
        "seizure_classification",
        "investigations",
        "epilepsy_classification",
    ]
    component_rates = {
        key: _nullable_rate(
            [row.get("component_invalid", {}).get(key) for row in validities]
        )
        for key in component_keys
    }
    implemented_rates = {
        key: _rate(
            sum(1 for row in validities if row.get("field_implemented", {}).get(key)),
            n,
        )
        for key in component_keys
    }
    return {
        "contract_version": EVALUATION_CONTRACT_VERSION,
        "n": n,
        "legacy_any_invalid_output_rate": _rate(
            sum(1 for row in validities if row.get("legacy_invalid_output")), n
        ),
        "full_contract_invalid_output_rate": _rate(
            sum(1 for row in validities if row.get("full_contract_invalid")), n
        ),
        "broader_fields_invalid_output_rate": _rate(
            sum(1 for row in validities if row.get("broader_fields_invalid")), n
        ),
        "component_invalid_output_rates": component_rates,
        "field_implementation_rates": implemented_rates,
        "mean_implemented_core_field_rate": round(
            sum(float(row.get("implemented_core_field_rate", 0.0)) for row in validities) / n,
            3,
        ),
    }


def _call_invalid(call: Any) -> bool | None:
    if not isinstance(call, dict):
        return None
    if "invalid_output" in call:
        return bool(call["invalid_output"])
    if call.get("error_type"):
        return True
    failed_call = call.get("failed_call")
    if isinstance(failed_call, dict) and failed_call.get("invalid_output") and not call.get("fallback_used"):
        return True
    return False


def _has_broader_payload(result: dict[str, Any]) -> bool:
    return any(
        key in result
        for key in ("current_medications", "seizure_types", "investigations")
    )


def _nullable_rate(values: list[Any]) -> float | None:
    applicable = [bool(value) for value in values if value is not None]
    if not applicable:
        return None
    return _rate(sum(applicable), len(applicable))


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def _validity_notes(implemented_core: dict[str, bool]) -> list[str]:
    notes = []
    missing = [field for field, implemented in implemented_core.items() if not implemented]
    if missing:
        notes.append("not_emitted_by_harness:" + ",".join(missing))
    return notes
