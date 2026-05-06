#!/usr/bin/env python3
"""Run bounded secondary analyses over existing extraction artifacts."""

from __future__ import annotations

import argparse
import csv
import json
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

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
