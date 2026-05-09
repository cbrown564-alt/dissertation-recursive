from __future__ import annotations

from enum import Enum

from epilepsy_extraction.schemas.contracts import FieldFamily


FIELD_FAMILY_TO_SCHEMA_KEYS: dict[FieldFamily, list[str]] = {
    FieldFamily.SEIZURE_FREQUENCY: ["seizure_frequency"],
    FieldFamily.CURRENT_MEDICATIONS: ["current_medications"],
    FieldFamily.INVESTIGATIONS: ["investigations"],
    FieldFamily.SEIZURE_CLASSIFICATION: [
        "seizure_types",
        "seizure_features",
        "seizure_pattern_modifiers",
    ],
    FieldFamily.EPILEPSY_CLASSIFICATION: ["epilepsy_type", "epilepsy_syndrome"],
    FieldFamily.RESCUE_MEDICATION: [],
    FieldFamily.OTHER_THERAPIES: [],
    FieldFamily.COMORBIDITIES: [],
    FieldFamily.ASSOCIATED_SYMPTOMS: [],
}

SCHEMA_KEY_TO_FIELD_FAMILY: dict[str, FieldFamily] = {
    key: family
    for family, keys in FIELD_FAMILY_TO_SCHEMA_KEYS.items()
    for key in keys
}

LITERATURE_ALIGNED_NAMES: dict[FieldFamily, str] = {
    FieldFamily.SEIZURE_FREQUENCY: "Seizure frequency",
    FieldFamily.CURRENT_MEDICATIONS: "Current anti-seizure medications",
    FieldFamily.INVESTIGATIONS: "Investigations",
    FieldFamily.SEIZURE_CLASSIFICATION: "Seizure type, semiology, and pattern modifiers",
    FieldFamily.EPILEPSY_CLASSIFICATION: "Epilepsy type and syndrome",
    FieldFamily.RESCUE_MEDICATION: "Rescue medication",
    FieldFamily.OTHER_THERAPIES: "Other therapies",
    FieldFamily.COMORBIDITIES: "Comorbidities",
    FieldFamily.ASSOCIATED_SYMPTOMS: "Associated symptoms",
}


class ErrorTag(str, Enum):
    WRONG_VALUE = "wrong_value"
    WRONG_STATUS = "wrong_status"
    WRONG_TEMPORALITY = "wrong_temporality"
    WRONG_NORMALIZATION = "wrong_normalization"
    UNSUPPORTED_EVIDENCE = "unsupported_evidence"
    RETRIEVAL_RECALL_LOSS = "retrieval_recall_loss"
    AGGREGATION_CONFLICT = "aggregation_conflict"
    BASELINE_MAPPING_ERROR = "baseline_mapping_error"
    PARSE_FAILURE = "parse_failure"
    ABSTENTION = "abstention"


def field_family_for_schema_key(key: str) -> FieldFamily | None:
    return SCHEMA_KEY_TO_FIELD_FAMILY.get(key)


def literature_name(family: FieldFamily) -> str:
    return LITERATURE_ALIGNED_NAMES.get(family, family.value)
