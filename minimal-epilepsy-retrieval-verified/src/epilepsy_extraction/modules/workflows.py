from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from epilepsy_extraction.schemas.contracts import CORE_FIELD_FAMILIES, FieldFamily


WORKFLOW_VERSION = "1.0.0"


@dataclass(frozen=True)
class WorkflowContract:
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowUnit:
    name: str
    version: str
    role: str
    field_family: str = ""
    contract: WorkflowContract = field(default_factory=WorkflowContract)
    hooks: list[str] = field(default_factory=list)

    @property
    def unit_id(self) -> str:
        suffix = f".{self.field_family}" if self.field_family else ""
        return f"{self.name}{suffix}@{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "name": self.name,
            "version": self.version,
            "role": self.role,
            "field_family": self.field_family,
            "contract": self.contract.to_dict(),
            "hooks": list(self.hooks),
        }


def field_extractor_unit(field_family: FieldFamily | str) -> WorkflowUnit:
    family = field_family.value if isinstance(field_family, FieldFamily) else str(field_family)
    return WorkflowUnit(
        name="field_extractor",
        version=WORKFLOW_VERSION,
        role="extract_field_family",
        field_family=family,
        contract=WorkflowContract(
            inputs=["field_family", "candidate_context", "schema_fragment"],
            outputs=["field_payload", "citations", "confidence", "warnings"],
            invariants=["may not read gold labels", "may not emit fields outside declared family"],
        ),
        hooks=["parse_json", "normalize_citations", "warning_emission"],
    )


def normalizer_unit() -> WorkflowUnit:
    return WorkflowUnit(
        name="deterministic_normalizer",
        version=WORKFLOW_VERSION,
        role="normalize_values",
        contract=WorkflowContract(
            inputs=["field_payload"],
            outputs=["normalized_values", "unit_metadata"],
            invariants=["normalization must not create new clinical claims"],
        ),
        hooks=["deterministic_normalization"],
    )


def verifier_unit(provider_backed: bool = False) -> WorkflowUnit:
    return WorkflowUnit(
        name="provider_verifier" if provider_backed else "deterministic_verifier",
        version=WORKFLOW_VERSION,
        role="verify_evidence",
        contract=WorkflowContract(
            inputs=["field_payload", "source_context"],
            outputs=["evidence_grade", "support_warnings"],
            invariants=["verification grades support; it does not adjudicate correctness"],
        ),
        hooks=["evidence_validation", "warning_emission"],
    )


def aggregator_unit() -> WorkflowUnit:
    return WorkflowUnit(
        name="schema_aggregator",
        version=WORKFLOW_VERSION,
        role="aggregate_final_payload",
        contract=WorkflowContract(
            inputs=["field_family_payloads"],
            outputs=["final_extraction_payload", "aggregation_conflicts"],
            invariants=["aggregator must not invent missing clinical claims"],
        ),
        hooks=["conflict_detection", "schema_adaptation", "warning_emission"],
    )


def modular_workflow_units(*, provider_verifier: bool = False) -> list[WorkflowUnit]:
    units = [field_extractor_unit(family) for family in CORE_FIELD_FAMILIES]
    units.extend([normalizer_unit(), verifier_unit(provider_verifier), aggregator_unit()])
    return units


def workflow_unit_dicts(units: list[WorkflowUnit]) -> list[dict[str, Any]]:
    return [unit.to_dict() for unit in units]
