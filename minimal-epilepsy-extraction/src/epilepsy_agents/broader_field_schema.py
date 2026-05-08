"""Tier 1a broader-field JSON schema, prompts, and parser for broader-field runs."""
from __future__ import annotations

import json
import re
from typing import Any

from .structured_schema import extract_json_object

TIER1A_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["seizure_frequency", "current_medications", "seizure_types", "investigations"],
    "properties": {
        "seizure_frequency": {
            "type": "object",
            "additionalProperties": False,
            "required": ["label", "evidence", "confidence"],
            "properties": {
                "label": {"type": "string"},
                "evidence": {"type": "string"},
                "confidence": {"type": "number"},
            },
        },
        "current_medications": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["drug_name", "dose_text", "status", "evidence", "confidence"],
                "properties": {
                    "drug_name": {"type": "string"},
                    "dose_text": {"type": "string"},
                    "status": {"type": "string"},
                    "evidence": {"type": "string"},
                    "confidence": {"type": "number"},
                },
            },
        },
        "seizure_types": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["description", "onset", "evidence", "confidence"],
                "properties": {
                    "description": {"type": "string"},
                    "onset": {"type": "string"},
                    "evidence": {"type": "string"},
                    "confidence": {"type": "number"},
                },
            },
        },
        "investigations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["investigation_type", "result", "status", "evidence", "confidence"],
                "properties": {
                    "investigation_type": {"type": "string"},
                    "result": {"type": "string"},
                    "status": {"type": "string"},
                    "evidence": {"type": "string"},
                    "confidence": {"type": "number"},
                },
            },
        },
    },
}


TIER1A_BROADER_ONLY_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["current_medications", "seizure_types", "investigations"],
    "properties": {
        "current_medications": TIER1A_JSON_SCHEMA["properties"]["current_medications"],  # type: ignore[index]
        "seizure_types": TIER1A_JSON_SCHEMA["properties"]["seizure_types"],  # type: ignore[index]
        "investigations": TIER1A_JSON_SCHEMA["properties"]["investigations"],  # type: ignore[index]
    },
}


def tier1a_system_prompt() -> str:
    return (
        "/no_think\n"
        "You extract structured clinical information from epilepsy clinic letters. "
        "Do not include deliberation, hidden reasoning, markdown, or explanatory prose. "
        "Return only JSON conforming to the supplied schema. "
        "Use the exact key names specified in the user message."
    )


def tier1a_user_prompt(letter: str) -> str:
    return (
        "Extract the following Tier 1a fields from this synthetic epilepsy clinic letter. "
        "Return a JSON object with exactly these four top-level keys: "
        "seizure_frequency, current_medications, seizure_types, investigations.\n\n"
        "seizure_frequency: object with keys label (structured frequency label such as "
        "'2 per week', 'seizure free for 6 months', or 'unknown'), "
        "evidence (quoted text span), confidence (0 to 1).\n\n"
        "current_medications: current anti-seizure medications only; do not include non-ASMs "
        "such as vitamins, folic acid, antihypertensives, antidepressants, analgesics, or antiemetics. "
        "Array of objects, each with keys drug_name (normalized name), "
        "dose_text (dose and frequency or empty string), "
        "status (one of: current, previous, planned, uncertain), "
        "evidence (quoted text span), confidence (0 to 1). "
        "Use an empty array if no anti-seizure medications are mentioned.\n\n"
        "seizure_types: array of objects, each with keys "
        "description (seizure type as stated in the letter), "
        "onset (one of: focal, generalized, unknown, not_stated), "
        "evidence (quoted text span), confidence (0 to 1). "
        "Use an empty array if no seizure type is explicitly stated.\n\n"
        "investigations: array of objects, each with keys "
        "investigation_type (one of: EEG, MRI, CT, genetic_test, video_EEG, other), "
        "result (one of: normal, abnormal, non_diagnostic, pending, not_stated), "
        "status (one of: completed, planned, historical, pending, conditional, uncertain), "
        "evidence (quoted text span), confidence (0 to 1). "
        "Extract an investigation only when the evidence explicitly names or clearly describes a test; "
        "do not infer EEG, MRI, CT, video EEG, or genetic testing from follow-up modality, diagnosis, "
        "medication choice, or general epilepsy context. Do not map non-diagnostic EEG wording to normal. "
        "Use planned when a test is firmly ordered but not yet done; use pending when a completed, "
        "sent, or requested test has no available result; use conditional when wording says to "
        "consider or arrange the test only if a future condition occurs. "
        "Map bloods, metabolic panels, thyroid tests, ECG/EKG, and drug levels to other, not CT. "
        "Do not extract absence-only or negated investigation statements such as no prior EEG, "
        "no MRI available, or no investigations planned as pending, completed, or planned tests. "
        "Use an empty array if no investigation is mentioned.\n\n"
        f"Letter:\n{letter}"
    )


