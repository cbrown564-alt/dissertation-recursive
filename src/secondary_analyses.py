#!/usr/bin/env python3
"""Run bounded secondary analyses over existing extraction artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from direct_baselines import load_split_ids, write_json
from evaluate import (
    DEFAULT_DIRECT_RUN_DIR,
    DEFAULT_EVENT_RUN_DIR,
    DEFAULT_MARKUP_ROOT,
    GoldDocument,
    extraction_path,
    flatten_summary,
    load_gold,
    load_json,
    score_document,
)
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, read_text
from validate_extraction import DEFAULT_SCHEMA


DEFAULT_OUTPUT_DIR = Path("runs/secondary_analyses")
FORMAT_SYSTEMS = ["S2", "S3"]
MODEL_SYSTEMS = ["S2", "S3", "E2", "E3"]


@dataclass(frozen=True)
class ModelCondition:
    label: str
    family: str
    system: str
    run_dir: Path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                records.append({"parse": {"parse_success": False, "error": "invalid JSONL record"}})
    return records


def parseability_by_system(run_dir: Path, systems: list[str], document_ids: list[str]) -> dict[str, dict[str, Any]]:
    expected = {(system, document_id) for system in systems for document_id in document_ids}
    records: dict[tuple[str, str], dict[str, Any]] = {}
    for record in read_jsonl(run_dir / "baseline_runs.jsonl"):
        key = (record.get("baseline"), record.get("document_id"))
        if key in expected:
            records[key] = record

    summaries: dict[str, dict[str, Any]] = {}
    for system in systems:
        system_records = [records.get((system, document_id)) for document_id in document_ids]
        present_records = [record for record in system_records if record is not None]
        parse_success = [
            bool(record.get("parse", {}).get("parse_success"))
            for record in present_records
            if isinstance(record, dict)
        ]
        repairs_attempted = [
            bool(record.get("parse", {}).get("repair_attempted"))
            for record in present_records
            if isinstance(record, dict)
        ]
        repairs_succeeded = [
            bool(record.get("parse", {}).get("repair_succeeded"))
            for record in present_records
            if isinstance(record, dict)
        ]
        canonical_available = [
            bool(record.get("canonical_output_path") and Path(record["canonical_output_path"]).exists())
            for record in present_records
            if isinstance(record, dict)
        ]
        summaries[system] = {
            "documents_expected": len(document_ids),
            "log_records_available": len(present_records),
            "parse_success_rate": sum(parse_success) / len(document_ids) if document_ids else None,
            "repair_attempt_rate": sum(repairs_attempted) / len(document_ids) if document_ids else None,
            "repair_success_rate": sum(repairs_succeeded) / sum(repairs_attempted) if sum(repairs_attempted) else None,
            "canonical_available_rate": sum(canonical_available) / len(document_ids) if document_ids else None,
        }
    return summaries


def parse_model_condition(value: str) -> ModelCondition:
    parts = value.split(":", 3)
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "--condition must use LABEL:FAMILY:SYSTEM:RUN_DIR, for example "
            "local_llama:open:E2:runs/event_first_llama"
        )
    label, family, system, run_dir = [part.strip() for part in parts]
    if not label or not family or not system or not run_dir:
        raise argparse.ArgumentTypeError("condition label, family, system, and run directory must be non-empty")
    if system not in MODEL_SYSTEMS:
        raise argparse.ArgumentTypeError(f"unsupported system {system!r}; choose one of {', '.join(MODEL_SYSTEMS)}")
    return ModelCondition(label=label, family=family, system=system, run_dir=Path(run_dir))


def condition_extraction_path(condition: ModelCondition, document_id: str) -> Path:
    if condition.system in {"S2", "S3"}:
        return condition.run_dir / condition.system / document_id / "canonical.json"
    if condition.system == "E2":
        return condition.run_dir / document_id / "e2_canonical.json"
    if condition.system == "E3":
        return condition.run_dir / document_id / "e3_canonical.json"
    raise ValueError(f"unsupported system: {condition.system}")


def condition_log_path(condition: ModelCondition) -> Path:
    if condition.system in {"S2", "S3"}:
        return condition.run_dir / "baseline_runs.jsonl"
    return condition.run_dir / "event_first_runs.jsonl"


def condition_record_matches(condition: ModelCondition, record: dict[str, Any], document_id: str) -> bool:
    if record.get("document_id") != document_id:
        return False
    if condition.system in {"S2", "S3"}:
        return record.get("baseline") == condition.system
    if condition.system == "E2":
        return record.get("pipeline") in {"E1", "E2"}
    return record.get("pipeline") == condition.system


def parseability_by_condition(condition: ModelCondition, document_ids: list[str]) -> dict[str, Any]:
    records_by_document: dict[str, list[dict[str, Any]]] = {document_id: [] for document_id in document_ids}
    for record in read_jsonl(condition_log_path(condition)):
        document_id = record.get("document_id")
        if isinstance(document_id, str) and document_id in records_by_document and condition_record_matches(
            condition, record, document_id
        ):
            records_by_document[document_id].append(record)

    parse_records = []
    repair_attempts = []
    repair_successes = []
    for records in records_by_document.values():
        records_with_parse = [record for record in records if isinstance(record.get("parse"), dict)]
        if not records_with_parse:
            continue
        upstream = next((record for record in records_with_parse if record.get("pipeline") == "E1"), records_with_parse[-1])
        parse = upstream.get("parse", {})
        parse_records.append(bool(parse.get("parse_success")))
        repair_attempts.append(bool(parse.get("repair_attempted")))
        repair_successes.append(bool(parse.get("repair_succeeded")))

    canonical_available = [condition_extraction_path(condition, document_id).exists() for document_id in document_ids]
    log_records_available = sum(1 for records in records_by_document.values() if records)
    return {
        "condition": condition.label,
        "family": condition.family,
        "system": condition.system,
        "run_dir": str(condition.run_dir),
        "documents_expected": len(document_ids),
        "log_records_available": log_records_available,
        "parse_success_rate": sum(parse_records) / len(parse_records) if parse_records else None,
        "repair_attempt_rate": sum(repair_attempts) / len(repair_attempts) if repair_attempts else None,
        "repair_success_rate": sum(repair_successes) / sum(repair_attempts) if sum(repair_attempts) else None,
        "canonical_available_rate": sum(canonical_available) / len(document_ids) if document_ids else None,
    }


def score_systems(args: argparse.Namespace, systems: list[str], document_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    gold = load_gold(Path(args.markup_root), Path(args.exect_root))
    all_scores: dict[str, list[dict[str, Any]]] = {system: [] for system in systems}

    for system in systems:
        for document_id in document_ids:
            data = load_json(extraction_path(system, document_id, args))
            source_text = read_text(Path(args.exect_root) / f"{document_id}.txt")
            document_gold = gold.get(document_id, GoldDocument(document_id=document_id))
            score = score_document(data, source_text, document_gold, Path(args.schema))
            score["document_id"] = document_id
            score["system"] = system
            all_scores[system].append(score)
    return all_scores


def score_condition(
    args: argparse.Namespace,
    condition: ModelCondition,
    document_ids: list[str],
    gold: dict[str, GoldDocument],
) -> list[dict[str, Any]]:
    scores = []
    for document_id in document_ids:
        data = load_json(condition_extraction_path(condition, document_id))
        source_text = read_text(Path(args.exect_root) / f"{document_id}.txt")
        document_gold = gold.get(document_id, GoldDocument(document_id=document_id))
        score = score_document(data, source_text, document_gold, Path(args.schema))
        score["document_id"] = document_id
        score["condition"] = condition.label
        score["family"] = condition.family
        score["system"] = condition.system
        scores.append(score)
    return scores


def numeric_deltas(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    deltas = {}
    for key, right_value in right.items():
        left_value = left.get(key)
        if key.endswith("_count") or key in {"documents_expected", "documents_available", "log_records_available"}:
            continue
        if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
            deltas[key] = right_value - left_value
    return deltas


def format_metric(value: Any) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) else "n/a"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def command_json_yaml(args: argparse.Namespace) -> int:
    systems = args.systems
    document_ids = load_split_ids(Path(args.splits), args.split, args.limit)
    scores = score_systems(args, systems, document_ids)
    evaluation_summaries = {system: flatten_summary(system, scores[system]) for system in systems}
    parse_summaries = parseability_by_system(Path(args.direct_run_dir), systems, document_ids)

    table_rows = []
    for system in systems:
        table_rows.append(
            {
                "system": system,
                **parse_summaries[system],
                **{
                    key: value
                    for key, value in evaluation_summaries[system].items()
                    if key not in {"system", "documents_expected", "documents_available"}
                },
            }
        )

    deltas = {}
    if "S2" in systems and "S3" in systems:
        deltas["S3_minus_S2_parseability"] = numeric_deltas(parse_summaries["S2"], parse_summaries["S3"])
        deltas["S3_minus_S2_evaluation"] = numeric_deltas(evaluation_summaries["S2"], evaluation_summaries["S3"])

    output_dir = Path(args.output_dir)
    write_json(
        output_dir / "json_yaml_summary.json",
        {
            "analysis": "json_vs_yaml_to_json",
            "split": args.split,
            "document_ids": document_ids,
            "systems": systems,
            "parseability": parse_summaries,
            "evaluation": evaluation_summaries,
            "deltas": deltas,
        },
    )
    write_json(output_dir / "json_yaml_document_scores.json", scores)
    write_csv(output_dir / "json_yaml_comparison_table.csv", table_rows)

    for row in table_rows:
        print(
            f"{row['system']}: logs={row['log_records_available']}/{row['documents_expected']} "
            f"parse={format_metric(row['parse_success_rate'])} "
            f"schema={format_metric(row['schema_valid_rate'])} "
            f"quote_valid={format_metric(row['quote_validity_rate'])}"
        )
    print(f"wrote {output_dir / 'json_yaml_summary.json'}")
    print(f"wrote {output_dir / 'json_yaml_comparison_table.csv'}")
    return 0


def command_model_compare(args: argparse.Namespace) -> int:
    conditions = args.conditions
    labels = [condition.label for condition in conditions]
    if len(labels) != len(set(labels)):
        raise ValueError("condition labels must be unique")

    document_ids = load_split_ids(Path(args.splits), args.split, args.limit)
    gold = load_gold(Path(args.markup_root), Path(args.exect_root))

    all_scores = {
        condition.label: score_condition(args, condition, document_ids, gold)
        for condition in conditions
    }
    evaluation_summaries = {
        condition.label: {
            **flatten_summary(condition.label, all_scores[condition.label]),
            "condition": condition.label,
            "family": condition.family,
            "system": condition.system,
            "run_dir": str(condition.run_dir),
        }
        for condition in conditions
    }
    parse_summaries = {condition.label: parseability_by_condition(condition, document_ids) for condition in conditions}

    table_rows = []
    for condition in conditions:
        evaluation = evaluation_summaries[condition.label]
        parseability = parse_summaries[condition.label]
        table_rows.append(
            {
                "condition": condition.label,
                "family": condition.family,
                "system": condition.system,
                "run_dir": str(condition.run_dir),
                **{
                    key: value
                    for key, value in parseability.items()
                    if key not in {"condition", "family", "system", "run_dir"}
                },
                **{
                    key: value
                    for key, value in evaluation.items()
                    if key not in {"condition", "family", "system", "run_dir", "system"}
                },
            }
        )

    reference = args.reference_condition
    deltas = {}
    if reference:
        if reference not in evaluation_summaries:
            raise ValueError(f"reference condition {reference!r} is not one of: {', '.join(labels)}")
        for condition in conditions:
            if condition.label == reference:
                continue
            deltas[f"{condition.label}_minus_{reference}_parseability"] = numeric_deltas(
                parse_summaries[reference], parse_summaries[condition.label]
            )
            deltas[f"{condition.label}_minus_{reference}_evaluation"] = numeric_deltas(
                evaluation_summaries[reference], evaluation_summaries[condition.label]
            )

    output_dir = Path(args.output_dir)
    write_json(
        output_dir / "model_comparison_summary.json",
        {
            "analysis": "open_local_vs_closed_frontier_model_comparison",
            "split": args.split,
            "document_ids": document_ids,
            "conditions": [
                {
                    "label": condition.label,
                    "family": condition.family,
                    "system": condition.system,
                    "run_dir": str(condition.run_dir),
                }
                for condition in conditions
            ],
            "parseability": parse_summaries,
            "evaluation": evaluation_summaries,
            "reference_condition": reference,
            "deltas": deltas,
            "interpretation_boundary": (
                "Secondary model-family comparison over matched existing artifacts; "
                "it is bounded to parseability, schema validity, evidence, temporal, "
                "accuracy, cost, and latency signals relevant to event-first reliability."
            ),
        },
    )
    write_json(output_dir / "model_comparison_document_scores.json", all_scores)
    write_csv(output_dir / "model_comparison_table.csv", table_rows)

    for row in table_rows:
        print(
            f"{row['condition']} ({row['family']}/{row['system']}): "
            f"docs={row['documents_available']}/{row['documents_expected']} "
            f"parse={format_metric(row['parse_success_rate'])} "
            f"schema={format_metric(row['schema_valid_rate'])} "
            f"quote_valid={format_metric(row['quote_validity_rate'])}"
        )
    print(f"wrote {output_dir / 'model_comparison_summary.json'}")
    print(f"wrote {output_dir / 'model_comparison_table.csv'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    json_yaml = subparsers.add_parser(
        "json-yaml",
        help="Compare S2 direct JSON against S3 YAML-to-JSON using matched direct-baseline artifacts.",
    )
    json_yaml.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    json_yaml.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    json_yaml.add_argument("--splits", default=str(DEFAULT_SPLITS))
    json_yaml.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    json_yaml.add_argument("--split", default="validation", choices=["development", "validation", "test"])
    json_yaml.add_argument("--limit", type=int)
    json_yaml.add_argument("--systems", nargs="+", default=FORMAT_SYSTEMS, choices=FORMAT_SYSTEMS)
    json_yaml.add_argument("--direct-run-dir", default=str(DEFAULT_DIRECT_RUN_DIR))
    json_yaml.add_argument("--event-run-dir", default=str(DEFAULT_EVENT_RUN_DIR))
    json_yaml.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    json_yaml.set_defaults(func=command_json_yaml)

    model_compare = subparsers.add_parser(
        "model-compare",
        help="Compare named open/local and closed/frontier model conditions using matched existing artifacts.",
    )
    model_compare.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    model_compare.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    model_compare.add_argument("--splits", default=str(DEFAULT_SPLITS))
    model_compare.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    model_compare.add_argument("--split", default="validation", choices=["development", "validation", "test"])
    model_compare.add_argument("--limit", type=int)
    model_compare.add_argument(
        "--condition",
        dest="conditions",
        action="append",
        type=parse_model_condition,
        required=True,
        help="Named condition as LABEL:FAMILY:SYSTEM:RUN_DIR, e.g. local_llama:open:E2:runs/event_first_llama.",
    )
    model_compare.add_argument(
        "--reference-condition",
        help="Optional condition label to subtract from all other conditions for compact deltas.",
    )
    model_compare.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    model_compare.set_defaults(func=command_model_compare)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
