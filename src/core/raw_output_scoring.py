"""Direct scoring for parsed raw model payloads before canonical projection."""

from __future__ import annotations

from typing import Any

from normalization import (
    benchmark_epilepsy_label,
    benchmark_seizure_type_label,
    canonical_diagnosis,
    canonical_investigation_result,
    canonical_medication_name,
    canonical_seizure_type,
    frequency_loose_match,
    normalize_dose,
    normalize_frequency,
    normalize_unit,
    normalize_value,
    parse_frequency_expression,
)

from .projection import first_value
from .projection_diagnostics import (
    _raw_diagnosis_values,
    _raw_frequency_values,
    _raw_investigation_values,
    _raw_medication_values,
    _raw_seizure_values,
)
from .scoring import GoldDocument, gold_frequency_part_candidates, set_prf


def _raw_medication_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_meds = payload.get("medications")
    if isinstance(raw_meds, list):
        result: list[dict[str, Any]] = []
        for item in raw_meds:
            if isinstance(item, dict):
                result.append(
                    {
                        "name": item.get("name") or item.get("medication_name"),
                        "dose": item.get("dose"),
                        "dose_unit": item.get("dose_unit") or item.get("unit"),
                        "frequency": item.get("frequency"),
                    }
                )
            else:
                result.append({"name": first_value(item), "dose": None, "dose_unit": None, "frequency": None})
        return result
    return [{"name": value, "dose": None, "dose_unit": None, "frequency": None} for value in _raw_medication_values(payload)]


def _medication_tuple(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        canonical_medication_name(item.get("name")),
        normalize_dose(item.get("dose")),
        normalize_unit(item.get("dose_unit")),
        normalize_frequency(item.get("frequency")),
    )


def _medication_name_tuple(item: dict[str, Any]) -> tuple[str]:
    return (canonical_medication_name(item.get("name")),)


def _medication_component_tuple(item: dict[str, Any], component: str) -> tuple[str, str]:
    name = canonical_medication_name(item.get("name"))
    if component == "dose":
        value = normalize_dose(item.get(component))
    elif component == "dose_unit":
        value = normalize_unit(item.get(component))
    elif component == "frequency":
        value = normalize_frequency(item.get(component))
    else:
        value = normalize_value(item.get(component))
    return (name, value)


def score_raw_payload(document_id: str, payload: dict[str, Any], document_gold: GoldDocument) -> dict[str, Any]:
    """Score fields that can be read directly from a raw model payload.

    This intentionally does not validate against the canonical schema and does
    not run deterministic projection. Metrics here are therefore a conservative
    audit surface for direct model output, not a replacement for canonical
    projected scores.
    """

    medication_items = _raw_medication_items(payload)
    predicted_med_names = {
        _medication_name_tuple(item) for item in medication_items if _medication_name_tuple(item)[0]
    }
    gold_med_names = {
        _medication_name_tuple(item) for item in document_gold.medications if _medication_name_tuple(item)[0]
    }
    predicted_medications = {
        _medication_tuple(item)
        for item in medication_items
        if _medication_tuple(item)[0] and any(_medication_tuple(item)[1:])
    }
    gold_medications = {
        _medication_tuple(item)
        for item in document_gold.medications
        if _medication_tuple(item)[0] and any(_medication_tuple(item)[1:])
    }
    field_scores: dict[str, Any] = {
        "medication_name": set_prf(predicted_med_names, gold_med_names),
        "medication_full": set_prf(predicted_medications, gold_medications),
    }
    field_label_sets: dict[str, dict[str, list[str]]] = {
        "medication_name": {
            "predicted": [" | ".join(item) for item in sorted(predicted_med_names)],
            "gold": [" | ".join(item) for item in sorted(gold_med_names)],
        },
        "medication_full": {
            "predicted": [" | ".join(item) for item in sorted(predicted_medications)],
            "gold": [" | ".join(item) for item in sorted(gold_medications)],
        },
    }
    for component in ["dose", "dose_unit", "frequency"]:
        predicted_component = {
            _medication_component_tuple(item, component)
            for item in medication_items
            if _medication_component_tuple(item, component)[0] and _medication_component_tuple(item, component)[1]
        }
        gold_component = {
            _medication_component_tuple(item, component)
            for item in document_gold.medications
            if _medication_component_tuple(item, component)[0] and _medication_component_tuple(item, component)[1]
        }
        metric_name = f"medication_{component}"
        field_scores[metric_name] = set_prf(predicted_component, gold_component)
        field_label_sets[metric_name] = {
            "predicted": [" | ".join(item) for item in sorted(predicted_component)],
            "gold": [" | ".join(item) for item in sorted(gold_component)],
        }

    predicted_types = {
        (canonical_seizure_type(value),) for value in _raw_seizure_values(payload) if canonical_seizure_type(value)
    }
    gold_types = {(item,) for item in set(document_gold.seizure_types) if item}
    field_scores["seizure_type"] = set_prf(predicted_types, gold_types)
    field_label_sets["seizure_type"] = {
        "predicted": [" | ".join(item) for item in sorted(predicted_types)],
        "gold": [" | ".join(item) for item in sorted(gold_types)],
    }

    predicted_types_collapsed = {
        (benchmark_seizure_type_label(value[0]),) for value in predicted_types if benchmark_seizure_type_label(value[0])
    }
    gold_types_collapsed = {
        (benchmark_seizure_type_label(item),) for item in document_gold.seizure_types if benchmark_seizure_type_label(item)
    }
    field_scores["seizure_type_collapsed"] = set_prf(predicted_types_collapsed, gold_types_collapsed)
    field_label_sets["seizure_type_collapsed"] = {
        "predicted": [" | ".join(item) for item in sorted(predicted_types_collapsed)],
        "gold": [" | ".join(item) for item in sorted(gold_types_collapsed)],
    }

    raw_frequency = normalize_value(first_value(_raw_frequency_values(payload)))
    predicted_frequency_parts = parse_frequency_expression(raw_frequency)
    gold_frequency_parts = gold_frequency_part_candidates(document_gold)
    field_scores["current_seizure_frequency_per_letter"] = {
        "correct": any(frequency_loose_match(predicted_frequency_parts, item) for item in gold_frequency_parts),
        "predicted": predicted_frequency_parts,
        "gold_values": gold_frequency_parts,
    }

    for field_name in ["eeg", "mri"]:
        predicted = canonical_investigation_result(first_value(_raw_investigation_values(payload, field_name)))
        gold = document_gold.investigations.get(field_name)
        field_scores[field_name] = {
            "correct": (predicted == gold) if gold else predicted in {"", "not stated", "none"},
            "predicted": predicted,
            "gold": gold,
        }

    raw_diagnosis = canonical_diagnosis(first_value(_raw_diagnosis_values(payload)))
    field_scores["epilepsy_diagnosis"] = {
        "correct": any(raw_diagnosis and (raw_diagnosis in gold or gold in raw_diagnosis) for gold in document_gold.diagnoses),
        "predicted": raw_diagnosis,
        "gold_values": sorted(set(document_gold.diagnoses)),
    }
    predicted_dx_collapsed = benchmark_epilepsy_label(raw_diagnosis)
    gold_dx_collapsed = {benchmark_epilepsy_label(d) for d in document_gold.diagnoses if benchmark_epilepsy_label(d)}
    field_scores["epilepsy_diagnosis_collapsed"] = {
        "correct": bool(predicted_dx_collapsed and predicted_dx_collapsed in gold_dx_collapsed),
        "predicted": predicted_dx_collapsed,
        "gold_values": sorted(gold_dx_collapsed),
    }

    return {
        "document_id": document_id,
        "available": True,
        "schema_valid": False,
        "field_scores": field_scores,
        "field_label_sets": field_label_sets,
        "raw_counts": {
            "medication": len(_raw_medication_values(payload)),
            "seizure_type": len(_raw_seizure_values(payload)),
            "epilepsy_diagnosis": len(_raw_diagnosis_values(payload)),
            "current_seizure_frequency": len(_raw_frequency_values(payload)),
            "eeg": len(_raw_investigation_values(payload, "eeg")),
            "mri": len(_raw_investigation_values(payload, "mri")),
        },
    }


