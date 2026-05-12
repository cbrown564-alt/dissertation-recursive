#!/usr/bin/env python3
"""Archived dashboard prototype exporter.

Retained for the original aggregate-results dashboard. The active audit
workbench is ExECT Explorer; model overlay exports are documented in
``docs/55_exect_explorer_data_contract.md`` and routed in
``docs/56_archival_entrypoints.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


DEFAULT_OUTPUT = Path("dashboard/public/data/dashboard_data.json")
ARCHIVAL_STATUS = "archived_dashboard_prototype"
MAINTAINED_ENTRYPOINT = "exect-explorer/scripts/build_model_overlay.py"
SCHEMA_PATH = Path("schemas/dashboard_data.schema.json")
DASHBOARD_SCHEMA_VERSION = "1.0.0"
EXPORTER_VERSION = "1.0.0"
SYSTEMS = [
    {"id": "S2", "label": "Direct JSON", "color": "#07858c"},
    {"id": "E2", "label": "Event-first aggregate", "color": "#2878d8"},
    {"id": "E3", "label": "Constrained aggregate", "color": "#f26d2b"},
]
FIELD_METRICS = [
    ("medication", "medication_full_f1"),
    ("seizure type", "seizure_type_f1"),
    ("seizure frequency", "current_seizure_frequency_accuracy"),
    ("EEG", "eeg_accuracy"),
    ("MRI", "mri_accuracy"),
    ("diagnosis", "epilepsy_diagnosis_accuracy"),
]
KPI_METRICS = [
    ("field_accuracy", "Field accuracy", "field_accuracy"),
    ("temporal_correctness", "Temporal correctness", "temporal_accuracy"),
    ("evidence_validity", "Evidence validity", "quote_validity_rate"),
    ("schema_validity", "Schema validity", "schema_valid_rate"),
    ("parse_repair", "Parse / repair", "parse_success_rate"),
    ("robustness_degradation", "Robustness degradation", "robustness_degradation"),
]


def read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def artifact_kind(path: Path) -> str:
    if path.is_dir():
        return "directory"
    suffix = path.suffix.lower()
    if suffix in {".json", ".jsonl", ".csv"}:
        return suffix[1:]
    return "other"


def artifact_row_count(path: Path) -> int | None:
    if not path.exists() or path.is_dir():
        return None
    if path.suffix.lower() == ".csv":
        return len(read_csv(path))
    if path.suffix.lower() == ".jsonl":
        return len(read_jsonl(path))
    if path.suffix.lower() == ".json":
        data = read_json(path)
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return len(data)
    return None


def artifact_record(artifact_id: str, path: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        "id": artifact_id,
        "path": str(path),
        "exists": exists,
        "kind": artifact_kind(path),
        "size_bytes": path.stat().st_size if exists and path.is_file() else None,
        "row_count": artifact_row_count(path),
    }


def build_artifacts(evaluation_dir: Path, robustness_dir: Path, direct_dir: Path, event_dir: Path, secondary_dirs: list[Path]) -> list[dict[str, Any]]:
    records = [
        artifact_record("evaluation_summary", evaluation_dir / "evaluation_summary.json"),
        artifact_record("comparison_table", evaluation_dir / "comparison_table.csv"),
        artifact_record("document_scores", evaluation_dir / "document_scores.json"),
        artifact_record("robustness_summary", robustness_dir / "robustness_summary.json"),
        artifact_record("label_preserving_degradation", robustness_dir / "label_preserving_degradation.csv"),
        artifact_record("label_changing_validity", robustness_dir / "label_changing_validity.json"),
        artifact_record("direct_run_log", direct_dir / "baseline_runs.jsonl"),
        artifact_record("event_run_log", event_dir / "event_first_runs.jsonl"),
    ]
    for index, directory in enumerate(secondary_dirs, start=1):
        records.extend(
            [
                artifact_record(f"secondary_{index}_json_yaml_table", directory / "json_yaml_comparison_table.csv"),
                artifact_record(f"secondary_{index}_model_comparison_table", directory / "model_comparison_table.csv"),
            ]
        )
    return records


def as_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def mean(values: list[float | None]) -> float | None:
    numeric = [value for value in values if value is not None]
    return sum(numeric) / len(numeric) if numeric else None


def metric(summary_by_system: dict[str, dict[str, Any]], system: str, key: str) -> float | None:
    return as_number(summary_by_system.get(system, {}).get(key))


def read_evaluation_summaries(evaluation_dir: Path, secondary_dirs: list[Path]) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for row in read_csv(evaluation_dir / "comparison_table.csv"):
        system = row.get("system")
        if system:
            summaries.setdefault(system, {}).update(row)

    for directory in secondary_dirs:
        for row in read_csv(directory / "json_yaml_comparison_table.csv"):
            system = row.get("system")
            if system:
                summaries.setdefault(system, {}).update({key: value for key, value in row.items() if value not in {None, ""}})
        for row in read_csv(directory / "model_comparison_table.csv"):
            system = row.get("system") or row.get("condition")
            if system and system in {"S2", "E2", "E3"}:
                summaries.setdefault(system, {}).update({key: value for key, value in row.items() if value not in {None, ""}})
    return summaries


def build_kpis(summary_by_system: dict[str, dict[str, Any]], robustness_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    robustness_by_system = {
        system["id"]: mean(
            [
                as_number(row.get("delta_medication_full_f1"))
                or as_number(row.get("delta_current_seizure_frequency_accuracy"))
                or as_number(row.get("delta_quote_validity_rate"))
                for row in robustness_rows
                if row.get("system") == system["id"]
            ]
        )
        for system in SYSTEMS
    }

    cards = []
    for card_id, label, key in KPI_METRICS:
        values = {}
        missingness = {}
        for system in SYSTEMS:
            system_id = system["id"]
            if key == "field_accuracy":
                values[system_id] = mean([metric(summary_by_system, system_id, metric_key) for _, metric_key in FIELD_METRICS])
            elif key == "robustness_degradation":
                values[system_id] = robustness_by_system[system_id]
            else:
                values[system_id] = metric(summary_by_system, system_id, key)
            if values[system_id] is None:
                missingness[system_id] = "no_clean_baseline" if key == "robustness_degradation" else "unavailable_metric"
        cards.append({"id": card_id, "label": label, "values": values, "missingness": missingness})
    return cards


def build_field_accuracy(summary_by_system: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for label, key in FIELD_METRICS:
        values = {system["id"]: metric(summary_by_system, system["id"], key) for system in SYSTEMS}
        rows.append(
            {
                "field": label,
                "values": values,
                "missingness": {
                    system_id: "unavailable_metric"
                    for system_id, value in values.items()
                    if value is None
                },
            }
        )
    return rows


def build_schema_breakdown(summary_by_system: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for system in SYSTEMS:
        valid = metric(summary_by_system, system["id"], "schema_valid_rate")
        if valid is None:
            continue
        invalid = max(0.0, 1.0 - valid)
        rows.append(
            {
                "system": system["id"],
                "valid": valid,
                "minor": invalid * 0.65,
                "major": invalid * 0.35,
            }
        )
    return rows


def build_robustness(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_perturbation: dict[str, dict[str, Any]] = {}
    for row in rows:
        perturbation = row.get("perturbation_id")
        system = row.get("system")
        if not perturbation or not system:
            continue
        value = (
            as_number(row.get("delta_medication_full_f1"))
            or as_number(row.get("delta_current_seizure_frequency_accuracy"))
            or as_number(row.get("delta_schema_valid_rate"))
        )
        by_perturbation.setdefault(perturbation, {"perturbation": perturbation, "values": {}})
        by_perturbation[perturbation]["values"][system] = value
    output = []
    for row in by_perturbation.values():
        missingness = {}
        for system in SYSTEMS:
            if row["values"].get(system["id"]) is None:
                missingness[system["id"]] = "no_clean_baseline"
        row["missingness"] = missingness
        output.append(row)
    return output


def read_parse_logs(log_paths: list[Path]) -> dict[str, dict[str, float | int]]:
    counts: dict[str, dict[str, float | int]] = {}
    for path in log_paths:
        for row in read_jsonl(path):
            system = row.get("baseline") or row.get("pipeline")
            if system not in {"S2", "E2", "E3"}:
                continue
            parse = row.get("parse") if isinstance(row.get("parse"), dict) else {}
            counts.setdefault(system, {"records": 0, "parse_success": 0, "repair_attempted": 0, "repair_succeeded": 0})
            counts[system]["records"] += 1
            counts[system]["parse_success"] += 1 if parse.get("parse_success") else 0
            counts[system]["repair_attempted"] += 1 if parse.get("repair_attempted") else 0
            counts[system]["repair_succeeded"] += 1 if parse.get("repair_succeeded") else 0
    return counts


def build_format_comparison(secondary_dirs: list[Path]) -> dict[str, Any]:
    rows = []
    for directory in secondary_dirs:
        rows.extend(read_csv(directory / "json_yaml_comparison_table.csv"))
    json_row = next((row for row in rows if row.get("system") == "S2"), {})
    yaml_row = next((row for row in rows if row.get("system") == "S3"), {})
    metrics = [
        ("field accuracy", "medication_full_f1"),
        ("temporal", "temporal_accuracy"),
        ("evidence", "quote_validity_rate"),
        ("schema", "schema_valid_rate"),
        ("parse", "parse_success_rate"),
    ]
    return {
        "metrics": [
            {
                "metric": label,
                "json": as_number(json_row.get(key)),
                "yaml": as_number(yaml_row.get(key)),
            }
            for label, key in metrics
        ],
        "mean": {
            "json": mean([as_number(json_row.get(key)) for _, key in metrics]),
            "yaml": mean([as_number(yaml_row.get(key)) for _, key in metrics]),
        },
    }


def build_model_family(secondary_dirs: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for directory in secondary_dirs:
        rows.extend(read_csv(directory / "model_comparison_table.csv"))
    output = []
    for row in rows:
        output.append(
            {
                "condition": row.get("condition"),
                "family": row.get("family"),
                "system": row.get("system"),
                "field_accuracy": mean([as_number(row.get(key)) for _, key in FIELD_METRICS]),
                "temporal_correctness": as_number(row.get("temporal_accuracy")),
                "evidence_validity": as_number(row.get("quote_validity_rate")),
                "schema_validity": as_number(row.get("schema_valid_rate")),
                "parse_repair": as_number(row.get("parse_success_rate")),
            }
        )
    return output


def field_issue_summary(score: dict[str, Any]) -> list[str]:
    issues = []
    for field, field_score in score.get("field_scores", {}).items():
        if isinstance(field_score, dict) and field_score.get("correct") is False:
            issues.append(field)
        elif isinstance(field_score, dict) and (field_score.get("fp") or field_score.get("fn")):
            issues.append(field)
    return issues


def build_documents(document_scores: Any, limit: int = 20) -> list[dict[str, Any]]:
    if not isinstance(document_scores, dict):
        return []
    rows = []
    for system, scores in document_scores.items():
        if not isinstance(scores, list):
            continue
        for score in scores:
            if not isinstance(score, dict):
                continue
            rows.append(
                {
                    "system": system,
                    "document_id": score.get("document_id"),
                    "schema_valid": bool(score.get("schema_valid")),
                    "quote_validity": score.get("quote_validity", {}).get("rate"),
                    "temporal_accuracy": score.get("temporal_scores", {}).get("accuracy"),
                    "issues": field_issue_summary(score),
                    "errors": score.get("errors", []),
                }
            )
    return rows[:limit]


def extract_evidence_from_canonical(path: Path, system: str, document_id: str) -> list[dict[str, Any]]:
    data = read_json(path)
    if not isinstance(data, dict):
        return []
    examples = []

    def visit(value: Any, field: str) -> None:
        if isinstance(value, dict):
            evidence = value.get("evidence")
            if isinstance(evidence, list):
                for item in evidence:
                    if isinstance(item, dict) and item.get("quote"):
                        examples.append(
                            {
                                "system": system,
                                "document_id": document_id,
                                "field": field,
                                "quote": item.get("quote"),
                                "char_start": item.get("char_start"),
                                "char_end": item.get("char_end"),
                            }
                        )
            for key, child in value.items():
                visit(child, key)
        elif isinstance(value, list):
            for child in value:
                visit(child, field)

    visit(data.get("fields", {}), "fields")
    return examples


def build_evidence_examples(direct_dir: Path, event_dir: Path, document_scores: Any) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    document_ids = []
    if isinstance(document_scores, dict):
        for scores in document_scores.values():
            if isinstance(scores, list):
                document_ids.extend(score.get("document_id") for score in scores if isinstance(score, dict))
    for document_id in sorted({item for item in document_ids if isinstance(item, str)}):
        examples.extend(extract_evidence_from_canonical(direct_dir / "S2" / document_id / "canonical.json", "S2", document_id))
        examples.extend(extract_evidence_from_canonical(event_dir / document_id / "e2_canonical.json", "E2", document_id))
        examples.extend(extract_evidence_from_canonical(event_dir / document_id / "e3_canonical.json", "E3", document_id))
    if examples:
        return examples[:8]
    return [
        {
            "system": "E2",
            "document_id": "example",
            "field": "evidence",
            "quote": "No evidence quotes were available in the selected smoke artifacts.",
            "char_start": None,
            "char_end": None,
        }
    ]


def missingness_from_bundle(data: dict[str, Any]) -> dict[str, str]:
    missing: dict[str, str] = {}
    for artifact in data["meta"]["artifacts"]:
        if not artifact["exists"]:
            missing[f"artifact:{artifact['id']}"] = "missing_artifact"
    for card in data["kpis"]:
        for system, reason in card.get("missingness", {}).items():
            missing[f"kpis.{card['id']}.{system}"] = reason
    for row in data["field_accuracy"]:
        for system, reason in row.get("missingness", {}).items():
            missing[f"field_accuracy.{row['field']}.{system}"] = reason
    for row in data["robustness"]:
        for system, reason in row.get("missingness", {}).items():
            missing[f"robustness.{row['perturbation']}.{system}"] = reason
    if not data["model_family"]:
        missing["model_family"] = "unsupported_analysis"
    if not data["robustness"]:
        missing["robustness"] = "missing_artifact"
    return missing


def validate_dashboard_data(data: Any, schema_path: Path = SCHEMA_PATH) -> list[str]:
    schema = read_json(schema_path)
    if not isinstance(schema, dict):
        return [f"schema not found or unreadable: {schema_path}"]
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        location = "/" + "/".join(str(part) for part in error.path) if error.path else "<root>"
        errors.append(f"{location}: {error.message}")
    return errors


def command_build(args: argparse.Namespace) -> int:
    evaluation_dir = Path(args.evaluation_dir)
    robustness_dir = Path(args.robustness_dir)
    direct_dir = Path(args.direct_run_dir)
    event_dir = Path(args.event_run_dir)
    secondary_dirs = [Path(item) for item in args.secondary_dir]
    output_path = Path(args.output)

    summary_by_system = read_evaluation_summaries(evaluation_dir, secondary_dirs)
    robustness_rows = read_csv(robustness_dir / "label_preserving_degradation.csv")
    document_scores = read_json(evaluation_dir / "document_scores.json")
    parse_logs = read_parse_logs(
        [
            direct_dir / "baseline_runs.jsonl",
            event_dir / "event_first_runs.jsonl",
            robustness_dir / "direct_baselines" / "baseline_runs.jsonl",
            robustness_dir / "event_first" / "event_first_runs.jsonl",
        ]
    )

    data = {
        "meta": {
            "schema_version": DASHBOARD_SCHEMA_VERSION,
            "exporter_version": EXPORTER_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "evaluation_dir": str(evaluation_dir),
            "robustness_dir": str(robustness_dir),
            "secondary_dirs": [str(item) for item in secondary_dirs],
            "split": (read_json(evaluation_dir / "evaluation_summary.json") or {}).get("split"),
            "artifacts": build_artifacts(evaluation_dir, robustness_dir, direct_dir, event_dir, secondary_dirs),
        },
        "systems": SYSTEMS,
        "summary_by_system": summary_by_system,
        "kpis": build_kpis(summary_by_system, robustness_rows),
        "field_accuracy": build_field_accuracy(summary_by_system),
        "schema_breakdown": build_schema_breakdown(summary_by_system),
        "robustness": build_robustness(robustness_rows),
        "format_comparison": build_format_comparison(secondary_dirs),
        "model_family": build_model_family(secondary_dirs),
        "parse_logs": parse_logs,
        "documents": build_documents(document_scores),
        "evidence_examples": build_evidence_examples(direct_dir, event_dir, document_scores),
        "missingness": {},
    }
    data["missingness"] = missingness_from_bundle(data)

    errors = validate_dashboard_data(data)
    if errors:
        for error in errors:
            print(f"dashboard schema error: {error}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output_path}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    data_path = Path(args.path)
    data = read_json(data_path)
    errors = validate_dashboard_data(data, Path(args.schema))
    if errors:
        for error in errors:
            print(f"dashboard schema error: {error}", file=sys.stderr)
        return 1
    print(f"validated {data_path} against {args.schema}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Export dashboard data from existing run artifacts.")
    build.add_argument("--evaluation-dir", default="runs/evaluation")
    build.add_argument("--robustness-dir", default="runs/robustness")
    build.add_argument("--direct-run-dir", default="runs/direct_baselines")
    build.add_argument("--event-run-dir", default="runs/event_first")
    build.add_argument("--secondary-dir", action="append", default=[])
    build.add_argument("--output", default=str(DEFAULT_OUTPUT))
    build.set_defaults(func=command_build)

    validate = subparsers.add_parser("validate", help="Validate a dashboard data bundle against the dashboard JSON Schema.")
    validate.add_argument("path", nargs="?", default=str(DEFAULT_OUTPUT))
    validate.add_argument("--schema", default=str(SCHEMA_PATH))
    validate.set_defaults(func=command_validate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
