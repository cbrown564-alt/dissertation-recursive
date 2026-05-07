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
    normalize_contract_aliases,
    parse_json_response,
    validate_and_score,
    write_json,
    write_text,
)
from evaluate import DEFAULT_MARKUP_ROOT, flatten_summary, load_gold, score_document
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document
from model_providers import ModelRequest, adapter_for, write_response_log
from model_registry import DEFAULT_REGISTRY, load_model_specs, write_registry_snapshot
from validate_extraction import DEFAULT_SCHEMA


DEFAULT_HARNESS_MATRIX = Path("configs/harness_matrix.yaml")
DEFAULT_OUTPUT_DIR = Path("runs/model_expansion/stage_a_smoke")
DEFAULT_STAGE_B_OUTPUT_DIR = Path("runs/model_expansion/stage_b_dev_pilot")
BENCHMARK_METRICS = ["medication_name_f1", "seizure_type_f1", "epilepsy_diagnosis_accuracy"]


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
        parse.data = normalize_contract_aliases(parse.data, document_id, f"D0_{harness_id}")
        metadata = parse.data.setdefault("metadata", {}) if isinstance(parse.data, dict) else {}
        if isinstance(metadata, dict):
            metadata.update(
                {
                    "model": spec.provider_model_id,
                    "model_label": model_label,
                    "provider": spec.provider,
                    "harness_id": harness_id,
                    "latency_ms": response.latency_ms,
                    "input_tokens": response.token_usage.input_tokens,
                    "output_tokens": response.token_usage.output_tokens,
                    "cache_read_tokens": response.token_usage.cache_read_tokens,
                    "cache_write_tokens": response.token_usage.cache_write_tokens,
                    "estimated_cost_usd": response.estimated_cost.get("total"),
                    "pricing_snapshot_date": response.estimated_cost.get("pricing_snapshot_date"),
                    "repair_attempted": parse.repair_attempted,
                    "repair_succeeded": parse.repair_succeeded,
                }
            )
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean_present(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) / len(present) if present else None


def system_for_harness(harness_id: str) -> str:
    return {
        "H0_strict_canonical": "D0",
        "H2_task_specific": "D1",
        "H3_loose_answer_then_parse": "D2",
    }.get(harness_id, harness_id)


def score_stage_b_canonical(
    stage_a_dir: Path,
    rows: list[dict[str, str]],
    exect_root: Path,
    markup_root: Path,
    schema_path: Path,
) -> dict[tuple[str, str], dict[str, Any]]:
    gold = load_gold(markup_root, exect_root)
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("harness_id") != "H0_strict_canonical":
            continue
        document_id = row["document_id"]
        canonical_path = stage_a_dir / row["model_label"] / row["harness_id"] / document_id / "canonical.json"
        data = json.loads(canonical_path.read_text(encoding="utf-8")) if canonical_path.exists() else None
        source_text = preprocess_document(document_id, exect_root)["text"]
        by_pair.setdefault((row["model_label"], row["harness_id"]), []).append(
            score_document(data, source_text, gold[document_id], schema_path)
        )
    return {pair: flatten_summary(f"{pair[0]}:{pair[1]}", scores) for pair, scores in by_pair.items()}