def flatten_raw_summary(system: str, document_scores: list[dict[str, Any]]) -> dict[str, Any]:
    available = [score for score in document_scores if score.get("available")]
    if not available:
        return {"system": system, "documents_expected": len(document_scores), "documents_available": 0}

    prf_metric_names = [
        "medication_name",
        "medication_dose",
        "medication_dose_unit",
        "medication_frequency",
        "medication_full",
        "seizure_type",
        "seizure_type_collapsed",
    ]
    prf_metrics: dict[str, dict[str, float | int]] = {}
    for metric in prf_metric_names:
        totals = {"tp": 0, "fp": 0, "fn": 0}
        for score in available:
            metric_score = score.get("field_scores", {}).get(metric, {})
            for key in totals:
                totals[key] += int(metric_score.get(key, 0))
        tp, fp, fn = totals["tp"], totals["fp"], totals["fn"]
        precision = tp / (tp + fp) if tp + fp else 1.0 if fn == 0 else 0.0
        recall = tp / (tp + fn) if tp + fn else 1.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        prf_metrics[metric] = {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}

    def accuracy(metric: str) -> float | None:
        values = [
            score.get("field_scores", {}).get(metric, {}).get("correct")
            for score in available
            if metric in score.get("field_scores", {})
        ]
        return sum(1 for item in values if item) / len(values) if values else None

    raw_counts: dict[str, int] = {}
    for score in available:
        for key, value in (score.get("raw_counts") or {}).items():
            raw_counts[key] = raw_counts.get(key, 0) + int(value or 0)

    return {
        "system": system,
        "documents_expected": len(document_scores),
        "documents_available": len(available),
        "raw_schema_valid_rate": 0.0,
        "medication_name_f1": prf_metrics["medication_name"]["f1"],
        "medication_dose_f1": prf_metrics["medication_dose"]["f1"],
        "medication_dose_unit_f1": prf_metrics["medication_dose_unit"]["f1"],
        "medication_frequency_f1": prf_metrics["medication_frequency"]["f1"],
        "medication_full_f1": prf_metrics["medication_full"]["f1"],
        "seizure_type_f1": prf_metrics["seizure_type"]["f1"],
        "seizure_type_f1_collapsed": prf_metrics["seizure_type_collapsed"]["f1"],
        "current_seizure_frequency_per_letter_accuracy": accuracy("current_seizure_frequency_per_letter"),
        "eeg_accuracy": accuracy("eeg"),
        "mri_accuracy": accuracy("mri"),
        "epilepsy_diagnosis_accuracy": accuracy("epilepsy_diagnosis"),
        "epilepsy_diagnosis_accuracy_collapsed": accuracy("epilepsy_diagnosis_collapsed"),
        **{f"raw_{key}_count": value for key, value in sorted(raw_counts.items())},
    }