def tier1a_h010_user_prompt(letter: str) -> str:
    """h010: same Tier 1a schema as h008 but with h003-style anti-abstention guidance for SF."""
    return (
        "Extract structured clinical information from this synthetic epilepsy clinic letter. "
        "Return a JSON object with exactly these four top-level keys: "
        "seizure_frequency, current_medications, seizure_types, investigations.\n\n"
        "For seizure_frequency: extract the current seizure-frequency label. "
        "Prefer an explicit frequency label when the letter gives a count and time window; "
        "if the letter states the patient is seizure-free or has had no seizures, use a label "
        "starting with 'seizure free' (e.g. 'seizure free for 6 months' or "
        "'seizure free for multiple months') — do not use unknown for seizure-free patients; "
        "use unknown only when frequency is genuinely absent, ambiguous, or impossible to normalize. "
        "Keys: label (string), evidence (quoted text span), confidence (0 to 1).\n\n"
        "For current_medications: current anti-seizure medications only; do not include non-ASMs "
        "such as vitamins, folic acid, antihypertensives, antidepressants, analgesics, or antiemetics. "
        "Array of objects, each with keys "
        "drug_name (normalized name), dose_text (dose and frequency or empty string), "
        "status (one of: current, previous, planned, uncertain), "
        "evidence (quoted text span), confidence (0 to 1). "
        "Use an empty array only if the letter mentions no anti-seizure medications.\n\n"
        "For seizure_types: array of objects, each with keys "
        "description (seizure type as stated in the letter), "
        "onset (one of: focal, generalized, unknown, not_stated), "
        "evidence (quoted text span), confidence (0 to 1). "
        "Use an empty array only if no seizure type is explicitly stated.\n\n"
        "For investigations: array of objects, each with keys "
        "investigation_type (one of: EEG, MRI, CT, genetic_test, video_EEG, other), "
        "result (one of: normal, abnormal, non_diagnostic, pending, not_stated), "
        "status (one of: completed, planned, historical, pending, conditional, uncertain), "
        "evidence (quoted text span), confidence (0 to 1). "
        "Extract an investigation only when the evidence explicitly names or clearly describes a test; "
        "do not infer EEG, MRI, CT, video EEG, or genetic testing from follow-up modality, diagnosis, "
        "medication choice, or general epilepsy context. Do not map non-diagnostic EEG wording to normal. "
        "Use planned when a test is firmly ordered but not yet done; use pending when a completed, "
        "sent, or requested test has no available result; use conditional when wording says to "
        "consider or arrange the test only if a future condition occurs. "
        "Map bloods, metabolic panels, thyroid tests, ECG/EKG, and drug levels to other, not CT. "
        "Do not extract absence-only or negated investigation statements such as no prior EEG, "
        "no MRI available, or no investigations planned as pending, completed, or planned tests. "
        "Use an empty array only if no investigation is mentioned.\n\n"
        f"Letter:\n{letter}"
    )


def broader_only_context_user_prompt(letter: str, sf_label: str) -> str:
    """h011: broader-only prompt with SF label injected as context (not a schema field)."""
    return (
        f"The seizure frequency for this patient is: {sf_label!r}. "
        "Using that context, extract the following three fields from the clinic letter below. "
        "Return a JSON object with exactly these top-level keys: "
        "current_medications, seizure_types, investigations.\n\n"
        "current_medications: current anti-seizure medications only; do not include non-ASMs "
        "such as vitamins, folic acid, antihypertensives, antidepressants, analgesics, or antiemetics. "
        "Array of objects, each with keys drug_name (normalized name), "
        "dose_text (dose and frequency or empty string), "
        "status (one of: current, previous, planned, uncertain), "
        "evidence (quoted text span), confidence (0 to 1). "
        "Use an empty array only if the letter mentions no anti-seizure medications.\n\n"
        "seizure_types: array of objects, each with keys "
        "description (seizure type as stated in the letter), "
        "onset (one of: focal, generalized, unknown, not_stated), "
        "evidence (quoted text span), confidence (0 to 1). "
        "Use an empty array only if no seizure type is explicitly stated.\n\n"
        "investigations: array of objects, each with keys "
        "investigation_type (one of: EEG, MRI, CT, genetic_test, video_EEG, other), "
        "result (one of: normal, abnormal, non_diagnostic, pending, not_stated), "
        "status (one of: completed, planned, historical, pending, conditional, uncertain), "
        "evidence (quoted text span), confidence (0 to 1). "
        "Extract an investigation only when the evidence explicitly names or clearly describes a test; "
        "do not infer EEG, MRI, CT, video EEG, or genetic testing from follow-up modality, diagnosis, "
        "medication choice, or general epilepsy context. Do not map non-diagnostic EEG wording to normal. "
        "Use planned when a test is firmly ordered but not yet done; use pending when a completed, "
        "sent, or requested test has no available result; use conditional when wording says to "
        "consider or arrange the test only if a future condition occurs. "
        "Map bloods, metabolic panels, thyroid tests, ECG/EKG, and drug levels to other, not CT. "
        "Do not extract absence-only or negated investigation statements such as no prior EEG, "
        "no MRI available, or no investigations planned as pending, completed, or planned tests. "
        "Use an empty array only if no investigation is mentioned.\n\n"
        f"Letter:\n{letter}"
    )


