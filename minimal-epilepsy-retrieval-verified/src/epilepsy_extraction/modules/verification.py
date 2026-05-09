from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from epilepsy_extraction.schemas.contracts import EvidenceGrade


@dataclass(frozen=True)
class EvidenceVerificationResult:
    grade: EvidenceGrade
    matched_span: str | None = None
    notes: list[str] = field(default_factory=list)


def verify_evidence_deterministic(
    claimed_value: str,
    evidence_quote: str | None,
    context: str,
) -> EvidenceVerificationResult:
    """Check whether the evidence_quote appears in context, grading the match quality."""
    if not evidence_quote:
        return EvidenceVerificationResult(
            grade=EvidenceGrade.MISSING_EVIDENCE,
            notes=["no_evidence_quote"],
        )
    if evidence_quote.lower() in context.lower():
        return EvidenceVerificationResult(
            grade=EvidenceGrade.EXACT_SPAN,
            matched_span=evidence_quote,
        )
    words = set(re.findall(r"\w+", evidence_quote.lower()))
    context_words = set(re.findall(r"\w+", context.lower()))
    overlap = words & context_words
    if words and len(overlap) / len(words) >= 0.6:
        return EvidenceVerificationResult(
            grade=EvidenceGrade.OVERLAPPING_SPAN,
            matched_span=evidence_quote,
            notes=["fuzzy_match"],
        )
    if claimed_value and claimed_value.lower() in context.lower():
        return EvidenceVerificationResult(
            grade=EvidenceGrade.SECTION_LEVEL,
            notes=["value_found_but_quote_not_matched"],
        )
    return EvidenceVerificationResult(
        grade=EvidenceGrade.UNSUPPORTED,
        notes=["evidence_not_found_in_context"],
    )


def verify_field_extraction(
    field_data: dict[str, Any],
    context: str,
) -> tuple[dict[str, Any], list[EvidenceVerificationResult]]:
    """Verify citation evidence for a field extraction result.

    Returns (artifact_dict, results) where artifact_dict records grades per
    citation. The original field_data is not mutated.
    """
    citations = field_data.get("citations", [])
    if not citations:
        return {"grade": EvidenceGrade.MISSING_EVIDENCE.value, "citations_checked": 0}, []

    results: list[EvidenceVerificationResult] = []
    annotated: list[dict[str, Any]] = []
    for citation in citations:
        quote = citation.get("quote") if isinstance(citation, dict) else str(citation)
        value_candidates = [str(v) for v in field_data.values() if isinstance(v, (str, int, float))]
        claimed = value_candidates[0] if value_candidates else ""
        result = verify_evidence_deterministic(claimed, quote, context)
        results.append(result)
        entry: dict[str, Any] = {"quote": quote, "grade": result.grade.value}
        if result.notes:
            entry["notes"] = result.notes
        annotated.append(entry)

    grades = [r.grade for r in results]
    grade_order = list(EvidenceGrade)
    best_grade = min(grades, key=lambda g: grade_order.index(g))
    return {
        "grade": best_grade.value,
        "citations_checked": len(results),
        "citation_grades": annotated,
        "verifier_gates": verifier_gate_summary(field_data, context),
    }, results


def verifier_gate_summary(field_data: dict[str, Any], context: str) -> dict[str, Any]:
    """Return gate-level verifier outcomes for a field-family payload."""
    citations = field_data.get("citations", [])
    citation_results: list[EvidenceVerificationResult] = []
    for citation in citations if isinstance(citations, list) else []:
        if not isinstance(citation, dict):
            continue
        quote = citation.get("quote")
        claim = _claim_for_citation(field_data, citation)
        citation_results.append(verify_evidence_deterministic(claim, quote, context))

    value_supported = any(result.grade in {EvidenceGrade.EXACT_SPAN, EvidenceGrade.OVERLAPPING_SPAN} for result in citation_results)
    if not citation_results:
        value_supported = False

    status_support = _status_support(field_data, context)
    temporality_support = _temporality_support(field_data, context)
    normalization_support = _normalization_support(field_data)
    placement_support = _field_family_placement_support(field_data)
    edge_case_support = _epilepsy_edge_case_support(field_data, context)
    gates = {
        "value_support": value_supported,
        "status_support": status_support,
        "temporality_support": temporality_support,
        "normalization_support": normalization_support,
        "field_family_placement": placement_support,
        "edge_case_checks": edge_case_support,
    }
    return {
        "gates": gates,
        "passed": all(gates.values()),
        "failed_gates": [name for name, passed in gates.items() if not passed],
        "citations_checked": len(citation_results),
    }


