"""Rule-assisted evidence support scoring for canonical extractions.

This module deliberately separates quote validity from evidence support.  A
quote can be copied from the source letter and still fail to support the
extracted claim, so the scorer reports a conservative support status per claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from normalization import (
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
from validate_extraction import normalize_text


@dataclass(frozen=True)
class GoldSpanLike:
    start: int
    end: int
    label: str
    value: str


@dataclass(frozen=True)
class SupportClaim:
    path: str
    field: str
    group: str
    value: str
    supported_by_gold: bool


def overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def evidence_overlaps_gold(evidence: dict[str, Any], spans: list[GoldSpanLike]) -> bool:
    start = evidence.get("char_start")
    end = evidence.get("char_end")
    if isinstance(start, int) and isinstance(end, int):
        return any(overlap(start, end, span.start, span.end) > 0 for span in spans)
    quote = normalize_value(evidence.get("quote"))
    return bool(quote and any(quote in normalize_value(span.value) or normalize_value(span.value) in quote for span in spans))


def _medication_tuple(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        canonical_medication_name(item.get("name")),
        normalize_dose(item.get("dose")),
        normalize_unit(item.get("dose_unit")),
        normalize_frequency(item.get("frequency")),
    )


def _medication_name_tuple(item: dict[str, Any]) -> tuple[str]:
    return (canonical_medication_name(item.get("name")),)


def _frequency_parts(item: dict[str, Any]) -> dict[str, str]:
    return {
        "count": item.get("count", "") or "",
        "period_count": item.get("period_count", "") or "",
        "period_unit": item.get("period_unit", "") or "",
        "class": "rate" if item.get("period_unit") else "count_only" if item.get("count") else "",
    }


def _gold_frequency_candidates(document_gold: Any) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add(parts: dict[str, str]) -> None:
        key = (
            parts.get("count", ""),
            parts.get("period_count", ""),
            parts.get("period_unit", ""),
            parts.get("class", ""),
        )
        if any(key) and key not in seen:
            seen.add(key)
            candidates.append(parts)

    for item in document_gold.seizure_frequencies:
        add(_frequency_parts(item))
        surface_parts = parse_frequency_expression(item.get("surface"))
        if surface_parts.get("class") not in {"", "unparsed"}:
            add(surface_parts)
    return candidates


def collect_support_claims(fields: dict[str, Any], document_gold: Any) -> list[SupportClaim]:
    """Return present extracted claims with field-level gold correctness flags."""
    claims: list[SupportClaim] = []
    gold_med_names = {_medication_name_tuple(item) for item in document_gold.medications}
    gold_med_full = {_medication_tuple(item) for item in document_gold.medications}

    for index, item in enumerate(fields.get("current_anti_seizure_medications", [])):
        if not isinstance(item, dict) or item.get("missingness") != "present":
            continue
        predicted_name = _medication_name_tuple(item)
        predicted_full = _medication_tuple(item)
        name_supported = predicted_name in gold_med_names
        full_supported = predicted_full in gold_med_full if any(predicted_full[1:]) else name_supported
        claims.append(
            SupportClaim(
                path=f"$.fields.current_anti_seizure_medications[{index}]",
                field="current_anti_seizure_medications",
                group="medications",
                value=predicted_full[0],
                supported_by_gold=name_supported and full_supported,
            )
        )

    gold_types = {canonical_seizure_type(item) for item in document_gold.seizure_types if item}
    for index, item in enumerate(fields.get("seizure_types", [])):
        if not isinstance(item, dict) or item.get("missingness") != "present":
            continue
        predicted = canonical_seizure_type(item.get("value"))
        claims.append(
            SupportClaim(
                path=f"$.fields.seizure_types[{index}]",
                field="seizure_types",
                group="diagnosis",
                value=predicted,
                supported_by_gold=bool(predicted and predicted in gold_types),
            )
        )

    frequency = fields.get("current_seizure_frequency", {})
    if isinstance(frequency, dict) and frequency.get("missingness") == "present":
        predicted_parts = parse_frequency_expression(normalize_value(frequency.get("value")))
        claims.append(
            SupportClaim(
                path="$.fields.current_seizure_frequency",
                field="current_seizure_frequency",
                group="seizure_frequency",
                value=normalize_value(frequency.get("value")),
                supported_by_gold=any(
                    frequency_loose_match(predicted_parts, item)
                    for item in _gold_frequency_candidates(document_gold)
                ),
            )
        )

    for field_name in ("eeg", "mri"):
        field = fields.get(field_name, {})
        if not isinstance(field, dict) or field.get("missingness") != "present":
            continue
        predicted = canonical_investigation_result(field.get("result"))
        gold = document_gold.investigations.get(field_name)
        claims.append(
            SupportClaim(
                path=f"$.fields.{field_name}",
                field=field_name,
                group=field_name,
                value=predicted,
                supported_by_gold=(predicted == gold) if gold else predicted in {"", "not stated", "none"},
            )
        )

    diagnosis = fields.get("epilepsy_diagnosis", {})
    if isinstance(diagnosis, dict) and diagnosis.get("missingness") == "present":
        predicted = canonical_diagnosis(diagnosis.get("value"))
        claims.append(
            SupportClaim(
                path="$.fields.epilepsy_diagnosis",
                field="epilepsy_diagnosis",
                group="diagnosis",
                value=predicted,
                supported_by_gold=any(predicted and (predicted in gold or gold in predicted) for gold in document_gold.diagnoses),
            )
        )
    return claims


def _field_evidence(fields: dict[str, Any], claim: SupportClaim) -> list[dict[str, Any]]:
    if claim.field == "current_anti_seizure_medications":
        index = int(claim.path.rsplit("[", 1)[1].split("]", 1)[0])
        raw = fields.get("current_anti_seizure_medications", [])[index].get("evidence")
    elif claim.field == "seizure_types":
        index = int(claim.path.rsplit("[", 1)[1].split("]", 1)[0])
        raw = fields.get("seizure_types", [])[index].get("evidence")
    else:
        raw = fields.get(claim.field, {}).get("evidence")
    return [item for item in raw or [] if isinstance(item, dict)]


def classify_evidence_support(
    fields: dict[str, Any],
    document_gold: Any,
    source_text: str,
) -> dict[str, Any]:
    """Classify evidence support separately from quote validity.

    Status meanings:
    - supported: valid quote overlaps relevant gold evidence and the extracted
      claim matches the gold label/value under current scorer rules.
    - contradicts_gold: valid quote overlaps relevant gold evidence, but the
      extracted claim does not match the gold label/value.
    - co_located: valid quote exists but does not overlap relevant gold evidence.
    - ambiguous: valid quote exists, but no gold evidence span exists for the
      field group, so automatic support cannot be adjudicated.
    - invalid_quote / no_quote: quote validity or presence failed before support
      can be assessed.
    """
    normalized_source = normalize_text(source_text)
    claims = collect_support_claims(fields, document_gold)
    rows: list[dict[str, Any]] = []
    status_counts = {
        "supported": 0,
        "contradicts_gold": 0,
        "co_located": 0,
        "ambiguous": 0,
        "invalid_quote": 0,
        "no_quote": 0,
    }

    for claim in claims:
        evidence = _field_evidence(fields, claim)
        spans = document_gold.spans_by_group.get(claim.group, [])
        if not evidence:
            status = "no_quote"
            valid_quote_count = 0
            overlap_count = 0
        else:
            valid_evidence = [
                item
                for item in evidence
                if isinstance(item.get("quote"), str) and normalize_text(item["quote"]) in normalized_source
            ]
            valid_quote_count = len(valid_evidence)
            overlap_count = sum(1 for item in valid_evidence if evidence_overlaps_gold(item, spans))
            if not valid_evidence:
                status = "invalid_quote"
            elif not spans:
                status = "ambiguous"
            elif overlap_count > 0 and claim.supported_by_gold:
                status = "supported"
            elif overlap_count > 0:
                status = "contradicts_gold"
            else:
                status = "co_located"
        status_counts[status] += 1
        rows.append(
            {
                "path": claim.path,
                "field": claim.field,
                "group": claim.group,
                "value": claim.value,
                "status": status,
                "supported_by_gold": claim.supported_by_gold,
                "evidence_count": len(evidence),
                "valid_quote_count": valid_quote_count,
                "gold_span_count": len(spans),
                "gold_overlap_count": overlap_count,
            }
        )

    evaluated = len(rows)
    supported = status_counts["supported"]
    decidable = evaluated - status_counts["ambiguous"]
    return {
        "claim_count": evaluated,
        "supported_count": supported,
        "decidable_claim_count": decidable,
        "support_rate": supported / evaluated if evaluated else 1.0,
        "decidable_support_rate": supported / decidable if decidable else None,
        "status_counts": status_counts,
        "claims": rows,
    }
