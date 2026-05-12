"""Canonical projection helpers for promoted benchmark-style harness outputs."""

from __future__ import annotations

import re
from typing import Any

from normalization import canonical_investigation_result as _canonical_inv
from validate_extraction import normalize_text

RELAXED_PROJECTION_VERSION = "relaxed_v2_benchmark_seizure_labels_no_evidence"


def to_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def system_for_harness(harness_id: str) -> str:
    return {
        "H0_strict_canonical": "D0",
        "H2_task_specific": "D1",
        "H3_loose_answer_then_parse": "D2",
        "H4_provider_native_structured_output": "D4",
        "H6_benchmark_only_coarse_json": "D6",
        "H6fs_benchmark_only_coarse_json": "D6fs",
        "H6fs_ev_resolver": "D6fs",
        "H6full_benchmark_json": "D6full",
        "H7_extract_then_normalize": "D7",
        "H8_evidence_later": "D8",
        "D3_candidate_plus_verifier": "D3",
    }.get(harness_id, harness_id)


def first_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            result = first_value(item)
            if result:
                return result
        return None
    if isinstance(value, dict):
        for key in ["value", "name", "result", "text"]:
            result = first_value(value.get(key))
            if result:
                return result
        return None
    text = str(value).strip()
    if not text or text.lower() in {"not stated", "none", "null", "[]"}:
        return None
    return text


def split_compact_list(text: str) -> list[str]:
    cleaned = text.strip().strip("[]")
    if not cleaned or cleaned.lower() in {"not stated", "none", "null"}:
        return []
    parts = cleaned.split(";") if ";" in cleaned else [cleaned]
    return [part.strip(" -\t\n\r,") for part in parts if part.strip(" -\t\n\r,")]


def value_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if isinstance(item, str):
                items.extend(split_compact_list(item))
            else:
                nested = first_value(item)
                if nested:
                    items.append(nested)
        return [item for item in items if item and item.lower() not in {"not stated", "none", "null"}]
    if isinstance(value, dict):
        nested = first_value(value)
        return [nested] if nested else []
    return split_compact_list(str(value))


def benchmark_seizure_type(value: str | None) -> str | None:
    """Collapse relaxed seizure descriptions to the ExECT benchmark label space."""
    if not value:
        return None
    text = value.lower().replace("generalised", "generalized")
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9/ ]+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text, flags=re.IGNORECASE).strip()
    if not text or text in {"not stated", "none", "null"}:
        return None

    symptom_terms = [
        "aura",
        "warning",
        "unusual smell",
        "strange smell",
        "strange taste",
        "abdominal sensation",
        "epigastric",
    ]
    seizure_terms = ["seizure", "seizures", "fit", "fits", "convulsive", "convulsion"]
    if any(term in text for term in symptom_terms) and not any(term in text for term in seizure_terms):
        return None

    if any(term in text for term in ["dissociative", "nonepileptic", "non epileptic", "dizzy spell"]):
        return "unknown seizure type"
    if "secondary" in text and any(term in text for term in ["generalized", "convulsive", "tonic clonic"]):
        return "secondary generalized seizures"
    if "focal to bilateral" in text and "tonic clonic" in text:
        return "secondary generalized seizures"
    if "focal" in text or "partial" in text or "temporal" in text:
        return "focal seizure"
    if "complex partial" in text:
        return "focal seizure"
    if "tonic clonic" in text or "gtc" in text:
        return "generalized tonic clonic seizure"
    if "absence" in text:
        return "generalized absence seizure"
    if "myoclonic" in text:
        return "generalized myoclonic seizure"
    if "generalized seizure" in text or "generalized seizures" in text:
        return "generalized seizures"
    if text in {"seizure", "seizures", "fits"}:
        return "unknown seizure type"
    return value.strip()


def benchmark_seizure_types(values: list[str]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for value in values:
        label = benchmark_seizure_type(value)
        if label and label not in seen:
            labels.append(label)
            seen.add(label)
    return labels


def medication_from_text(text: str) -> dict[str, Any]:
    dose_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml)\b", text, flags=re.IGNORECASE)
    frequency_match = re.search(
        r"\b(once daily|twice daily|three times daily|four times daily|bd|od|tds|qds|daily|nocte)\b",
        text,
        flags=re.IGNORECASE,
    )
    name = text
    if dose_match:
        name = text[: dose_match.start()].strip(" ,-")
    name = name.split("(")[0].strip(" ,-")
    return {
        "name": name or text,
        "dose": dose_match.group(1) if dose_match else None,
        "dose_unit": dose_match.group(2) if dose_match else None,
        "frequency": frequency_match.group(1) if frequency_match else None,
        "status": "current",
        "missingness": "present",
        "temporality": "current",
        "evidence": [],
        "evidence_event_ids": [],
    }


