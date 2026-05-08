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
from evaluate import DEFAULT_MARKUP_ROOT, GoldDocument, build_field_prf_table, flatten_summary, load_gold, score_document
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document
from model_providers import ModelRequest, TokenUsage, adapter_for, estimate_cost, write_response_log
from model_registry import DEFAULT_REGISTRY, load_model_specs, write_registry_snapshot
from validate_extraction import DEFAULT_SCHEMA


DEFAULT_HARNESS_MATRIX = Path("configs/harness_matrix.yaml")
DEFAULT_OUTPUT_DIR = Path("runs/model_expansion/stage_a_smoke")
DEFAULT_STAGE_B_OUTPUT_DIR = Path("runs/model_expansion/stage_b_dev_pilot")
DEFAULT_STAGE_C_OUTPUT_DIR = Path("runs/model_expansion/stage_c_validation")
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
        reasoning_effort=args.reasoning_effort,
        google_thinking_budget=args.google_thinking_budget,
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
        "stop_reason": response.stop_reason,
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "provider_response_path": str(response_log_path),
        "canonical_output_path": str(run_root / "canonical.json") if scores is not None else None,
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
        "parse_error": parse.error,
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
                print(f"{row['status']}: {model_label} {harness_id} {document_id}", flush=True)

    write_csv(output_dir / "provider_call_report.csv", rows)
    manifest = {
        "stage": "stage_a_smoke",
        "registry_version": snapshot.get("version"),
        "harness_matrix": args.harness_matrix,
        "split": args.split,
        "document_ids": document_ids,
        "model_labels": model_labels,
        "harness_ids": harness_ids,
        "max_output_tokens": args.max_output_tokens,
        "reasoning_effort": args.reasoning_effort,
        "google_thinking_budget": args.google_thinking_budget,
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


def truthy_csv(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def resolve_report_path(stage_a_dir: Path, row: dict[str, str], field: str) -> Path | None:
    value = (row.get(field) or "").strip()
    if not value:
        return None
    path = Path(value)
    candidates = [path] if path.is_absolute() else [path, stage_a_dir / path]
    source_dir = (row.get("source_dir") or "").strip()
    if source_dir and not path.is_absolute():
        candidates.append(Path(source_dir) / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def canonical_path_for_report_row(stage_a_dir: Path, row: dict[str, str]) -> Path:
    explicit = resolve_report_path(stage_a_dir, row, "canonical_output_path")
    if explicit and explicit.exists():
        return explicit
    raw_path = resolve_report_path(stage_a_dir, row, "raw_response_path")
    if raw_path:
        sibling = raw_path.with_name("canonical.json")
        if sibling.exists():
            return sibling
    return stage_a_dir / row["model_label"] / row["harness_id"] / row["document_id"] / "canonical.json"


def parse_success_for_row(stage_a_dir: Path, row: dict[str, str]) -> bool:
    if "parse_success" in row and (row.get("parse_success") or "") != "":
        parsed = truthy_csv(row.get("parse_success"))
        if row.get("harness_id") == "H0_strict_canonical":
            return parsed and canonical_path_for_report_row(stage_a_dir, row).exists()
        return parsed
    return row.get("harness_id") == "H0_strict_canonical" and canonical_path_for_report_row(stage_a_dir, row).exists()


def repair_attempted_for_row(row: dict[str, str]) -> bool:
    return truthy_csv(row.get("repair_attempted"))


def repair_succeeded_for_row(row: dict[str, str]) -> bool:
    return truthy_csv(row.get("repair_succeeded"))


def availability_note(pair_rows: list[dict[str, str]]) -> str:
    errors = " ".join(row.get("error") or "" for row in pair_rows)
    successes = sum(1 for row in pair_rows if row.get("status") == "success")
    failures = len(pair_rows) - successes
    if failures and successes == 0 and ("RESOURCE_EXHAUSTED" in errors or "quota" in errors.lower() or "429" in errors):
        return "unavailable_due_to_quota"
    if failures and successes and ("503" in errors or "UNAVAILABLE" in errors):
        return "mostly_available_with_transient_503"
    if failures:
        return "partially_available_with_failures"
    return "available"


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
        canonical_path = canonical_path_for_report_row(stage_a_dir, row)
        data = json.loads(canonical_path.read_text(encoding="utf-8")) if canonical_path.exists() else None
        source_text = preprocess_document(document_id, exect_root)["text"]
        by_pair.setdefault((row["model_label"], row["harness_id"]), []).append(
            score_document(data, source_text, gold[document_id], schema_path)
        )
    return {pair: flatten_summary(f"{pair[0]}:{pair[1]}", scores) for pair, scores in by_pair.items()}


def summarize_stage_b_rows(
    stage_a_dir: Path,
    rows: list[dict[str, str]],
    canonical_scores: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["model_label"], row["harness_id"]), []).append(row)

    summaries = []
    for (model_label, harness_id), pair_rows in sorted(grouped.items()):
        status_success = sum(1 for row in pair_rows if row.get("status") == "success")
        parse_success = sum(1 for row in pair_rows if parse_success_for_row(stage_a_dir, row))
        repair_attempted = sum(1 for row in pair_rows if repair_attempted_for_row(row))
        repair_succeeded = sum(1 for row in pair_rows if repair_succeeded_for_row(row))
        scored = canonical_scores.get((model_label, harness_id), {})
        canonical_documents_available = int(scored.get("documents_available") or 0)
        benchmark_values = [to_float(scored.get(metric)) for metric in BENCHMARK_METRICS]
        benchmark_quality = mean_present(benchmark_values)
        mean_cost = mean_present([to_float(row.get("estimated_cost")) for row in pair_rows])
        note = availability_note(pair_rows)
        scoring_status = "canonical_scored" if canonical_documents_available else "parser_only_until_canonical_projection"
        summary = {
            "model_label": model_label,
            "provider": pair_rows[0].get("provider"),
            "provider_model_id": pair_rows[0].get("provider_model_id"),
            "system": system_for_harness(harness_id),
            "harness_id": harness_id,
            "documents": len(pair_rows),
            "canonical_documents_available": canonical_documents_available,
            "successful_calls": status_success,
            "call_success_rate": status_success / len(pair_rows) if pair_rows else 0.0,
            "availability_note": note,
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
            "scoring_status": scoring_status,
            "promotion_eligibility": "eligible" if scoring_status == "canonical_scored" and note == "available" else f"excluded_or_marked:{note}",
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
        and row.get("availability_note") == "available"
        and (to_float(row.get("call_success_rate")) or 0.0) >= 0.9
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
    lines.extend(["", "## Gate Notes", ""])
    if any(row["model_label"] == "gemini_3_1_pro" and row.get("availability_note") == "unavailable_due_to_quota" for row in rows):
        lines.append("- `gemini_3_1_pro` is marked unavailable where Stage A returned quota/resource-exhausted errors.")
    if any(row["model_label"] == "gemini_3_1_flash" and row.get("availability_note") == "mostly_available_with_transient_503" for row in rows):
        lines.append("- `gemini_3_1_flash` is marked mostly available where Stage A mixed successful calls with a transient 503.")
    lines.extend(
        [
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
    summaries = summarize_stage_b_rows(stage_a_dir, rows, canonical_scores)
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
        "artifact_path_policy": "canonical_output_path/raw_response_path from provider report are honored before falling back under source_stage_a_dir",
        "comparison_table": str(output_dir / "comparison_table.csv"),
        "cost_effectiveness_frontier": str(output_dir / "cost_effectiveness_frontier.csv"),
        "promotion_decision": str(output_dir / "promotion_decision.md"),
    }
    write_json(output_dir / "stage_b_manifest.json", manifest)
    print(f"wrote Stage B comparison for {len(summaries)} model/harness pairs")
    return 0


def condition_label(model_label: str, harness_id: str, system: str) -> str:
    return f"{model_label}:{system}:{harness_id}"


def score_stage_a_outputs(
    stage_a_dir: Path,
    exect_root: Path,
    markup_root: Path,
    schema_path: Path,
    harness_ids: set[str] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    report_path = stage_a_dir / "provider_call_report.csv"
    if not report_path.exists():
        raise FileNotFoundError(f"Stage A provider report not found: {report_path}")
    rows = read_csv(report_path)
    gold = load_gold(markup_root, exect_root)
    all_scores: dict[str, list[dict[str, Any]]] = {}
    metadata: dict[str, dict[str, Any]] = {}

    for row in rows:
        harness_id = row.get("harness_id", "")
        if harness_ids and harness_id not in harness_ids:
            continue
        system = system_for_harness(harness_id)
        label = condition_label(row["model_label"], harness_id, system)
        metadata.setdefault(
            label,
            {
                "model_label": row["model_label"],
                "registry_model_label": row["model_label"],
                "provider": row.get("provider"),
                "provider_model_id": row.get("provider_model_id"),
                "system": system,
                "harness_id": harness_id,
                "source": "stage_a_outputs",
                "source_dir": str(stage_a_dir),
                "call_rows": [],
            },
        )
        metadata[label]["call_rows"].append(row)
        if harness_id != "H0_strict_canonical":
            continue

        document_id = row["document_id"]
        canonical_path = canonical_path_for_report_row(stage_a_dir, row)
        data = json.loads(canonical_path.read_text(encoding="utf-8")) if canonical_path.exists() else None
        source_text = preprocess_document(document_id, exect_root)["text"]
        score = score_document(data, source_text, gold.get(document_id, GoldDocument(document_id=document_id)), schema_path)
        score["document_id"] = document_id
        score["system"] = label
        all_scores.setdefault(label, []).append(score)
    return all_scores, metadata


def load_evaluation_condition(value: str) -> tuple[str, str, str, Path]:
    parts = value.split(":", 3)
    if len(parts) != 4:
        raise ValueError(
            "--evaluation-condition must be LABEL:SYSTEM:HARNESS_ID:EVALUATION_DIR, "
            f"got: {value}"
        )
    label, system, harness_id, evaluation_dir = parts
    return label, system, harness_id, Path(evaluation_dir)


def parse_condition_model(values: list[str] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"--condition-model must be CONDITION=REGISTRY_MODEL_LABEL, got: {value}")
        condition, model_label = value.split("=", 1)
        mapping[condition] = model_label
    return mapping


def load_existing_evaluation_conditions(
    conditions: list[str] | None,
    condition_models: dict[str, str] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    all_scores: dict[str, list[dict[str, Any]]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for condition in conditions or []:
        label, system, harness_id, evaluation_dir = load_evaluation_condition(condition)
        document_scores_path = evaluation_dir / "document_scores.json"
        if not document_scores_path.exists():
            raise FileNotFoundError(f"missing document scores for condition {condition}: {document_scores_path}")
        document_scores = json.loads(document_scores_path.read_text(encoding="utf-8"))
        system_scores = document_scores.get(system)
        if not isinstance(system_scores, list):
            raise ValueError(f"system {system} not found in {document_scores_path}")
        all_scores[label] = [{**score, "system": label} for score in system_scores]
        metadata[label] = {
            "model_label": label,
            "registry_model_label": (condition_models or {}).get(label, label),
            "provider": None,
            "provider_model_id": None,
            "system": system,
            "harness_id": harness_id,
            "source": "evaluation_dir",
            "source_dir": str(evaluation_dir),
            "call_rows": [],
        }
    return all_scores, metadata


def document_metric_value(score: dict[str, Any], metric: str) -> float:
    field_scores = score.get("field_scores", {})
    item = field_scores.get(metric, {})
    if metric in {"medication_name", "seizure_type"} and isinstance(item, dict):
        return float(item.get("f1", 0.0))
    if isinstance(item, dict):
        return 1.0 if item.get("correct") else 0.0
    return 0.0


def summarize_condition(label: str, scores: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    summary = flatten_summary(label, scores)
    call_rows = meta.get("call_rows") or []
    parse_success = sum(1 for row in call_rows if row.get("parse_success") == "True")
    repair_attempted = sum(1 for row in call_rows if row.get("repair_attempted") == "True")
    repair_succeeded = sum(1 for row in call_rows if row.get("repair_succeeded") == "True")
    benchmark_quality = mean_present([to_float(summary.get(metric)) for metric in BENCHMARK_METRICS])
    mean_input_tokens = summary.get("mean_input_tokens")
    mean_output_tokens = summary.get("mean_output_tokens")
    mean_estimated_cost = summary.get("mean_estimated_cost_usd")
    if mean_estimated_cost is None:
        mean_estimated_cost = estimate_mean_cost_from_registry(
            meta.get("registry_model_label"),
            mean_input_tokens,
            mean_output_tokens,
            meta.get("model_specs", {}),
        )

    return {
        "condition": label,
        "model_label": meta.get("model_label"),
        "provider": meta.get("provider"),
        "provider_model_id": meta.get("provider_model_id"),
        "system": meta.get("system"),
        "harness_id": meta.get("harness_id"),
        "source": meta.get("source"),
        "documents_expected": summary.get("documents_expected"),
        "documents_available": summary.get("documents_available"),
        "call_success_rate": (sum(1 for row in call_rows if row.get("status") == "success") / len(call_rows))
        if call_rows
        else None,
        "parse_success_rate": parse_success / len(call_rows) if call_rows else None,
        "repair_attempt_rate": repair_attempted / len(call_rows) if call_rows else None,
        "repair_success_rate": repair_succeeded / repair_attempted if repair_attempted else None,
        "schema_valid_rate": summary.get("schema_valid_rate"),
        "quote_presence_rate": summary.get("quote_presence_rate"),
        "quote_validity_rate": summary.get("quote_validity_rate"),
        "temporal_accuracy": summary.get("temporal_accuracy"),
        "medication_name_f1": summary.get("medication_name_f1"),
        "seizure_type_f1": summary.get("seizure_type_f1"),
        "epilepsy_diagnosis_accuracy": summary.get("epilepsy_diagnosis_accuracy"),
        "medication_full_f1": summary.get("medication_full_f1"),
        "current_seizure_frequency_accuracy": summary.get("current_seizure_frequency_accuracy"),
        "seizure_frequency_type_linkage_accuracy": summary.get("seizure_frequency_type_linkage_accuracy"),
        "benchmark_quality": benchmark_quality,
        "mean_latency_ms": summary.get("mean_latency_ms"),
        "mean_input_tokens": mean_input_tokens,
        "mean_output_tokens": mean_output_tokens,
        "mean_estimated_cost_usd": mean_estimated_cost,
        "cost_estimation_status": cost_estimation_status(
            mean_estimated_cost,
            meta.get("registry_model_label"),
            mean_input_tokens,
            mean_output_tokens,
        ),
    }


def estimate_mean_cost_from_registry(
    registry_model_label: str | None,
    mean_input_tokens: Any,
    mean_output_tokens: Any,
    specs: dict[str, Any],
) -> float | None:
    input_tokens = to_float(mean_input_tokens)
    output_tokens = to_float(mean_output_tokens)
    if not registry_model_label or registry_model_label not in specs:
        return None
    if input_tokens is None or output_tokens is None:
        return None
    if input_tokens <= 0 and output_tokens <= 0:
        return None
    cost = estimate_cost(
        specs[registry_model_label],
        TokenUsage(input_tokens=int(round(input_tokens)), output_tokens=int(round(output_tokens))),
    )
    return cost.get("total") if cost.get("status") == "complete" else None


def cost_estimation_status(
    mean_estimated_cost: Any,
    registry_model_label: str | None,
    mean_input_tokens: Any,
    mean_output_tokens: Any,
) -> str:
    if isinstance(mean_estimated_cost, (int, float)):
        return "estimated_or_recorded"
    if not registry_model_label:
        return "missing_registry_model_label"
    input_tokens = to_float(mean_input_tokens)
    output_tokens = to_float(mean_output_tokens)
    if input_tokens is None or output_tokens is None:
        return "missing_token_usage"
    if input_tokens <= 0 and output_tokens <= 0:
        return "legacy_zero_token_usage"
    return "missing_registry_price"


def bootstrap_stage_c(
    all_scores: dict[str, list[dict[str, Any]]],
    summaries: dict[str, dict[str, Any]],
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    import random

    rng = random.Random(seed)
    intervals: dict[str, dict[str, Any]] = {}
    for label, scores in all_scores.items():
        intervals[label] = {}
        if not scores:
            continue
        for metric in ["medication_name", "seizure_type", "epilepsy_diagnosis"]:
            samples = []
            for _ in range(iterations):
                sampled_scores = [scores[rng.randrange(len(scores))] for _ in scores]
                samples.append(sum(document_metric_value(score, metric) for score in sampled_scores) / len(sampled_scores))
            intervals[label][metric] = {
                "observed": summaries[label].get(f"{metric}_f1")
                if metric != "epilepsy_diagnosis"
                else summaries[label].get("epilepsy_diagnosis_accuracy"),
                "ci95_low": percentile(samples, 0.025),
                "ci95_high": percentile(samples, 0.975),
                "bootstrap_iterations": iterations,
            }
    return intervals


def correctly_extracted_benchmark_units(scores: list[dict[str, Any]]) -> float:
    total = 0.0
    for score in scores:
        total += document_metric_value(score, "medication_name")
        total += document_metric_value(score, "seizure_type")
        total += document_metric_value(score, "epilepsy_diagnosis")
    return total


def build_cost_latency_table(summaries: list[dict[str, Any]], all_scores: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for summary in summaries:
        label = summary["condition"]
        scores = all_scores.get(label, [])
        cost = to_float(summary.get("mean_estimated_cost_usd"))
        correct_units = correctly_extracted_benchmark_units(scores)
        rows.append(
            {
                "condition": label,
                "model_label": summary.get("model_label"),
                "system": summary.get("system"),
                "harness_id": summary.get("harness_id"),
                "documents_available": summary.get("documents_available"),
                "mean_latency_ms": summary.get("mean_latency_ms"),
                "latency_p50_ms": percentile(
                    [
                        score.get("cost_latency", {}).get("latency_ms")
                        for score in scores
                        if isinstance(score.get("cost_latency", {}).get("latency_ms"), (int, float))
                    ],
                    0.50,
                ),
                "latency_p95_ms": percentile(
                    [
                        score.get("cost_latency", {}).get("latency_ms")
                        for score in scores
                        if isinstance(score.get("cost_latency", {}).get("latency_ms"), (int, float))
                    ],
                    0.95,
                ),
                "mean_input_tokens": summary.get("mean_input_tokens"),
                "mean_output_tokens": summary.get("mean_output_tokens"),
                "mean_estimated_cost_usd": cost,
                "cost_estimation_status": summary.get("cost_estimation_status"),
                "cost_per_correct_benchmark_unit": cost / correct_units if cost is not None and correct_units else None,
                "correct_benchmark_units": correct_units,
            }
        )
    return rows


def validation_decision(summaries: list[dict[str, Any]], split: str) -> dict[str, Any]:
    eligible = [
        row
        for row in summaries
        if (to_float(row.get("benchmark_quality")) or 0.0) > 0.0
        and (to_float(row.get("schema_valid_rate")) or 0.0) >= 0.9
        and (to_float(row.get("quote_validity_rate")) or 0.0) >= 0.9
    ]
    quality_ranked = sorted(eligible, key=lambda row: to_float(row.get("benchmark_quality")) or 0.0, reverse=True)
    cost_ranked = sorted(
        [row for row in eligible if isinstance(row.get("mean_estimated_cost_usd"), (int, float))],
        key=lambda row: (
            -(to_float(row.get("benchmark_quality")) or 0.0),
            to_float(row.get("mean_estimated_cost_usd")) or float("inf"),
        ),
    )
    best_quality = quality_ranked[0] if quality_ranked else None
    best_cost_effective = cost_ranked[0] if cost_ranked else None
    selected = []
    for row in [best_quality, best_cost_effective]:
        if row and row["condition"] not in selected:
            selected.append(row["condition"])
    return {
        "split": split,
        "held_out_test_used": split == "test",
        "eligible_conditions": [row["condition"] for row in eligible],
        "quality_rank_order": [row["condition"] for row in quality_ranked],
        "selected_final_candidates": selected[:2],
        "best_quality_candidate": best_quality["condition"] if best_quality else None,
        "best_cost_effective_candidate": best_cost_effective["condition"] if best_cost_effective else None,
        "decision": "select_final_candidates" if selected else "no_candidate_selected",
        "notes": [
            "Candidates require positive benchmark quality plus schema and quote validity gates.",
            "Relaxed harnesses without canonical projection are excluded from final-candidate selection.",
        ],
    }


def command_stage_c(args: argparse.Namespace) -> int:
    all_scores: dict[str, list[dict[str, Any]]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    model_specs = load_model_specs(Path(args.registry))
    if args.stage_a_dir:
        stage_scores, stage_metadata = score_stage_a_outputs(
            Path(args.stage_a_dir),
            Path(args.exect_root),
            Path(args.markup_root),
            Path(args.schema),
            set(args.harnesses) if args.harnesses else None,
        )
        all_scores.update(stage_scores)
        metadata.update(stage_metadata)

    eval_scores, eval_metadata = load_existing_evaluation_conditions(
        args.evaluation_condition,
        parse_condition_model(args.condition_model),
    )
    all_scores.update(eval_scores)
    metadata.update(eval_metadata)
    for meta in metadata.values():
        meta["model_specs"] = model_specs

    summaries_by_label = {
        label: summarize_condition(label, scores, metadata[label])
        for label, scores in all_scores.items()
        if scores
    }
    summaries = list(summaries_by_label.values())
    output_dir = Path(args.output_dir)
    write_csv(output_dir / "model_harness_table.csv", summaries)
    write_csv(output_dir / "field_prf_table.csv", build_field_prf_table(all_scores))
    write_json(
        output_dir / "bootstrap_intervals.json",
        bootstrap_stage_c(all_scores, summaries_by_label, args.bootstrap_iterations, args.seed),
    )
    write_csv(output_dir / "cost_latency_table.csv", build_cost_latency_table(summaries, all_scores))
    write_json(output_dir / "validation_decision.json", validation_decision(summaries, args.split))
    write_json(
        output_dir / "stage_c_manifest.json",
        {
            "stage": "stage_c_validation",
            "split": args.split,
            "stage_a_dir": args.stage_a_dir,
            "evaluation_conditions": args.evaluation_condition or [],
            "conditions": sorted(all_scores),
            "outputs": {
                "model_harness_table": str(output_dir / "model_harness_table.csv"),
                "field_prf_table": str(output_dir / "field_prf_table.csv"),
                "bootstrap_intervals": str(output_dir / "bootstrap_intervals.json"),
                "cost_latency_table": str(output_dir / "cost_latency_table.csv"),
                "validation_decision": str(output_dir / "validation_decision.json"),
            },
        },
    )
    print(f"wrote Stage C validation matrix for {len(summaries)} scored conditions")
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
    stage_a.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        help="OpenAI reasoning effort for reasoning models; use low/minimal for extraction smoke runs.",
    )
    stage_a.add_argument(
        "--google-thinking-budget",
        type=int,
        help="Google thinking token budget. Use 0 or a small value for extraction smoke runs.",
    )
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

    stage_c = subparsers.add_parser(
        "stage-c-validation",
        help="Build Stage C validation tables and candidate decision from scored validation artifacts.",
    )
    stage_c.add_argument("--stage-a-dir", help="Stage A-style validation run directory to score canonical H0 outputs.")
    stage_c.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    stage_c.add_argument(
        "--evaluation-condition",
        action="append",
        help="Existing evaluation condition as LABEL:SYSTEM:HARNESS_ID:EVALUATION_DIR.",
    )
    stage_c.add_argument(
        "--condition-model",
        action="append",
        help="Map an evaluation condition to a registry model label, as CONDITION=REGISTRY_MODEL_LABEL.",
    )
    stage_c.add_argument("--harnesses", nargs="+")
    stage_c.add_argument("--output-dir", default=str(DEFAULT_STAGE_C_OUTPUT_DIR))
    stage_c.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    stage_c.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    stage_c.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    stage_c.add_argument("--split", default="validation", choices=["development", "validation", "test"])
    stage_c.add_argument("--bootstrap-iterations", type=int, default=1000)
    stage_c.add_argument("--seed", type=int, default=1729)
    stage_c.set_defaults(func=command_stage_c)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
