#!/usr/bin/env python3
"""Stage A smoke runner for the powerful-model expansion study."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import yaml

from direct_baselines import (
    build_prompt as build_direct_prompt,
    load_split_ids,
    parse_json_response,
    validate_and_score,
    write_json,
    write_text,
)
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document
from model_providers import ModelRequest, adapter_for, write_response_log
from model_registry import DEFAULT_REGISTRY, load_model_specs, write_registry_snapshot
from validate_extraction import DEFAULT_SCHEMA


DEFAULT_HARNESS_MATRIX = Path("configs/harness_matrix.yaml")
DEFAULT_OUTPUT_DIR = Path("runs/model_expansion/stage_a_smoke")


def load_harnesses(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    harnesses = data.get("harnesses")
    if not isinstance(harnesses, dict):
        raise ValueError(f"harness matrix must contain a harnesses object: {path}")
    return harnesses


def sentence_table(document: dict[str, Any]) -> str:
    return "\n".join(
        f"{sentence['sentence_id']} [{sentence['char_start']}, {sentence['char_end']}]: {sentence['text']}"
        for sentence in document["sentences"]
    )


def build_task_specific_prompt(document: dict[str, Any], harness_id: str) -> str:
    return "\n\n".join(
        [
            "Extract only these benchmark-oriented fields from the epilepsy clinic letter.",
            "Return compact JSON with keys: medication_names, seizure_types, epilepsy_types, seizure_frequency, investigations.",
            "Use null or [] when absent. Do not invent unsupported values.",
            f"## Harness\n{harness_id}",
            "## Sentence List",
            sentence_table(document),
            "## Source Letter",
            document["text"],
        ]
    )


def build_loose_prompt(document: dict[str, Any], harness_id: str) -> str:
    return "\n\n".join(
        [
            "Answer concisely from the epilepsy clinic letter.",
            "List current anti-seizure medications, seizure types, epilepsy diagnosis/type, current seizure frequency, EEG result, and MRI result.",
            "Use brief bullets or simple JSON. Say not stated when the letter does not support a field.",
            f"## Harness\n{harness_id}",
            "## Source Letter",
            document["text"],
        ]
    )


def build_harness_prompt(harness_id: str, document: dict[str, Any], schema_path: Path) -> str:
    if harness_id == "H0_strict_canonical":
        return build_direct_prompt("S2", document, schema_path)
    if harness_id == "H2_task_specific":
        return build_task_specific_prompt(document, harness_id)
    if harness_id == "H3_loose_answer_then_parse":
        return build_loose_prompt(document, harness_id)
    raise ValueError(f"unsupported Stage A harness: {harness_id}")


def provider_for_args(model_provider: str, stub_calls: bool) -> str:
    return "stub" if stub_calls else model_provider


def run_one(args: argparse.Namespace, model_label: str, harness_id: str, document_id: str) -> dict[str, Any]:
    specs = load_model_specs(Path(args.registry))
    spec = specs[model_label]
    document = preprocess_document(document_id, Path(args.exect_root))
    prompt = build_harness_prompt(harness_id, document, Path(args.schema))

    run_root = Path(args.output_dir) / model_label / harness_id / document_id
    prompt_path = run_root / "prompt.txt"
    raw_path = run_root / "raw_response.txt"
    response_log_path = run_root / "provider_response.json"
    write_text(prompt_path, prompt)

    request = ModelRequest(
        prompt=prompt,
        model=spec,
        harness_id=harness_id,
        temperature=args.temperature if args.temperature is not None else spec.temperature,
        max_output_tokens=args.max_output_tokens or spec.max_output_tokens,
        schema_mode=None,
        metadata={"document_id": document_id, "stage": "stage_a_smoke"},
    )
    adapter = adapter_for(provider_for_args(spec.provider, args.stub_calls))
    response = adapter.call(request)
    write_text(raw_path, response.text)
    response.raw_response_path = str(raw_path)
    write_response_log(response, response_log_path)

    parse = parse_json_response(response.text)
    scores = None
    if harness_id == "H0_strict_canonical" and parse.data is not None:
        scores = validate_and_score(parse.data, document["text"], Path(args.schema), require_present_evidence=True)
        write_json(run_root / "canonical.json", parse.data)

    record = {
        "model_label": model_label,
        "provider": spec.provider,
        "called_provider": adapter.provider,
        "provider_model_id": spec.provider_model_id,
        "harness_id": harness_id,
        "document_id": document_id,
        "status": "success" if not response.error else "unavailable",
        "error": response.error,
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "provider_response_path": str(response_log_path),
        "parse_success": parse.parse_success,
        "repair_attempted": parse.repair_attempted,
        "repair_succeeded": parse.repair_succeeded,
        "schema_valid": (scores or {}).get("schema_valid"),
        "project_constraints_valid": (scores or {}).get("project_constraints_valid"),
        "input_tokens": response.token_usage.input_tokens,
        "output_tokens": response.token_usage.output_tokens,
        "cache_read_tokens": response.token_usage.cache_read_tokens,
        "cache_write_tokens": response.token_usage.cache_write_tokens,
        "latency_ms": round(response.latency_ms, 3),
        "retries": response.retries,
        "estimated_cost": response.estimated_cost.get("total"),
        "cost_status": response.estimated_cost.get("status"),
        "pricing_snapshot_date": response.estimated_cost.get("pricing_snapshot_date"),
    }
    return record


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def command_stage_a(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    snapshot = write_registry_snapshot(output_dir / "model_registry_snapshot.json", Path(args.registry))
    specs = load_model_specs(Path(args.registry))
    harnesses = load_harnesses(Path(args.harness_matrix))
    document_ids = load_split_ids(Path(args.splits), args.split, args.limit)
    model_labels = args.models or list(specs)
    harness_ids = args.harnesses or ["H0_strict_canonical", "H2_task_specific", "H3_loose_answer_then_parse"]

    rows = []
    for model_label in model_labels:
        if model_label not in specs:
            raise ValueError(f"unknown model label: {model_label}")
        for harness_id in harness_ids:
            if harness_id not in harnesses:
                raise ValueError(f"unknown harness id: {harness_id}")
            for document_id in document_ids:
                row = run_one(args, model_label, harness_id, document_id)
                rows.append(row)
                print(f"{row['status']}: {model_label} {harness_id} {document_id}")

    write_csv(output_dir / "provider_call_report.csv", rows)
    manifest = {
        "stage": "stage_a_smoke",
        "registry_version": snapshot.get("version"),
        "harness_matrix": args.harness_matrix,
        "split": args.split,
        "document_ids": document_ids,
        "model_labels": model_labels,
        "harness_ids": harness_ids,
        "stub_calls": args.stub_calls,
        "report": str(output_dir / "provider_call_report.csv"),
    }
    write_json(output_dir / "stage_a_manifest.json", manifest)
    failures = [row for row in rows if row["status"] != "success"]
    return 1 if failures and not args.allow_unavailable else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage_a = subparsers.add_parser("stage-a-smoke", help="Run the Stage A provider and harness smoke matrix.")
    stage_a.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    stage_a.add_argument("--harness-matrix", default=str(DEFAULT_HARNESS_MATRIX))
    stage_a.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    stage_a.add_argument("--splits", default=str(DEFAULT_SPLITS))
    stage_a.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    stage_a.add_argument("--split", default="development", choices=["development", "validation", "test"])
    stage_a.add_argument("--limit", type=int, default=2)
    stage_a.add_argument("--models", nargs="+")
    stage_a.add_argument("--harnesses", nargs="+")
    stage_a.add_argument("--temperature", type=float)
    stage_a.add_argument("--max-output-tokens", type=int)
    stage_a.add_argument("--stub-calls", action="store_true", help="Exercise logging without paid provider calls.")
    stage_a.add_argument("--allow-unavailable", action="store_true", help="Exit zero even if providers are unavailable.")
    stage_a.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    stage_a.set_defaults(func=command_stage_a)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