def scalar_field(value: str | None, temporality: str = "current") -> dict[str, Any]:
    return {
        "value": value,
        "missingness": "present" if value else "not_stated",
        "temporality": temporality if value else "uncertain",
        "evidence": [] if value else None,
        "evidence_event_ids": [],
    }


def investigation_field(value: str | None) -> dict[str, Any]:
    normalized = _canonical_inv(value)
    result = normalized if normalized in {"normal", "abnormal", "uncertain"} else "not_stated"
    status = "completed" if result in {"normal", "abnormal"} else "not_stated"
    return {
        "status": status,
        "result": result,
        "missingness": "present" if status == "completed" else "not_stated",
        "temporality": "completed" if status == "completed" else "uncertain",
        "evidence": [] if status == "completed" else None,
        "evidence_event_ids": [],
    }


def quote_value(item: Any) -> str | None:
    if isinstance(item, dict):
        for key in ["quote", "support", "evidence", "source_quote"]:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def named_items(value: Any, value_keys: list[str]) -> list[dict[str, str | None]]:
    if value is None:
        return []
    if isinstance(value, list):
        items: list[dict[str, str | None]] = []
        for item in value:
            items.extend(named_items(item, value_keys))
        return items
    if isinstance(value, dict):
        text = None
        for key in value_keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                text = candidate.strip()
                break
        if text is None:
            text = first_value(value)
        return [{"value": text, "quote": quote_value(value)}] if text else []
    text = first_value(value)
    return [{"value": text, "quote": None}] if text else []


def d3_medication_items(payload: dict[str, Any]) -> list[dict[str, str | None]]:
    return named_items(
        payload.get("medication_names")
        or payload.get("current_anti_seizure_medications")
        or payload.get("current anti-seizure medications"),
        ["name", "value", "text", "medication"],
    )