def broader_only_user_prompt(letter: str) -> str:
    return (
        "Extract the following three fields from this synthetic epilepsy clinic letter. "
        "Return a JSON object with exactly these top-level keys: "
        "current_medications, seizure_types, investigations.\n\n"
        "current_medications: current anti-seizure medications only; do not include non-ASMs "
        "such as vitamins, folic acid, antihypertensives, antidepressants, analgesics, or antiemetics. "
        "Array of objects, each with keys drug_name (normalized name), "
        "dose_text (dose and frequency or empty string), "
        "status (one of: current, previous, planned, uncertain), "
        "evidence (quoted text span), confidence (0 to 1). "
        "Use an empty array if no anti-seizure medications are mentioned.\n\n"
        "seizure_types: array of objects, each with keys "
        "description (seizure type as stated in the letter), "
        "onset (one of: focal, generalized, unknown, not_stated), "
        "evidence (quoted text span), confidence (0 to 1). "
        "Use an empty array if no seizure type is explicitly stated.\n\n"
        "investigations: array of objects, each with keys "
        "investigation_type (one of: EEG, MRI, CT, genetic_test, video_EEG, other), "
        "result (one of: normal, abnormal, non_diagnostic, pending, not_stated), "
        "status (one of: completed, planned, historical, pending, conditional, uncertain), "
        "evidence (quoted text span), confidence (0 to 1). "
        "Extract an investigation only when the evidence explicitly names or clearly describes a test; "
        "do not infer EEG, MRI, CT, video EEG, or genetic testing from follow-up modality, diagnosis, "
        "medication choice, or general epilepsy context. Do not map non-diagnostic EEG wording to normal. "
        "Use planned when a test is firmly ordered but not yet done; use pending when a completed, "
        "sent, or requested test has no available result; use conditional when wording says to "
        "consider or arrange the test only if a future condition occurs. "
        "Map bloods, metabolic panels, thyroid tests, ECG/EKG, and drug levels to other, not CT. "
        "Do not extract absence-only or negated investigation statements such as no prior EEG, "
        "no MRI available, or no investigations planned as pending, completed, or planned tests. "
        "Use an empty array if no investigation is mentioned.\n\n"
        f"Letter:\n{letter}"
    )


