from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from collections.abc import Iterable


SCHEMA_VERSION = "1.0.0"


class FieldFamily(str, Enum):
    SEIZURE_FREQUENCY = "seizure_frequency"
    CURRENT_MEDICATIONS = "current_medications"
    INVESTIGATIONS = "investigations"
    SEIZURE_CLASSIFICATION = "seizure_classification"
    EPILEPSY_CLASSIFICATION = "epilepsy_classification"
    RESCUE_MEDICATION = "rescue_medication"
    OTHER_THERAPIES = "other_therapies"
    COMORBIDITIES = "comorbidities"
    ASSOCIATED_SYMPTOMS = "associated_symptoms"


CORE_FIELD_FAMILIES: tuple[FieldFamily, ...] = (
    FieldFamily.SEIZURE_FREQUENCY,
    FieldFamily.CURRENT_MEDICATIONS,
    FieldFamily.INVESTIGATIONS,
    FieldFamily.SEIZURE_CLASSIFICATION,
    FieldFamily.EPILEPSY_CLASSIFICATION,
)


class ArchitectureFamily(str, Enum):
    CLINICAL_NLP_BASELINE = "clinical_nlp_baseline"
    DIRECT_LLM = "direct_llm"
    RETRIEVAL_FIELD_PIPELINE = "retrieval_field_pipeline"
    CLINES_INSPIRED_MODULAR = "clines_inspired_modular"
    COSTED_RELIABILITY_VARIANT = "costed_reliability_variant"


class FieldCoverageStatus(str, Enum):
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    NOT_IMPLEMENTED = "not_implemented"
    NOT_ATTEMPTED = "not_attempted"
    FAILED = "failed"


class EvidenceGrade(str, Enum):
    EXACT_SPAN = "exact_span"
    OVERLAPPING_SPAN = "overlapping_span"
    SECTION_LEVEL = "section_level"
    WRONG_TEMPORAL_STATUS = "wrong_temporal_status"
    UNSUPPORTED = "unsupported"
    MISSING_EVIDENCE = "missing_evidence"


@dataclass(frozen=True)
class SupportAssessment:
    grade: EvidenceGrade
    warnings: list[str] = field(default_factory=list)

    @property
    def full_credit(self) -> bool:
        return self.grade in {
            EvidenceGrade.EXACT_SPAN,
            EvidenceGrade.OVERLAPPING_SPAN,
        }


def empty_field_coverage() -> dict[str, str]:
    return {
        field.value: FieldCoverageStatus.NOT_IMPLEMENTED.value
        for field in FieldFamily
    }


def field_coverage(
    implemented: Iterable[FieldFamily | str] = (),
    partial: Iterable[FieldFamily | str] = (),
    failed: Iterable[FieldFamily | str] = (),
) -> dict[str, str]:
    coverage = empty_field_coverage()
    for field in implemented:
        coverage[_field_value(field)] = FieldCoverageStatus.IMPLEMENTED.value
    for field in partial:
        coverage[_field_value(field)] = FieldCoverageStatus.PARTIAL.value
    for field in failed:
        coverage[_field_value(field)] = FieldCoverageStatus.FAILED.value
    return coverage


def not_attempted_coverage() -> dict[str, str]:
    return {f.value: FieldCoverageStatus.NOT_ATTEMPTED.value for f in FieldFamily}


def full_contract_coverage() -> dict[str, str]:
    return field_coverage(implemented=FieldFamily)


def partial_contract_coverage(fields: Iterable[FieldFamily | str]) -> dict[str, str]:
    return field_coverage(partial=fields)


def failed_component_coverage(fields: Iterable[FieldFamily | str]) -> dict[str, str]:
    return field_coverage(failed=fields)


def _field_value(field: FieldFamily | str) -> str:
    value = field.value if isinstance(field, FieldFamily) else field
    FieldFamily(value)
    return value
