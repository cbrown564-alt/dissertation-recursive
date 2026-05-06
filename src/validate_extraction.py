#!/usr/bin/env python3
"""Validate and lightly score a canonical extraction JSON file.

This is the Milestone 1 executable contract. It intentionally covers the
project schema surface used by the sample output and the evidence checks that
can be scored without model or gold-loader infrastructure.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


MISSINGNESS = {"present", "not_stated", "uncertain", "conflicting", "not_applicable"}
TEMPORALITY = {
    "current",
    "historical",
    "planned",
    "requested",
    "completed",
    "family_history",
    "hypothetical",
    "uncertain",
}
MEDICATION_STATUS = {
    "current",
    "previous",
    "stopped",
    "declined",
    "planned",
    "increased",
    "reduced",
    "uncertain",
    "not_stated",
}
INVESTIGATION_STATUS = {"requested", "pending", "completed", "unavailable", "not_stated", "uncertain"}
INVESTIGATION_RESULT = {"normal", "abnormal", "not_stated", "uncertain", None}
EVENT_CATEGORY = {"medication", "seizure_frequency", "seizure_type", "investigation", "diagnosis"}
EVENT_STATUS = MEDICATION_STATUS | INVESTIGATION_STATUS | {None}


class ValidationError(Exception):
    pass


def normalize_text(value: str) -> str:
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return re.sub(r"\s+", " ", value).strip()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require_keys(obj: dict[str, Any], keys: list[str], path: str) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        raise ValidationError(f"{path} missing required keys: {', '.join(missing)}")


def require_enum(value: Any, allowed: set[Any], path: str) -> None:
    if value not in allowed:
        allowed_values = ", ".join(sorted(str(item) for item in allowed))
        raise ValidationError(f"{path} has invalid value {value!r}; expected one of {allowed_values}")


def validate_evidence(evidence: Any, path: str) -> None:
    if not isinstance(evidence, dict):
        raise ValidationError(f"{path} must be an object")
    require_keys(evidence, ["quote"], path)
    if not isinstance(evidence["quote"], str) or not evidence["quote"].strip():
        raise ValidationError(f"{path}.quote must be a non-empty string")
    for optional_key in ["sentence_id", "char_start", "char_end"]:
        if optional_key in evidence and evidence[optional_key] is not None:
            if optional_key == "sentence_id" and not isinstance(evidence[optional_key], str):
                raise ValidationError(f"{path}.{optional_key} must be string or null")
            if optional_key != "sentence_id" and not isinstance(evidence[optional_key], int):
                raise ValidationError(f"{path}.{optional_key} must be integer or null")


def validate_evidence_list(value: Any, missingness: str, path: str) -> None:
    if value is None:
        if missingness == "present":
            raise ValidationError(f"{path} cannot be null when missingness is present")
        return
    if not isinstance(value, list):
        raise ValidationError(f"{path} must be an array or null")
    if missingness == "present" and not value:
        raise ValidationError(f"{path} must not be empty when missingness is present")
    for index, item in enumerate(value):
        validate_evidence(item, f"{path}[{index}]")


def validate_scalar_field(field: Any, path: str) -> None:
    if not isinstance(field, dict):
        raise ValidationError(f"{path} must be an object")
    require_keys(field, ["value", "missingness", "temporality", "evidence", "evidence_event_ids"], path)
    require_enum(field["missingness"], MISSINGNESS, f"{path}.missingness")
    require_enum(field["temporality"], TEMPORALITY, f"{path}.temporality")
    validate_evidence_list(field["evidence"], field["missingness"], f"{path}.evidence")
    if not isinstance(field["evidence_event_ids"], list):
        raise ValidationError(f"{path}.evidence_event_ids must be an array")


def validate_medication_field(field: Any, path: str) -> None:
    if not isinstance(field, dict):
        raise ValidationError(f"{path} must be an object")
    require_keys(
        field,
        ["name", "dose", "dose_unit", "frequency", "status", "missingness", "temporality", "evidence", "evidence_event_ids"],
        path,
    )
    require_enum(field["status"], MEDICATION_STATUS, f"{path}.status")
    require_enum(field["missingness"], MISSINGNESS, f"{path}.missingness")
    require_enum(field["temporality"], TEMPORALITY, f"{path}.temporality")
    validate_evidence_list(field["evidence"], field["missingness"], f"{path}.evidence")


def validate_investigation_field(field: Any, path: str) -> None:
    if not isinstance(field, dict):
        raise ValidationError(f"{path} must be an object")
    require_keys(field, ["status", "result", "missingness", "temporality", "evidence", "evidence_event_ids"], path)
    require_enum(field["status"], INVESTIGATION_STATUS, f"{path}.status")
    require_enum(field["result"], INVESTIGATION_RESULT, f"{path}.result")
    require_enum(field["missingness"], MISSINGNESS, f"{path}.missingness")
    require_enum(field["temporality"], TEMPORALITY, f"{path}.temporality")
    validate_evidence_list(field["evidence"], field["missingness"], f"{path}.evidence")


def validate_seizure_frequency_field(field: Any, path: str) -> None:
    validate_scalar_field(field, path)
    require_keys(field, ["temporal_scope", "seizure_type"], path)


def validate_event(event: Any, path: str) -> None:
    if not isinstance(event, dict):
        raise ValidationError(f"{path} must be an object")
    require_keys(event, ["id", "category", "temporality", "status", "value", "evidence"], path)
    if not isinstance(event["id"], str) or not event["id"].strip():
        raise ValidationError(f"{path}.id must be a non-empty string")
    require_enum(event["category"], EVENT_CATEGORY, f"{path}.category")
    require_enum(event["temporality"], TEMPORALITY, f"{path}.temporality")
    require_enum(event["status"], EVENT_STATUS, f"{path}.status")
    validate_evidence(event["evidence"], f"{path}.evidence")


def validate_extraction(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValidationError("top-level extraction must be an object")
    require_keys(data, ["document_id", "pipeline_id", "fields", "events", "metadata"], "$")

    fields = data["fields"]
    if not isinstance(fields, dict):
        raise ValidationError("$.fields must be an object")
    require_keys(
        fields,
        [
            "current_anti_seizure_medications",
            "previous_anti_seizure_medications",
            "current_seizure_frequency",
            "seizure_types",
            "eeg",
            "mri",
            "epilepsy_diagnosis",
        ],
        "$.fields",
    )

    for collection_name in ["current_anti_seizure_medications", "previous_anti_seizure_medications"]:
        collection = fields[collection_name]
        if not isinstance(collection, list):
            raise ValidationError(f"$.fields.{collection_name} must be an array")
        for index, item in enumerate(collection):
            validate_medication_field(item, f"$.fields.{collection_name}[{index}]")

    validate_seizure_frequency_field(fields["current_seizure_frequency"], "$.fields.current_seizure_frequency")
    for index, item in enumerate(fields["seizure_types"]):
        validate_scalar_field(item, f"$.fields.seizure_types[{index}]")
    validate_investigation_field(fields["eeg"], "$.fields.eeg")
    validate_investigation_field(fields["mri"], "$.fields.mri")
    validate_scalar_field(fields["epilepsy_diagnosis"], "$.fields.epilepsy_diagnosis")

    if not isinstance(data["events"], list):
        raise ValidationError("$.events must be an array")
    event_ids = set()
    for index, event in enumerate(data["events"]):
        validate_event(event, f"$.events[{index}]")
        if event["id"] in event_ids:
            raise ValidationError(f"duplicate event id: {event['id']}")
        event_ids.add(event["id"])


def iter_evidence(data: Any) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if "quote" in value and isinstance(value["quote"], str):
                found.append((path, value["quote"]))
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(data, "$")
    return found


def check_quote_validity(data: Any, source_text: str) -> tuple[int, list[str]]:
    normalized_source = normalize_text(source_text)
    failures = []
    total = 0
    for path, quote in iter_evidence(data):
        total += 1
        if normalize_text(quote) not in normalized_source:
            failures.append(path)
    return total, failures


def resolve_path(data: Any, path: str) -> Any:
    current = data["fields"]
    for part in path.split("."):
        match = re.fullmatch(r"([A-Za-z0-9_]+)(?:\[(\d+)])?", part)
        if not match:
            raise ValidationError(f"unsupported expectation path: {path}")
        key, index = match.groups()
        current = current[key]
        if index is not None:
            current = current[int(index)]
    return current


def score_expectations(data: Any, expectations: Any) -> tuple[int, list[str]]:
    field_expectations = expectations.get("field_expectations", {})
    failures = []
    for path, expected in field_expectations.items():
        actual = resolve_path(data, path)
        if normalize_text(str(actual)).lower() != normalize_text(str(expected)).lower():
            failures.append(f"{path}: expected {expected!r}, got {actual!r}")
    return len(field_expectations), failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extraction", type=Path)
    parser.add_argument("--source", type=Path, required=True, help="Source clinic letter for quote validation.")
    parser.add_argument("--expectations", type=Path, help="Manual field expectations for sample scoring.")
    args = parser.parse_args()

    data = load_json(args.extraction)
    source_text = args.source.read_text(encoding="utf-8")

    try:
        validate_extraction(data)
        quote_total, quote_failures = check_quote_validity(data, source_text)
        if quote_failures:
            raise ValidationError("invalid evidence quotes at: " + ", ".join(quote_failures))

        print(f"schema_validation: pass")
        print(f"quote_presence: pass ({quote_total} quotes)")
        print(f"quote_validity: pass ({quote_total}/{quote_total})")

        if args.expectations:
            expectations = load_json(args.expectations)
            field_total, field_failures = score_expectations(data, expectations)
            if field_failures:
                raise ValidationError("field expectation failures:\n- " + "\n- ".join(field_failures))
            print(f"field_correctness: pass ({field_total}/{field_total})")
        else:
            print("field_correctness: skipped (no expectations file)")

        print("milestone_1_exit_check: pass")
        return 0
    except ValidationError as exc:
        print(f"milestone_1_exit_check: fail\n{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
