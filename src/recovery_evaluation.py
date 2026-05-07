#!/usr/bin/env python3
"""Phase 6 recovery-cycle evaluation with uncertainty and paired comparisons."""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from pathlib import Path
from typing import Any

from direct_baselines import load_split_ids, write_json
from evaluate import (
    DEFAULT_DIRECT_RUN_DIR,
    DEFAULT_EVENT_RUN_DIR,
    DEFAULT_MARKUP_ROOT,
    DEFAULT_RECOVERY_RUN_DIR,
    GoldDocument,
    aggregate_set_metric,
    build_field_prf_table,
    extraction_path,
    flatten_summary,
    load_gold,
    load_json,
    score_document,
    write_csv,
)
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, read_text
from validate_extraction import DEFAULT_SCHEMA


DEFAULT_OUTPUT_DIR = Path("runs/recovery/validation_cycle_01")

SET_METRICS = ["medication_name", "medication_full", "seizure_type"]
ACCURACY_METRICS = [
    "current_seizure_frequency",
    "current_seizure_frequency_relaxed",
    "seizure_frequency_type_linkage",
    "epilepsy_diagnosis",
    "eeg",
    "mri",
]
PRIMARY_METRICS = [
    "medication_name_f1",
    "medication_full_f1",
    "seizure_type_f1",
    "current_seizure_frequency_accuracy",
    "seizure_frequency_type_linkage_accuracy",
    "epilepsy_diagnosis_accuracy",
]
TARGETS = {
    "schema_valid_rate": 0.99,
    "quote_validity_rate": 0.99,
    "temporal_accuracy": 0.95,
    "medication_name_f1": 0.90,
    "medication_full_f1": 0.80,
    "seizure_type_f1": 0.76,
    "current_seizure_frequency_accuracy": 0.70,
    "seizure_frequency_type_linkage_accuracy": 0.75,
    "epilepsy_diagnosis_accuracy": 0.80,
}


def metric_value(summary: dict[str, Any], metric: str) -> float | None:
    value = summary.get(metric)
    return float(value) if isinstance(value, (int, float)) else None


def document_metric_value(score: dict[str, Any], metric: str) -> float:
    field_scores = score.get("field_scores", {})
    if metric in SET_METRICS:
        item = field_scores.get(metric, {})
        return float(item.get("f1", 0.0)) if isinstance(item, dict) else 0.0
    item = field_scores.get(metric, {})
    if isinstance(item, dict):
        return 1.0 if item.get("correct") else 0.0
    return 0.0