def d3_seizure_items(payload: dict[str, Any]) -> list[dict[str, str | None]]:
    items = named_items(payload.get("seizure_types") or payload.get("seizure_type"), ["label", "benchmark_label", "value", "text"])
    for mapping in payload.get("verified_seizure_type_mappings") or []:
        if not isinstance(mapping, dict) or mapping.get("keep") is False:
            continue
        label = mapping.get("benchmark_label") or mapping.get("label")
        if isinstance(label, str) and label.strip():
            items.append({"value": label.strip(), "quote": quote_value(mapping)})
    deduped: list[dict[str, str | None]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for item in items:
        key = (item.get("value"), item.get("quote"))
        if item.get("value") and key not in seen:
            deduped.append(item)
            seen.add(key)
    return deduped


def d3_epilepsy_item(payload: dict[str, Any]) -> dict[str, str | None]:
    raw = (
        payload.get("epilepsy_types")
        or payload.get("epilepsy_diagnosis")
        or payload.get("epilepsy_diagnosis_type")
        or payload.get("epilepsy diagnosis/type")
    )
    items = named_items(raw, ["label", "value", "text", "diagnosis"])
    return items[0] if items else {"value": None, "quote": None}


def evidence_from_quote(document: dict[str, Any] | None, quote: str | None) -> list[dict[str, Any]]:
    if not quote or not document:
        return []
    if normalize_text(quote) not in normalize_text(document["text"]):
        return []
    char_start = document["text"].find(quote)
    char_end = char_start + len(quote) if char_start >= 0 else None
    sentence_id = None
    if char_start >= 0 and char_end is not None:
        for sentence in document.get("sentences", []):
            if sentence["char_start"] <= char_start and char_end <= sentence["char_end"]:
                sentence_id = sentence["sentence_id"]
                break
    return [
        {
            "quote": quote,
            "sentence_id": sentence_id,
            "char_start": char_start if char_start >= 0 else None,
            "char_end": char_end,
        }
    ]


def medication_from_item(item: dict[str, str | None], document: dict[str, Any] | None) -> dict[str, Any]:
    field = medication_from_text(str(item["value"]))
    field["evidence"] = evidence_from_quote(document, item.get("quote"))
    return field


def scalar_field_with_evidence(
    value: str | None,
    quote: str | None,
    document: dict[str, Any] | None,
    temporality: str = "current",
) -> dict[str, Any]:
    field = scalar_field(value, temporality)
    if value:
        field["evidence"] = evidence_from_quote(document, quote)
    return field


def projected_canonical(
    document_id: str,
    harness_id: str,
    model_label: str,
    payload: dict[str, Any],
    row: dict[str, str],
    document: dict[str, Any] | None = None,
    require_present_evidence: bool = False,
) -> dict[str, Any]:
    use_evidence_items = harness_id in {"D3_candidate_plus_verifier", "H7_extract_then_normalize"}
    raw_meds = payload.get("medications")
    has_structured_meds = isinstance(raw_meds, list) and any(isinstance(m, dict) and m.get("name") for m in raw_meds)
    if has_structured_meds:
        medication_items = [
            {"value": m["name"], "_structured": m, "quote": m.get("quote")}
            for m in raw_meds
            if isinstance(m, dict) and m.get("name")
        ]
    elif use_evidence_items:
        medication_items = d3_medication_items(payload)
    else:
        medication_items = [
            {"value": item, "quote": None}
            for item in value_list(
                payload.get("medication_names")
                or payload.get("current_anti_seizure_medications")
                or payload.get("current anti-seizure medications")
            )
        ]

    raw_seizure_items = d3_seizure_items(payload) if use_evidence_items else [
        {"value": item, "quote": None}
        for item in value_list(payload.get("seizure_types") or payload.get("seizure_type"))
    ]
    seizure_items: list[dict[str, str | None]] = []
    seen_seizure_labels: set[str] = set()
    for item in raw_seizure_items:
        label = benchmark_seizure_type(item.get("value"))
        if label and label not in seen_seizure_labels:
            seizure_items.append({"value": label, "quote": item.get("quote")})
            seen_seizure_labels.add(label)

    epilepsy_item = d3_epilepsy_item(payload) if use_evidence_items else {
        "value": first_value(
            payload.get("epilepsy_types")
            or payload.get("epilepsy_diagnosis")
            or payload.get("epilepsy_diagnosis_type")
            or payload.get("epilepsy diagnosis/type")
        ),
        "quote": None,
    }
    seizure_types = [str(item["value"]) for item in seizure_items if item.get("value")]
    epilepsy = epilepsy_item.get("value")
    if use_evidence_items and require_present_evidence:
        medication_items = [
            item for item in medication_items if item.get("value") and evidence_from_quote(document, item.get("quote"))
        ]
        seizure_items = [
            item for item in seizure_items if item.get("value") and evidence_from_quote(document, item.get("quote"))
        ]
        seizure_types = [str(item["value"]) for item in seizure_items if item.get("value")]
        if epilepsy and not evidence_from_quote(document, epilepsy_item.get("quote")):
            epilepsy = None
            epilepsy_item = {"value": None, "quote": None}

    frequency = first_value(payload.get("seizure_frequency") or payload.get("current_seizure_frequency"))
    inv_payload = payload.get("investigations")
    if isinstance(inv_payload, dict):
        eeg = first_value(inv_payload.get("eeg") or payload.get("eeg") or payload.get("EEG_result"))
        mri = first_value(inv_payload.get("mri") or payload.get("mri") or payload.get("MRI_result"))
    else:
        investigations = value_list(inv_payload)
        eeg = first_value(payload.get("eeg") or payload.get("EEG_result"))
        mri = first_value(payload.get("mri") or payload.get("MRI_result"))
        for item in investigations:
            lowered = item.lower()
            if "eeg" in lowered and not eeg:
                eeg = item
            if ("mri" in lowered or "magnetic resonance" in lowered) and not mri:
                mri = item

    def build_med(item: dict[str, Any]) -> dict[str, Any]:
        if "_structured" in item:
            med = item["_structured"]
            result = {
                "name": med.get("name") or "",
                "dose": str(med["dose"]) if med.get("dose") is not None else None,
                "dose_unit": str(med.get("unit") or med.get("dose_unit") or "") or None,
                "frequency": str(med["frequency"]) if med.get("frequency") else None,
                "status": "current",
                "missingness": "present",
                "temporality": "current",
                "evidence": [],
                "evidence_event_ids": [],
            }
            quote = item.get("quote") or med.get("quote")
            if quote:
                result["evidence"] = evidence_from_quote(document, quote)
            return result
        return medication_from_item(item, document)

    return {
        "document_id": document_id,
        "pipeline_id": f"{system_for_harness(harness_id)}_{'evidence_projection' if use_evidence_items else 'relaxed_projection'}",
        "fields": {
            "current_anti_seizure_medications": [
                build_med(item) for item in medication_items if item.get("value")
            ],
            "previous_anti_seizure_medications": [],
            "current_seizure_frequency": {
                **scalar_field(frequency),
                "temporal_scope": "current" if frequency else None,
                "seizure_type": seizure_types[0] if seizure_types else None,
            },
            "seizure_types": [
                scalar_field_with_evidence(str(item["value"]), item.get("quote"), document)
                for item in seizure_items
                if item.get("value")
            ],
            "eeg": investigation_field(eeg),
            "mri": investigation_field(mri),
            "epilepsy_diagnosis": scalar_field_with_evidence(
                str(epilepsy) if epilepsy else None,
                epilepsy_item.get("quote"),
                document,
            ),
        },
        "events": [],
        "metadata": {
            "model": row.get("provider_model_id") or model_label,
            "model_label": model_label,
            "harness_id": harness_id,
            "format": "unknown",
            "projection": RELAXED_PROJECTION_VERSION,
            "latency_ms": to_float(row.get("latency_ms")),
            "input_tokens": int(to_float(row.get("input_tokens")) or 0),
            "output_tokens": int(to_float(row.get("output_tokens")) or 0),
            "estimated_cost_usd": to_float(row.get("estimated_cost")),
        },
    }