def apply_verifier_gate_policy(field_data: dict[str, Any], gate_summary: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Downgrade unsupported overclaims without inventing replacement values."""
    if gate_summary.get("passed"):
        return field_data, []
    warnings = [f"verifier_gate_failed:{gate}" for gate in gate_summary.get("failed_gates", [])]
    if not gate_summary.get("gates", {}).get("value_support", True):
        downgraded = dict(field_data)
        downgraded["warnings"] = [str(w) for w in downgraded.get("warnings", [])] + warnings
        downgraded["unsupported_by_verifier"] = True
        return downgraded, warnings
    return field_data, warnings


def _claim_for_citation(field_data: dict[str, Any], citation: dict[str, Any]) -> str:
    field_name = citation.get("field")
    if isinstance(field_name, str) and field_name in field_data:
        value = field_data[field_name]
        if isinstance(value, dict):
            return str(value.get("value") or value.get("label") or "")
        return str(value)
    values = [str(v) for v in field_data.values() if isinstance(v, (str, int, float))]
    return values[0] if values else ""


def _status_support(field_data: dict[str, Any], context: str) -> bool:
    text = context.lower()
    current_terms = ("current", "currently", "ongoing", "now", "taking", "continues")
    status_values = _nested_values(field_data, "status")
    if not status_values:
        return True
    if any(str(value).lower() == "current" for value in status_values):
        return any(term in text for term in current_terms)
    return True


def _temporality_support(field_data: dict[str, Any], context: str) -> bool:
    temporal_values = _nested_values(field_data, "temporality")
    if not temporal_values:
        return True
    text = context.lower()
    temporal_terms = ("current", "currently", "previous", "previously", "last", "since", "for", "now")
    return any(term in text for term in temporal_terms)


def _normalization_support(field_data: dict[str, Any]) -> bool:
    seizure_frequency = field_data.get("seizure_frequency")
    if not isinstance(seizure_frequency, dict):
        return True
    value = seizure_frequency.get("value") or seizure_frequency.get("label")
    monthly_rate = seizure_frequency.get("monthly_rate") or seizure_frequency.get("parsed_monthly_rate")
    if value and "per" in str(value).lower() and monthly_rate is None:
        return False
    return True


def _field_family_placement_support(field_data: dict[str, Any]) -> bool:
    known_fields = {
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
    }
    return all(key in known_fields or key.startswith("_") for key in field_data)


def _epilepsy_edge_case_support(field_data: dict[str, Any], context: str) -> bool:
    text = context.lower()
    if "seizure free" in text or "seizure-free" in text:
        return True
    seizure_frequency = field_data.get("seizure_frequency")
    if isinstance(seizure_frequency, dict):
        value = str(seizure_frequency.get("value") or "").lower()
        if "seizure free" in value or "seizure-free" in value:
            return "seizure free" in text or "seizure-free" in text
    return True


def _nested_values(data: Any, key: str) -> list[Any]:
    values: list[Any] = []
    if isinstance(data, dict):
        for item_key, item_value in data.items():
            if item_key == key:
                values.append(item_value)
            values.extend(_nested_values(item_value, key))
    elif isinstance(data, list):
        for item in data:
            values.extend(_nested_values(item, key))
    return values
