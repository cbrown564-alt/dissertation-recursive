from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from epilepsy_extraction.providers import (
    ChatProvider,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
)
from epilepsy_extraction.schemas.contracts import FieldFamily


FIELD_FAMILY_KEYS: dict[FieldFamily, list[str]] = {
    FieldFamily.SEIZURE_FREQUENCY: ["seizure_frequency"],
    FieldFamily.CURRENT_MEDICATIONS: ["current_medications"],
    FieldFamily.INVESTIGATIONS: ["investigations"],
    FieldFamily.SEIZURE_CLASSIFICATION: ["seizure_types", "seizure_features", "seizure_pattern_modifiers"],
    FieldFamily.EPILEPSY_CLASSIFICATION: ["epilepsy_type", "epilepsy_syndrome"],
}


@dataclass(frozen=True)
class FieldExtractionResult:
    family: FieldFamily
    data: dict[str, Any]
    valid: bool
    warnings: list[str] = field(default_factory=list)
    response: ProviderResponse | None = None


def extract_field_family(
    provider: ChatProvider,
    prompt_text: str,
    schema: dict[str, Any],
    family: FieldFamily,
    context: str,
    model: str,
    temperature: float,
) -> FieldExtractionResult:
    """Extract one field family from section-aware context using the provider."""
    keys = FIELD_FAMILY_KEYS.get(family, [])
    schema_properties = schema.get("properties", {})
    field_schema = {k: schema_properties.get(k, {}) for k in keys}
    content = (
        f"{prompt_text}\n\n"
        f"Field family: {family.value}\n"
        f"Target fields: {', '.join(keys)}\n"
        f"Field schema: {json.dumps(field_schema, sort_keys=True)}\n\n"
        f"Section-aware context:\n{context}"
    )
    response = provider.complete(
        ProviderRequest(
            messages=[ProviderMessage(role="user", content=content)],
            model=model,
            temperature=temperature,
            response_format="json",
            metadata={"prompt_id": "clines_field_extractor", "field_family": family.value},
        )
    )
    if not response.ok:
        return FieldExtractionResult(
            family=family,
            data={},
            valid=False,
            warnings=["provider_error"],
            response=response,
        )
    try:
        data = json.loads(response.content)
    except json.JSONDecodeError:
        return FieldExtractionResult(
            family=family,
            data={},
            valid=False,
            warnings=["json_parse_error"],
            response=response,
        )
    parsed: dict[str, Any] = {k: data[k] for k in keys if k in data}
    valid = bool(parsed)
    for shared_key in ("citations", "confidence", "warnings"):
        if shared_key in data:
            parsed[shared_key] = data[shared_key]
    parsed["citations"] = _normalize_citations(parsed)
    return FieldExtractionResult(
        family=family,
        data=parsed,
        valid=valid,
        warnings=[],
        response=response,
    )


def _normalize_citations(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    existing = parsed.get("citations")
    if isinstance(existing, list):
        citations.extend(c for c in existing if isinstance(c, dict))

    for field_name, value in parsed.items():
        if field_name in {"citations", "confidence", "warnings"}:
            continue
        citations.extend(_evidence_citations(field_name, value))

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for citation in citations:
        key = (citation.get("field"), citation.get("quote"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(citation)
    return deduped


def _evidence_citations(field_name: str, value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        quote = value.get("evidence")
        return [_citation(field_name, quote)] if isinstance(quote, str) and quote.strip() else []
    if isinstance(value, list):
        citations: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            quote = item.get("evidence")
            if isinstance(quote, str) and quote.strip():
                citations.append(_citation(field_name, quote))
        return citations
    return []


def _citation(field_name: str, quote: str) -> dict[str, Any]:
    return {"field": field_name, "quote": quote}
