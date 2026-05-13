"""Diagnostics that make deterministic projection effects explicit."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .projection import first_value, value_list


def _projected_medications(canonical: dict[str, Any]) -> list[dict[str, Any]]:
    fields = canonical.get("fields") if isinstance(canonical, dict) else {}
    meds = fields.get("current_anti_seizure_medications") if isinstance(fields, dict) else []
    return [item for item in meds if isinstance(item, dict)]


def _projected_scalar_values(canonical: dict[str, Any], field_name: str) -> list[str]:
    fields = canonical.get("fields") if isinstance(canonical, dict) else {}
    raw = fields.get(field_name) if isinstance(fields, dict) else None
    if isinstance(raw, list):
        return [str(item.get("value")) for item in raw if isinstance(item, dict) and item.get("value")]
    if isinstance(raw, dict) and raw.get("value"):
        return [str(raw["value"])]
    return []


def _raw_medication_values(payload: dict[str, Any]) -> list[str]:
    raw_meds = payload.get("medications")
    if isinstance(raw_meds, list):
        values = []
        for item in raw_meds:
            if isinstance(item, dict) and item.get("name"):
                values.append(str(item["name"]))
            else:
                value = first_value(item)
                if value:
                    values.append(value)
        return values
    return value_list(
        payload.get("medication_names")
        or payload.get("current_anti_seizure_medications")
        or payload.get("current anti-seizure medications")
    )


def _raw_seizure_values(payload: dict[str, Any]) -> list[str]:
    values = value_list(payload.get("seizure_types") or payload.get("seizure_type"))
    for mapping_key in ["verified_seizure_type_mappings", "seizure_type_mappings"]:
        mappings = payload.get(mapping_key)
        if not isinstance(mappings, list):
            continue
        for mapping in mappings:
            if not isinstance(mapping, dict) or mapping.get("keep") is False:
                continue
            value = mapping.get("benchmark_label") or mapping.get("label") or mapping.get("fact")
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
    return _dedupe(values)


def _raw_diagnosis_values(payload: dict[str, Any]) -> list[str]:
    value = first_value(
        payload.get("epilepsy_types")
        or payload.get("epilepsy_diagnosis")
        or payload.get("epilepsy_diagnosis_type")
        or payload.get("epilepsy diagnosis/type")
    )
    return [value] if value else []


def _raw_frequency_values(payload: dict[str, Any]) -> list[str]:
    value = first_value(payload.get("seizure_frequency") or payload.get("current_seizure_frequency"))
    return [value] if value else []


def _raw_investigation_values(payload: dict[str, Any], key: str) -> list[str]:
    investigations = payload.get("investigations")
    if isinstance(investigations, dict):
        value = first_value(investigations.get(key) or payload.get(key) or payload.get(key.upper() + "_result"))
    else:
        value = first_value(payload.get(key) or payload.get(key.upper() + "_result"))
    return [value] if value else []


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _evidence_count(value: Any) -> int:
    if isinstance(value, dict):
        evidence = value.get("evidence")
        count = len(evidence) if isinstance(evidence, list) else 0
        return count + sum(_evidence_count(child) for child in value.values() if child is not evidence)
    if isinstance(value, list):
        return sum(_evidence_count(item) for item in value)
    return 0


def _quote_count(value: Any) -> int:
    if isinstance(value, dict):
        count = 0
        for key in ["quote", "support", "evidence", "source_quote"]:
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                count += 1
        return count + sum(_quote_count(child) for child in value.values())
    if isinstance(value, list):
        return sum(_quote_count(item) for item in value)
    return 0


def projection_delta_row(
    document_id: str,
    harness_id: str,
    model_label: str,
    payload: dict[str, Any],
    canonical: dict[str, Any],
) -> dict[str, Any]:
    """Summarize how raw parsed payload values changed under projection."""
    raw_meds = _raw_medication_values(payload)
    projected_meds = [str(item["name"]) for item in _projected_medications(canonical) if item.get("name")]
    raw_seizures = _raw_seizure_values(payload)
    projected_seizures = _projected_scalar_values(canonical, "seizure_types")
    raw_dx = _raw_diagnosis_values(payload)
    projected_dx = _projected_scalar_values(canonical, "epilepsy_diagnosis")
    raw_frequency = _raw_frequency_values(payload)
    projected_frequency = _projected_scalar_values(canonical, "current_seizure_frequency")
    raw_eeg = _raw_investigation_values(payload, "eeg")
    raw_mri = _raw_investigation_values(payload, "mri")
    fields = canonical.get("fields") if isinstance(canonical, dict) else {}
    projected_eeg = [fields.get("eeg", {}).get("result")] if isinstance(fields.get("eeg"), dict) else []
    projected_mri = [fields.get("mri", {}).get("result")] if isinstance(fields.get("mri"), dict) else []
    projected_eeg = [str(value) for value in projected_eeg if value and value != "not_stated"]
    projected_mri = [str(value) for value in projected_mri if value and value != "not_stated"]

    raw_total = len(raw_meds) + len(raw_seizures) + len(raw_dx) + len(raw_frequency) + len(raw_eeg) + len(raw_mri)
    projected_total = (
        len(projected_meds)
        + len(projected_seizures)
        + len(projected_dx)
        + len(projected_frequency)
        + len(projected_eeg)
        + len(projected_mri)
    )
    projected_fields = canonical.get("fields", {})
    force_current_count = len(projected_meds) + len(projected_seizures)
    if projected_frequency:
        force_current_count += 1

    return {
        "document_id": document_id,
        "model_label": model_label,
        "harness_id": harness_id,
        "raw_medication_count": len(raw_meds),
        "projected_medication_count": len(projected_meds),
        "raw_seizure_type_count": len(raw_seizures),
        "projected_seizure_type_count": len(projected_seizures),
        "raw_epilepsy_diagnosis_count": len(raw_dx),
        "projected_epilepsy_diagnosis_count": len(projected_dx),
        "raw_frequency_count": len(raw_frequency),
        "projected_frequency_count": len(projected_frequency),
        "raw_eeg_count": len(raw_eeg),
        "projected_eeg_count": len(projected_eeg),
        "raw_mri_count": len(raw_mri),
        "projected_mri_count": len(projected_mri),
        "raw_total_field_count": raw_total,
        "projected_total_field_count": projected_total,
        "dropped_field_count": max(raw_total - projected_total, 0),
        "added_field_count": max(projected_total - raw_total, 0),
        "seizure_label_changed": raw_seizures != projected_seizures,
        "diagnosis_label_changed": raw_dx != projected_dx,
        "eeg_label_changed": raw_eeg != projected_eeg,
        "mri_label_changed": raw_mri != projected_mri,
        "raw_quote_count": _quote_count(payload),
        "projected_evidence_count": _evidence_count(projected_fields),
        "force_current_field_count": force_current_count,
        "projection_version": canonical.get("metadata", {}).get("projection"),
    }


def summarize_projection_deltas(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate projection delta rows for manifest/report output."""
    total = len(rows)
    if total == 0:
        return {"documents": 0}
    numeric_keys = [
        "dropped_field_count",
        "added_field_count",
        "raw_quote_count",
        "projected_evidence_count",
        "force_current_field_count",
    ]
    return {
        "documents": total,
        **{key: sum(int(row.get(key) or 0) for row in rows) for key in numeric_keys},
        "seizure_label_changed_documents": sum(1 for row in rows if row.get("seizure_label_changed")),
        "diagnosis_label_changed_documents": sum(1 for row in rows if row.get("diagnosis_label_changed")),
        "investigation_label_changed_documents": sum(
            1 for row in rows if row.get("eeg_label_changed") or row.get("mri_label_changed")
        ),
    }