def summarize_stage_b_rows(
    rows: list[dict[str, str]],
    canonical_scores: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["model_label"], row["harness_id"]), []).append(row)

    summaries = []
    for (model_label, harness_id), pair_rows in sorted(grouped.items()):
        status_success = sum(1 for row in pair_rows if row.get("status") == "success")
        parse_success = sum(1 for row in pair_rows if row.get("parse_success") == "True")
        repair_attempted = sum(1 for row in pair_rows if row.get("repair_attempted") == "True")
        repair_succeeded = sum(1 for row in pair_rows if row.get("repair_succeeded") == "True")
        scored = canonical_scores.get((model_label, harness_id), {})
        benchmark_values = [to_float(scored.get(metric)) for metric in BENCHMARK_METRICS]
        benchmark_quality = mean_present(benchmark_values)
        mean_cost = mean_present([to_float(row.get("estimated_cost")) for row in pair_rows])
        summary = {
            "model_label": model_label,
            "provider": pair_rows[0].get("provider"),
            "provider_model_id": pair_rows[0].get("provider_model_id"),
            "system": system_for_harness(harness_id),
            "harness_id": harness_id,
            "documents": len(pair_rows),
            "successful_calls": status_success,
            "call_success_rate": status_success / len(pair_rows) if pair_rows else 0.0,
            "parse_success_rate": parse_success / len(pair_rows) if pair_rows else 0.0,
            "repair_attempt_rate": repair_attempted / len(pair_rows) if pair_rows else 0.0,
            "repair_success_rate": repair_succeeded / repair_attempted if repair_attempted else 1.0,
            "schema_valid_rate": scored.get("schema_valid_rate"),
            "quote_presence_rate": scored.get("quote_presence_rate"),
            "quote_validity_rate": scored.get("quote_validity_rate"),
            "temporal_accuracy": scored.get("temporal_accuracy"),
            "medication_name_f1": scored.get("medication_name_f1"),
            "seizure_type_f1": scored.get("seizure_type_f1"),
            "epilepsy_diagnosis_accuracy": scored.get("epilepsy_diagnosis_accuracy"),
            "benchmark_quality": benchmark_quality,
            "mean_latency_ms": mean_present([to_float(row.get("latency_ms")) for row in pair_rows]),
            "latency_p50_ms": percentile([value for value in [to_float(row.get("latency_ms")) for row in pair_rows] if value is not None], 0.50),
            "latency_p95_ms": percentile([value for value in [to_float(row.get("latency_ms")) for row in pair_rows] if value is not None], 0.95),
            "mean_input_tokens": mean_present([to_float(row.get("input_tokens")) for row in pair_rows]),
            "mean_output_tokens": mean_present([to_float(row.get("output_tokens")) for row in pair_rows]),
            "mean_estimated_cost_usd": mean_cost,
            "cost_per_benchmark_quality_point": (mean_cost / benchmark_quality) if mean_cost is not None and benchmark_quality else None,
            "scoring_status": "canonical_scored" if scored else "parser_only_until_canonical_projection",
        }
        summaries.append(summary)
    return summaries


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def cost_frontier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in rows
        if isinstance(row.get("benchmark_quality"), (int, float))
        and isinstance(row.get("mean_estimated_cost_usd"), (int, float))
    ]
    frontier = []
    for row in candidates:
        dominated = any(
            other is not row
            and other["benchmark_quality"] >= row["benchmark_quality"]
            and other["mean_estimated_cost_usd"] <= row["mean_estimated_cost_usd"]
            and (
                other["benchmark_quality"] > row["benchmark_quality"]
                or other["mean_estimated_cost_usd"] < row["mean_estimated_cost_usd"]
            )
            for other in candidates
        )
        if not dominated:
            frontier.append({**row, "frontier_reason": "not_dominated_on_quality_and_cost"})
    return sorted(frontier, key=lambda row: (row["mean_estimated_cost_usd"], -row["benchmark_quality"]))