def broader_coverage_user_prompt(letter: str) -> str:
    """h012: broader-only prompt tuned for coverage while keeping evidence support."""
    return (
        "Seizure frequency is extracted in a separate call. Your task here is to extract the "
        "other clinically useful M-C3 fields from this synthetic epilepsy clinic letter. "
        "Be coverage-oriented and evidence-bound: include every supported current anti-seizure "
        "medication, seizure type, and investigation you can find, but do not infer facts that "
        "are not stated or clearly described. Return a JSON object with exactly these top-level "
        "keys: current_medications, seizure_types, investigations.\n\n"
        "General rules: quote the shortest useful evidence span for each item; prefer including "
        "a low-confidence or uncertain item when the letter explicitly mentions it over leaving "
        "a supported field empty; use empty arrays only when the letter has no support for that "
        "field. Do not include explanatory prose or markdown.\n\n"
        "current_medications: extract current anti-seizure medications only. Include maintenance "
        "ASMs and rescue ASMs if they are currently prescribed. Do not include non-ASMs such as "
        "vitamins, folic acid, antihypertensives, antidepressants, analgesics, or antiemetics. "
        "Array of objects, each with keys drug_name (normalized name), dose_text (dose and "
        "frequency or empty string), status (one of: current, previous, planned, uncertain), "
        "evidence (quoted text span), confidence (0 to 1).\n\n"
        "seizure_types: extract explicitly stated seizure/event types, semiology labels, or "
        "clinically named episode descriptions. Array of objects, each with keys description "
        "(seizure type as stated in the letter), onset (one of: focal, generalized, unknown, "
        "not_stated), evidence (quoted text span), confidence (0 to 1). Use onset unknown or "
        "not_stated rather than dropping a clearly stated seizure type.\n\n"
        "investigations: extract tests that are completed, historical, planned, pending, or "
        "conditional when a test is explicitly named or clearly described. Array of objects, each "
        "with keys investigation_type (one of: EEG, MRI, CT, genetic_test, video_EEG, other), "
        "result (one of: normal, abnormal, non_diagnostic, pending, not_stated), status (one of: "
        "completed, planned, historical, pending, conditional, uncertain), evidence (quoted text "
        "span), confidence (0 to 1). Use planned when a test is firmly ordered but not yet done; "
        "pending when a completed, sent, requested, or ordered test has no available result; "
        "conditional when wording says to consider or arrange the test only if a future condition "
        "occurs. Extract bloods, metabolic panels, thyroid tests, ECG/EKG, and drug levels as "
        "other. Do not infer EEG, MRI, CT, video EEG, or genetic testing from follow-up modality, "
        "diagnosis, medication choice, or general epilepsy context. Do not extract absence-only "
        "or negated investigation statements such as no prior EEG, no MRI available, or no "
        "investigations planned as pending, completed, or planned tests.\n\n"
        f"Letter:\n{letter}"
    )


def parse_broader_only_response(content: str) -> dict[str, Any]:
    """Parse a broader-only (no SF) LLM response; returns a dict with the 3 broader fields."""
    try:
        payload = _payload_object(json.loads(extract_json_object(content)))
        return {
            "current_medications": _normalize_medications(
                _first_present(payload, "current_medications", "medications", "anti_seizure_medications")
            ),
            "seizure_types": _coerce_list(_first_present(payload, "seizure_types", "seizure_type")),
            "investigations": _normalize_investigations(
                _first_present(payload, "investigations", "investigation")
            ),
            "invalid_output": False,
        }
    except Exception:
        return {
            "current_medications": [],
            "seizure_types": [],
            "investigations": [],
            "invalid_output": True,
        }


def parse_broader_field_response(content: str) -> dict[str, Any]:
    """Parse raw LLM output into a broader-field dict; returns an invalid-flagged dict on failure."""
    try:
        payload = _payload_object(json.loads(extract_json_object(content)))
        return {
            "seizure_frequency": _parse_sf(payload.get("seizure_frequency", {})),
            "current_medications": _normalize_medications(
                _first_present(payload, "current_medications", "medications", "anti_seizure_medications")
            ),
            "seizure_types": _coerce_list(_first_present(payload, "seizure_types", "seizure_type")),
            "investigations": _normalize_investigations(
                _first_present(payload, "investigations", "investigation")
            ),
            "invalid_output": False,
        }
    except Exception:
        return {
            "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
            "current_medications": [],
            "seizure_types": [],
            "investigations": [],
            "invalid_output": True,
        }


