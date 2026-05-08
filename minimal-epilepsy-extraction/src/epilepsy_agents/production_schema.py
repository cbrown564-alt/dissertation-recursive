"""Production multi-agent schema, prompts, and parsers.

This module defines the JSON contracts for the faithful role-based extractor:
field-specific extraction calls feed a verifier and aggregator rather than one
large joint prompt.
"""

from __future__ import annotations

import json
from typing import Any

from .structured_schema import extract_json_object


EPILEPSY_CLASSIFICATION_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epilepsy_type", "epilepsy_syndrome"],
    "properties": {
        "epilepsy_type": {
            "type": "object",
            "additionalProperties": False,
            "required": ["value", "evidence", "confidence"],
            "properties": {
                "value": {"type": "string"},
                "evidence": {"type": "string"},
                "confidence": {"type": "number"},
            },
        },
        "epilepsy_syndrome": {
            "type": "object",
            "additionalProperties": False,
            "required": ["value", "evidence", "confidence"],
            "properties": {
                "value": {"type": "string"},
                "evidence": {"type": "string"},
                "confidence": {"type": "number"},
            },
        },
    },
}


def classification_system_prompt() -> str:
    return (
        "/no_think\n"
        "You extract epilepsy classification fields from synthetic clinic letters. "
        "Return only JSON conforming to the supplied schema. Quote evidence exactly "
        "when a field is supported. Use value 'unknown' and empty evidence when the "
        "letter does not explicitly support the field."
    )


def classification_user_prompt(letter: str) -> str:
    return (
        "Extract epilepsy_type and epilepsy_syndrome from this synthetic epilepsy clinic letter.\n\n"
        "epilepsy_type: use the explicit stated epilepsy type where present, for example "
        "focal epilepsy, generalized epilepsy, combined generalized and focal epilepsy, "
        "unknown epilepsy type, or non-epileptic attack disorder. Do not infer type from "
        "medication, investigation choice, or semiology alone.\n\n"
        "epilepsy_syndrome: use the explicit syndrome name where present, for example "
        "juvenile myoclonic epilepsy, Dravet syndrome, Lennox-Gastaut syndrome, or "
        "unknown. Do not invent a syndrome from seizure type descriptions.\n\n"
        "Each field must be an object with keys value, evidence, confidence. Quote the "
        "shortest useful evidence span. Return unknown with empty evidence when absent.\n\n"
        f"Letter:\n{letter}"
    )


def parse_classification_response(content: str) -> dict[str, Any]:
    try:
        payload = json.loads(extract_json_object(content))
        return {
            "epilepsy_type": _parse_classification_field(payload.get("epilepsy_type", {})),
            "epilepsy_syndrome": _parse_classification_field(payload.get("epilepsy_syndrome", {})),
            "invalid_output": False,
        }
    except Exception:
        return {
            "epilepsy_type": {"value": "unknown", "evidence": "", "confidence": 0.0},
            "epilepsy_syndrome": {"value": "unknown", "evidence": "", "confidence": 0.0},
            "invalid_output": True,
        }


def _parse_classification_field(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"value": "unknown", "evidence": "", "confidence": 0.0}
    return {
        "value": str(value.get("value", "unknown")).strip() or "unknown",
        "evidence": str(value.get("evidence", "")),
        "confidence": float(value.get("confidence", 0.0)),
    }