def promotion_decision(rows: list[dict[str, Any]], frontier_rows: list[dict[str, Any]], split: str) -> str:
    scored_rows = [row for row in rows if row["scoring_status"] == "canonical_scored"]
    baseline = next((row for row in scored_rows if row["model_label"] == "gpt_4_1_mini_baseline"), None)
    baseline_quality = to_float((baseline or {}).get("benchmark_quality")) or 0.0
    promoted = [
        row
        for row in frontier_rows
        if (to_float(row.get("benchmark_quality")) or 0.0) >= baseline_quality
        and (to_float(row.get("parse_success_rate")) or 0.0) >= 0.9
        and (to_float(row.get("schema_valid_rate")) or 0.0) >= 0.9
    ]
    cheapest = min(scored_rows, key=lambda row: to_float(row.get("mean_estimated_cost_usd")) or float("inf"), default=None)
    retained_baseline = baseline or cheapest

    lines = [
        "# Stage B Development Pilot Promotion Decision",
        "",
        f"Split: `{split}`",
        "",
        "## Summary",
        "",
        f"- Scored canonical pairs: {len(scored_rows)}",
        f"- Cost-effectiveness frontier pairs: {len(frontier_rows)}",
        f"- Baseline benchmark quality: {baseline_quality:.4f}",
        f"- Retained cheap baseline: `{retained_baseline['model_label']}` / `{retained_baseline['harness_id']}`"
        if retained_baseline
        else "- Retained cheap baseline: none",
        "",
        "## Promoted Pairs",
        "",
    ]
    if promoted:
        for row in promoted:
            lines.append(
                "- "
                + f"`{row['model_label']}` / `{row['harness_id']}` "
                + f"(quality={to_float(row.get('benchmark_quality')) or 0.0:.4f}, "
                + f"mean_cost_usd={to_float(row.get('mean_estimated_cost_usd')) or 0.0:.8f})"
            )
    else:
        lines.append("- None; no scored pair passed the promotion gate.")
    lines.extend(
        [
            "",
            "## Gate Notes",
            "",
            "- `H2_task_specific` and `H3_loose_answer_then_parse` are tracked for call and parse stability, but remain parser-only until a deterministic canonical projection is added.",
            "- Promotion requires call/parse stability, canonical schema validity, and non-dominance on cost versus benchmark-quality when cost is available.",
        ]
    )
    return "\n".join(lines) + "\n"


def command_stage_b(args: argparse.Namespace) -> int:
    stage_a_dir = Path(args.stage_a_dir)
    report_path = stage_a_dir / "provider_call_report.csv"
    if not report_path.exists():
        raise FileNotFoundError(f"Stage A provider report not found: {report_path}")
    rows = read_csv(report_path)
    canonical_scores = score_stage_b_canonical(
        stage_a_dir,
        rows,
        Path(args.exect_root),
        Path(args.markup_root),
        Path(args.schema),
    )
    summaries = summarize_stage_b_rows(rows, canonical_scores)
    frontier = cost_frontier(summaries)
    output_dir = Path(args.output_dir)
    write_csv(output_dir / "comparison_table.csv", summaries)
    write_csv(output_dir / "cost_effectiveness_frontier.csv", frontier)
    (output_dir / "promotion_decision.md").parent.mkdir(parents=True, exist_ok=True)
    (output_dir / "promotion_decision.md").write_text(
        promotion_decision(summaries, frontier, args.split),
        encoding="utf-8",
    )
    manifest = {
        "stage": "stage_b_dev_pilot",
        "source_stage_a_dir": str(stage_a_dir),
        "split": args.split,
        "comparison_table": str(output_dir / "comparison_table.csv"),
        "cost_effectiveness_frontier": str(output_dir / "cost_effectiveness_frontier.csv"),
        "promotion_decision": str(output_dir / "promotion_decision.md"),
    }
    write_json(output_dir / "stage_b_manifest.json", manifest)
    print(f"wrote Stage B comparison for {len(summaries)} model/harness pairs")
    return 0


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

    stage_b = subparsers.add_parser(
        "stage-b-dev-pilot",
        help="Summarize a Stage A/dev-pilot run into comparison, frontier, and promotion artifacts.",
    )
    stage_b.add_argument("--stage-a-dir", default=str(DEFAULT_OUTPUT_DIR))
    stage_b.add_argument("--output-dir", default=str(DEFAULT_STAGE_B_OUTPUT_DIR))
    stage_b.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    stage_b.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    stage_b.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    stage_b.add_argument("--split", default="development", choices=["development", "validation", "test"])
    stage_b.set_defaults(func=command_stage_b)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