def summarize_subset(system: str, scores: list[dict[str, Any]], indexes: list[int]) -> dict[str, Any]:
    return flatten_summary(system, [scores[index] for index in indexes])


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def bootstrap_intervals(
    all_scores: dict[str, list[dict[str, Any]]],
    summaries: list[dict[str, Any]],
    iterations: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    summary_by_system = {row["system"]: row for row in summaries}
    for system, scores in all_scores.items():
        if not scores:
            continue
        for metric in [
            "schema_valid_rate",
            "quote_validity_rate",
            "temporal_accuracy",
            *PRIMARY_METRICS,
            "current_seizure_frequency_relaxed_accuracy",
        ]:
            observed = metric_value(summary_by_system[system], metric)
            if observed is None:
                continue
            samples = []
            for _ in range(iterations):
                indexes = [rng.randrange(len(scores)) for _ in scores]
                sample_summary = summarize_subset(system, scores, indexes)
                sample_value = metric_value(sample_summary, metric)
                if sample_value is not None:
                    samples.append(sample_value)
            rows.append(
                {
                    "system": system,
                    "metric": metric,
                    "observed": observed,
                    "standard_error": statistics.pstdev(samples) if len(samples) > 1 else 0.0,
                    "ci95_low": percentile(samples, 0.025),
                    "ci95_high": percentile(samples, 0.975),
                    "bootstrap_iterations": len(samples),
                }
            )
    return rows


def paired_randomization(
    baseline_scores: list[dict[str, Any]],
    candidate_scores: list[dict[str, Any]],
    metric: str,
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    paired = list(zip(baseline_scores, candidate_scores, strict=False))
    differences = [document_metric_value(candidate, metric) - document_metric_value(baseline, metric) for baseline, candidate in paired]
    observed = sum(differences) / len(differences) if differences else 0.0
    extreme = 0
    for _ in range(iterations):
        randomized = [diff if rng.random() < 0.5 else -diff for diff in differences]
        sampled = sum(randomized) / len(randomized) if randomized else 0.0
        if abs(sampled) >= abs(observed):
            extreme += 1
    return {
        "observed_mean_document_delta": observed,
        "p_value_two_sided": (extreme + 1) / (iterations + 1) if iterations else None,
        "iterations": iterations,
        "paired_documents": len(paired),
    }


def paired_significance(all_scores: dict[str, list[dict[str, Any]]], baseline: str, iterations: int, seed: int) -> dict[str, Any]:
    if baseline not in all_scores:
        return {"baseline": baseline, "comparisons": {}, "error": "baseline system unavailable"}
    comparisons: dict[str, Any] = {}
    for system, scores in all_scores.items():
        if system == baseline:
            continue
        comparisons[system] = {
            metric: paired_randomization(all_scores[baseline], scores, metric, iterations, seed + index)
            for index, metric in enumerate([*SET_METRICS, *ACCURACY_METRICS])
        }
    return {
        "baseline": baseline,
        "method": "paired approximate randomization over document-level metric utilities",
        "comparisons": comparisons,
    }


def metric_failed(score: dict[str, Any], metric: str) -> bool:
    value = document_metric_value(score, metric)
    return value < 1.0


def error_budget(all_scores: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for system, scores in all_scores.items():
        for metric in [*SET_METRICS, *ACCURACY_METRICS]:
            failures = sum(1 for score in scores if metric_failed(score, metric))
            unavailable = sum(1 for score in scores if not score.get("available"))
            schema_invalid = sum(1 for score in scores if score.get("available") and not score.get("schema_valid"))
            quote_invalid = sum(1 for score in scores if score.get("quote_validity", {}).get("invalid_quote_count", 0))
            rows.append(
                {
                    "system": system,
                    "field": metric,
                    "documents": len(scores),
                    "field_failures": failures,
                    "field_failure_rate": failures / len(scores) if scores else 0.0,
                    "unavailable_outputs": unavailable,
                    "schema_invalid_outputs": schema_invalid,
                    "quote_invalid_outputs": quote_invalid,
                }
            )
    return rows


def recovery_decision(summaries: list[dict[str, Any]], significance: dict[str, Any], split: str) -> dict[str, Any]:
    candidates = [row for row in summaries if row["system"] != "S2"]
    ranked = sorted(
        candidates,
        key=lambda row: (
            metric_value(row, "medication_name_f1") or 0.0,
            metric_value(row, "seizure_type_f1") or 0.0,
            metric_value(row, "epilepsy_diagnosis_accuracy") or 0.0,
        ),
        reverse=True,
    )
    best = ranked[0] if ranked else None
    target_status = {}
    if best:
        target_status = {
            metric: {
                "observed": metric_value(best, metric),
                "target": target,
                "met": (metric_value(best, metric) or 0.0) >= target,
            }
            for metric, target in TARGETS.items()
        }
    return {
        "split": split,
        "held_out_test_used": False,
        "candidate_rank_order": [row["system"] for row in ranked],
        "recommended_system": best["system"] if best else None,
        "target_status": target_status,
        "decision": "promote_to_robustness_gate"
        if best and all(item["met"] for item in target_status.values())
        else "continue_recovery_cycle",
        "rationale": "Recovery targets are checked on validation/development only; held-out test remains locked.",
        "paired_significance": significance,
    }


def score_systems(args: argparse.Namespace) -> dict[str, list[dict[str, Any]]]:
    document_ids = load_split_ids(Path(args.splits), args.split, args.limit)
    gold = load_gold(Path(args.markup_root), Path(args.exect_root))
    all_scores: dict[str, list[dict[str, Any]]] = {system: [] for system in args.systems}
    for system in args.systems:
        for document_id in document_ids:
            data = load_json(extraction_path(system, document_id, args))
            source_text = read_text(Path(args.exect_root) / f"{document_id}.txt")
            document_gold = gold.get(document_id, GoldDocument(document_id=document_id))
            score = score_document(data, source_text, document_gold, Path(args.schema))
            score["document_id"] = document_id
            score["system"] = system
            all_scores[system].append(score)
    return all_scores


def write_interval_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["system", "metric", "observed", "standard_error", "ci95_low", "ci95_high", "bootstrap_iterations"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def command_run(args: argparse.Namespace) -> int:
    if args.split == "test":
        raise SystemExit("Phase 6 recovery evaluation must not use the held-out test split.")
    output_dir = Path(args.output_dir)
    all_scores = score_systems(args)
    summaries = [flatten_summary(system, all_scores[system]) for system in args.systems]
    intervals = bootstrap_intervals(all_scores, summaries, args.bootstrap_iterations, args.seed)
    significance = paired_significance(all_scores, args.baseline, args.randomization_iterations, args.seed)
    budget = error_budget(all_scores)
    decision = recovery_decision(summaries, significance, args.split)

    write_json(output_dir / "evaluation_summary.json", {"split": args.split, "systems": args.systems, "summaries": summaries})
    write_json(output_dir / "document_scores.json", all_scores)
    write_json(output_dir / "paired_significance.json", significance)
    write_json(output_dir / "recovery_decision.json", decision)
    write_csv(output_dir / "comparison_table.csv", summaries)
    write_csv(output_dir / "field_prf_table.csv", build_field_prf_table(all_scores))
    write_interval_csv(output_dir / "metric_uncertainty.csv", intervals)
    write_csv(output_dir / "error_budget.csv", budget)

    for row in summaries:
        print(
            f"{row['system']}: docs={row['documents_available']}/{row['documents_expected']} "
            f"schema={row['schema_valid_rate']:.3f} med_name_f1={row['medication_name_f1']:.3f} "
            f"seizure_type_f1={row['seizure_type_f1']:.3f}"
        )
    print(f"wrote {output_dir / 'recovery_decision.json'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    parser.add_argument("--splits", default=str(DEFAULT_SPLITS))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--split", default="validation", choices=["development", "validation", "test"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--systems", nargs="+", default=["S2", "E2", "E3"], choices=["S2", "S3", "S4", "S5", "E2", "E3"])
    parser.add_argument("--baseline", default="S2")
    parser.add_argument("--direct-run-dir", default=str(DEFAULT_DIRECT_RUN_DIR))
    parser.add_argument("--event-run-dir", default=str(DEFAULT_EVENT_RUN_DIR))
    parser.add_argument("--recovery-run-dir", default=str(DEFAULT_RECOVERY_RUN_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--bootstrap-iterations", type=int, default=1000)
    parser.add_argument("--randomization-iterations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=1701)
    parser.set_defaults(func=command_run)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
