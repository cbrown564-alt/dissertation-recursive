"""Deterministic support checks for M-C3 broader-field outputs."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


_MEDICATION_STATUSES = {"current", "previous", "planned", "uncertain"}
_INVESTIGATION_TYPES = {"EEG", "MRI", "CT", "genetic_test", "video_EEG", "other"}
_INVESTIGATION_RESULTS = {"normal", "abnormal", "non_diagnostic", "pending", "not_stated"}
_INVESTIGATION_STATUSES = {"completed", "planned", "historical", "pending", "conditional", "uncertain"}
_MIN_OVERLAP_TOKENS = 4
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


def verify_broader_field_support(letter: str, result: dict[str, Any]) -> dict[str, Any]:
    """Annotate scored broader-field items with deterministic support metadata.

    The verifier is intentionally conservative. It does not adjudicate clinical
    truth; it records whether an item cites text that is present in the source
    letter and whether the scored labels stay inside the locked M-C3 policy.
    """
    verified = deepcopy(result)
    verified["current_medications"] = [
        _verify_medication(letter, item) for item in verified.get("current_medications", [])
    ]
    verified["investigations"] = [
        _verify_investigation(letter, item) for item in verified.get("investigations", [])
    ]
    return verified


def _verify_medication(letter: str, item: dict[str, Any]) -> dict[str, Any]:
    evidence_grade = _evidence_grade(letter, str(item.get("evidence", "")))
    warnings: list[str] = []
    status = str(item.get("status", "")).strip()
    drug_name = str(item.get("drug_name", "")).strip()

    if status not in _MEDICATION_STATUSES:
        warnings.append("invalid_medication_status")
    if drug_name and not _contains_phrase(str(item.get("evidence", "")), drug_name):
        warnings.append("drug_name_not_in_evidence")
    if drug_name and not _is_anti_seizure_medication(drug_name, str(item.get("evidence", ""))):
        warnings.append("non_asm_medication")

    supported = (
        evidence_grade in {"exact_span", "overlapping_span"}
        and status in _MEDICATION_STATUSES
        and bool(drug_name)
        and "drug_name_not_in_evidence" not in warnings
        and "non_asm_medication" not in warnings
    )
    return {
        **item,
        "support": {
            "evidence_grade": evidence_grade,
            "value_supported": bool(drug_name)
            and "drug_name_not_in_evidence" not in warnings
            and "non_asm_medication" not in warnings,
            "status_supported": status in _MEDICATION_STATUSES,
            "supported": supported,
            "warnings": warnings,
        },
    }


def _verify_investigation(letter: str, item: dict[str, Any]) -> dict[str, Any]:
    evidence_grade = _evidence_grade(letter, str(item.get("evidence", "")))
    warnings: list[str] = []
    investigation_type = str(item.get("investigation_type", "")).strip()
    result = str(item.get("result", "")).strip()
    status = str(item.get("status", "")).strip()

    if investigation_type not in _INVESTIGATION_TYPES:
        warnings.append("invalid_investigation_type")
    if result not in _INVESTIGATION_RESULTS:
        warnings.append("invalid_investigation_result")
    if status not in _INVESTIGATION_STATUSES:
        warnings.append("invalid_investigation_status")
    if investigation_type != "other" and not _investigation_type_in_evidence(
        str(item.get("evidence", "")), investigation_type
    ):
        warnings.append("investigation_type_not_in_evidence")
    if status == "planned" and _evidence_has_conditional_plan(str(item.get("evidence", ""))):
        warnings.append("conditional_plan_marked_planned")
    if status == "pending" and _evidence_has_conditional_plan(str(item.get("evidence", ""))):
        warnings.append("conditional_plan_marked_pending")
    if status in {"completed", "planned", "pending"} and _evidence_is_absence_only_investigation(
        str(item.get("evidence", "")), investigation_type
    ):
        warnings.append("absence_only_investigation")

    supported = (
        evidence_grade in {"exact_span", "overlapping_span"}
        and investigation_type in _INVESTIGATION_TYPES
        and result in _INVESTIGATION_RESULTS
        and status in _INVESTIGATION_STATUSES
        and "investigation_type_not_in_evidence" not in warnings
        and "conditional_plan_marked_planned" not in warnings
        and "conditional_plan_marked_pending" not in warnings
        and "absence_only_investigation" not in warnings
    )
    return {
        **item,
        "support": {
            "evidence_grade": evidence_grade,
            "value_supported": "investigation_type_not_in_evidence" not in warnings
            and investigation_type in _INVESTIGATION_TYPES,
            "status_supported": status in _INVESTIGATION_STATUSES
            and "conditional_plan_marked_planned" not in warnings
            and "conditional_plan_marked_pending" not in warnings
            and "absence_only_investigation" not in warnings,
            "normalization_supported": result in _INVESTIGATION_RESULTS,
            "supported": supported,
            "warnings": warnings,
        },
    }


def _evidence_grade(letter: str, evidence: str) -> str:
    evidence = evidence.strip()
    if not evidence:
        return "missing_evidence"
    if _norm(evidence) in _norm(letter):
        return "exact_span"
    if _has_contiguous_overlap(letter, evidence):
        return "overlapping_span"
    return "unsupported"


def _has_contiguous_overlap(letter: str, evidence: str) -> bool:
    letter_tokens = _tokens(letter)
    evidence_tokens = _tokens(evidence)
    if len(evidence_tokens) < _MIN_OVERLAP_TOKENS:
        return False
    letter_ngrams = {
        tuple(letter_tokens[i : i + _MIN_OVERLAP_TOKENS])
        for i in range(0, len(letter_tokens) - _MIN_OVERLAP_TOKENS + 1)
    }
    return any(
        tuple(evidence_tokens[i : i + _MIN_OVERLAP_TOKENS]) in letter_ngrams
        for i in range(0, len(evidence_tokens) - _MIN_OVERLAP_TOKENS + 1)
    )


def _contains_phrase(text: str, phrase: str) -> bool:
    return _norm(phrase) in _norm(text)


def _is_anti_seizure_medication(drug_name: str, evidence: str) -> bool:
    haystack = _norm(f"{drug_name} {evidence}")
    return any(_norm(alias) in haystack for alias in _ASM_ALIASES)


def _investigation_type_in_evidence(evidence: str, investigation_type: str) -> bool:
    aliases = {
        "genetic_test": ["genetic", "gene", "panel"],
        "video_EEG": ["video eeg", "video-eeg", "telemetry"],
    }.get(investigation_type, [investigation_type])
    evidence_norm = _norm(evidence)
    return any(_norm(alias) in evidence_norm for alias in aliases)


def _evidence_has_conditional_plan(evidence: str) -> bool:
    evidence_norm = _norm(evidence)
    conditional_markers = (
        "consider",
        "if frequency",
        "if pattern",
        "if events",
        "if seizures",
        "if worse",
        "if worsens",
        "if recurs",
        "if recur",
        "should symptoms",
        "should events",
        "if clinically indicated",
    )
    return any(marker in evidence_norm for marker in conditional_markers)


def _evidence_is_absence_only_investigation(evidence: str, investigation_type: str) -> bool:
    evidence_norm = _norm(evidence)
    if not evidence_norm:
        return False

    absence_markers = (
        "no prior",
        "no previous",
        "no recent",
        "no available",
        "not available",
        "unavailable",
        "not accessible",
        "no eegs available",
        "no eeg available",
        "no mri available",
        "no ct available",
        "no investigations",
        "no further investigations",
        "no investigation planned",
        "no investigations planned",
        "not been performed",
        "has not been performed",
        "no prior video eeg",
        "no prior video eeg monitoring",
    )
    if not any(marker in evidence_norm for marker in absence_markers):
        return False
    if investigation_type == "other":
        return False
    return _investigation_type_in_evidence(evidence, investigation_type)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _norm(text: str) -> str:
    return " ".join(_tokens(text))