def _payload_object(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload_not_object")
    for key in ("extractions", "fields", "result", "output"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            return nested
    return payload


def _first_present(payload: dict[str, Any], *keys: str) -> object:
    for key in keys:
        if key in payload:
            return payload[key]
    return []


def _parse_sf(sf: object) -> dict[str, Any]:
    if not isinstance(sf, dict):
        return {"label": "unknown", "evidence": "", "confidence": 0.0}
    return {
        "label": str(sf.get("label", "unknown")).strip(),
        "evidence": str(sf.get("evidence", "")),
        "confidence": float(sf.get("confidence", 0.0)),
    }


def _coerce_list(value: object) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


_ASM_ALIASES = {
    "brivaracetam",
    "buccal midazolam",
    "carbamazepine",
    "cenobamate",
    "clobazam",
    "clonazepam",
    "diazepam",
    "eslicarbazepine",
    "ethosuximide",
    "gabapentin",
    "lacosamide",
    "lamotrigine",
    "levetiracetam",
    "midazolam",
    "oxcarbazepine",
    "perampanel",
    "phenobarbital",
    "phenobarbitone",
    "phenytoin",
    "pregabalin",
    "primidone",
    "rufinamide",
    "sodium valproate",
    "stiripentol",
    "tiagabine",
    "topiramate",
    "valproate",
    "vigabatrin",
    "zonisamide",
}


def _normalize_medications(value: object) -> list[dict[str, Any]]:
    medications = _coerce_list(value)
    return [item for item in medications if _is_anti_seizure_medication(item)]


def _is_anti_seizure_medication(item: dict[str, Any]) -> bool:
    drug_name = _norm(str(item.get("drug_name", "")))
    evidence = _norm(str(item.get("evidence", "")))
    haystack = f"{drug_name} {evidence}"
    return any(_contains_any(haystack, (alias,)) for alias in _ASM_ALIASES)


def _normalize_investigations(value: object) -> list[dict[str, Any]]:
    investigations = _coerce_list(value)
    return [_normalize_investigation_item(item) for item in investigations]


def _normalize_investigation_item(item: dict[str, Any]) -> dict[str, Any]:
    evidence = str(item.get("evidence", ""))
    return {
        **item,
        "investigation_type": _normalize_investigation_type(
            str(item.get("investigation_type", "")),
            evidence,
        ),
        "result": _normalize_investigation_result(str(item.get("result", ""))),
        "status": _normalize_investigation_status(str(item.get("status", ""))),
        "evidence": evidence,
    }


def _normalize_investigation_type(raw_type: str, evidence: str) -> str:
    evidence_norm = _norm(evidence)
    raw_norm = _norm(raw_type)

    if _contains_any(evidence_norm, ("video eeg", "video eeg monitoring", "telemetry", "video telemetry")):
        return "video_EEG"
    if _contains_any(evidence_norm, ("ambulatory eeg", "home eeg", "routine eeg", "eeg")):
        return "EEG"
    if _contains_any(evidence_norm, ("mri", "magnetic resonance")):
        return "MRI"
    if _contains_any(evidence_norm, ("ct", "computed tomography")):
        return "CT"
    if _contains_any(evidence_norm, ("genetic", "gene panel", "genomic")):
        return "genetic_test"
    if _contains_any(
        evidence_norm,
        (
            "blood",
            "serum",
            "u e",
            "lft",
            "fbc",
            "vitamin",
            "drug level",
            "drug levels",
            "ecg",
            "ekg",
            "thyroid",
            "thyroid function",
            "metabolic panel",
            "metabolic profile",
            "neuroimaging",
            "imaging",
        ),
    ):
        return "other"

    if raw_norm in {"eeg"}:
        return "EEG"
    if raw_norm in {"mri"}:
        return "MRI"
    if raw_norm in {"ct"}:
        return "CT"
    if raw_norm in {"genetic test", "genetic", "gene panel"}:
        return "genetic_test"
    if raw_norm in {"video eeg", "video eeg monitoring", "telemetry"}:
        return "video_EEG"
    if raw_norm in {
        "other",
        "blood test",
        "bloods",
        "blood",
        "serum biochemistry",
        "drug level",
        "drug levels",
        "metabolic panel",
        "metabolic profile",
        "ecg",
        "ekg",
        "thyroid",
        "thyroid function",
        "neuroimaging",
        "imaging",
    }:
        return "other"
    return raw_type.strip()


def _normalize_investigation_result(raw_result: str) -> str:
    result_norm = _norm(raw_result)
    if result_norm in {"normal", "within reference limits"}:
        return "normal"
    if result_norm in {"abnormal", "abnormality"}:
        return "abnormal"
    if result_norm in {"non diagnostic", "nondiagnostic", "indeterminate"}:
        return "non_diagnostic"
    if result_norm in {"pending", "awaited"}:
        return "pending"
    if result_norm in {"not stated", "unknown", ""}:
        return "not_stated"
    return raw_result.strip()


def _normalize_investigation_status(raw_status: str) -> str:
    status_norm = _norm(raw_status)
    if status_norm in {"completed", "done", "performed", "available"}:
        return "completed"
    if status_norm in {"planned", "ordered", "arranged"}:
        return "planned"
    if status_norm in {"pending", "awaiting", "awaited", "requested", "sent", "result awaited"}:
        return "pending"
    if status_norm in {"conditional", "considered", "consider", "if needed", "if worsens"}:
        return "conditional"
    if status_norm in {"historical", "history", "previous", "prior", "past"}:
        return "historical"
    if status_norm in {"uncertain", "unknown", "not stated", ""}:
        return "uncertain"
    return raw_status.strip()


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    padded_text = f" {text} "
    return any(f" {_norm(phrase)} " in padded_text for phrase in phrases)


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))
