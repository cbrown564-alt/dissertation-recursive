#!/usr/bin/env python3
"""Final full-field evaluation runner (WP1-WP4 of docs/27_final_full_field_evaluation_plan.md).

Handles local open-model candidates only. Closed-model candidates are evaluated separately.

Usage:
    python src/final_full_field.py setup
    python src/final_full_field.py import-existing --source-dir runs/local_models/stage_l5_35b_full
    python src/final_full_field.py run-validation --models gemma_26b_local gemma_31b_local
    python src/final_full_field.py build-report
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from direct_baselines import load_split_ids, parse_json_response, write_json, write_text
from evaluate import DEFAULT_MARKUP_ROOT, flatten_summary, load_gold, score_document
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document
from local_models import run_local_one, check_ollama_connectivity
from model_expansion import projected_canonical, write_csv
from model_registry import DEFAULT_REGISTRY, load_model_specs, write_registry_snapshot
from validate_extraction import DEFAULT_SCHEMA


DEFAULT_OUTPUT_ROOT = Path("runs/final_full_field")

# Full composite weights from the evaluation plan (docs/27).
# Penalises harnesses that don't extract medication_full, frequency, schema, quotes.
COMPOSITE_WEIGHTS = {
    "medication_name_f1": 0.20,
    "medication_full_f1": 0.15,
    "seizure_type_f1_collapsed": 0.15,
    "epilepsy_diagnosis_accuracy_collapsed": 0.10,
    "investigation_score": 0.10,
    "current_seizure_frequency_loose_accuracy": 0.10,
    "temporal_accuracy": 0.10,
    "schema_valid_rate": 0.05,
    "quote_validity_rate": 0.05,
}

# Benchmark-field composite: only the 5 fields every local harness actually extracts.
# Use this for apples-to-apples comparison between H6/H6fs and frontier systems.
BENCHMARK_COMPOSITE_WEIGHTS = {
    "medication_name_f1": 0.30,
    "seizure_type_f1_collapsed": 0.25,
    "epilepsy_diagnosis_accuracy_collapsed_or_plain": 0.20,
    "eeg_accuracy": 0.125,
    "mri_accuracy": 0.125,
}

# Frontier baselines for the comparison table
FRONTIER_BASELINES = [
    {
        "system": "GPT-4.1-mini S2 (frontier validation)",
        "medication_name_f1": 0.852, "medication_full_f1": 0.655,
        "seizure_type_f1_collapsed": 0.610, "epilepsy_diagnosis_accuracy": 0.700,
        "epilepsy_diagnosis_accuracy_collapsed": 0.700,
        "eeg_accuracy": 0.950, "mri_accuracy": 1.000,
        "current_seizure_frequency_loose_accuracy": 0.075, "temporal_accuracy": 0.835,
        "schema_valid_rate": None, "quote_validity_rate": None,
        "mean_latency_ms": None, "model_location": "API", "cost_per_doc_usd": 0.003,
    },
    {
        "system": "GPT-4.1-mini E3 (frontier validation)",
        "medication_name_f1": 0.872, "medication_full_f1": 0.707,
        "seizure_type_f1_collapsed": 0.633, "epilepsy_diagnosis_accuracy": 0.725,
        "epilepsy_diagnosis_accuracy_collapsed": 0.725,
        "eeg_accuracy": 0.975, "mri_accuracy": 0.975,
        "current_seizure_frequency_loose_accuracy": 0.125, "temporal_accuracy": 0.914,
        "schema_valid_rate": None, "quote_validity_rate": None,
        "mean_latency_ms": None, "model_location": "API", "cost_per_doc_usd": 0.005,
    },
]

# Maps a source run directory pattern to the model labels expected inside it.
# Used to discover existing artifacts to import.
KNOWN_SOURCE_DIRS = {
    "stage_l5_35b_full": ["qwen_35b_local"],
    "stage_l5_27b_full": ["qwen_27b_local"],
    "stage_l5_gemma4_full": ["gemma_4b_local"],
    "stage_l5_h6fs_gemma4": ["gemma_4b_local"],
    "stage_l5_h6fs_9b": ["qwen_9b_local"],
    "stage_l5_n2_9b_full": ["qwen_9b_local"],
    "stage_l5_n3_4b_full": ["qwen_4b_local"],
}


def _git_commit_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def command_setup(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    validation_dir = output_root / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)

    specs = load_model_specs(Path(args.registry))
    commit = _git_commit_hash()

    local_labels = [
        k for k, v in specs.items()
        if getattr(v, "provider", "") == "ollama" or getattr(v, "region", "") == "local"
    ]

    freeze = {
        "freeze_version": "2026-05-09-v1",
        "scorer_version": "ExECTv2-corrected",
        "code_commit": commit,
        "registry_path": str(args.registry),
        "splits_path": str(args.splits),
        "validation_split": "validation",
        "test_split": "test",
        "local_model_labels": local_labels,
        "harnesses": ["H6_benchmark_only_coarse_json", "H6fs_benchmark_only_coarse_json"],
        "notes": [
            "Closed-model candidates (F1, F2, F7) evaluated separately.",
            "Candidates may only be added by updating candidate_registry.json with a reason.",
            "Validation is used for final candidate selection; test is run once per promoted system.",
        ],
    }
    write_json(output_root / "experiment_freeze.json", freeze)

    candidate_registry = {
        "version": "2026-05-09-v1",
        "local_candidates": [
            {
                "id": "F3", "model_label": "qwen_35b_local", "harness": "H6fs_benchmark_only_coarse_json",
                "purpose": "Primary local deployment candidate",
                "status": "existing_run", "source_dir": "runs/local_models/stage_l5_35b_full",
            },
            {
                "id": "F3-H6", "model_label": "qwen_35b_local", "harness": "H6_benchmark_only_coarse_json",
                "purpose": "Local deployment ablation (plain harness)",
                "status": "existing_run", "source_dir": "runs/local_models/stage_l5_35b_full",
            },
            {
                "id": "F4", "model_label": "qwen_27b_local", "harness": "H6_benchmark_only_coarse_json",
                "purpose": "Best local medication-F1 candidate",
                "status": "existing_run", "source_dir": "runs/local_models/stage_l5_27b_full",
            },
            {
                "id": "F4-fs", "model_label": "qwen_27b_local", "harness": "H6fs_benchmark_only_coarse_json",
                "purpose": "Best local medication-F1 with few-shot (ablation)",
                "status": "existing_run", "source_dir": "runs/local_models/stage_l5_27b_full",
            },
            {
                "id": "F5", "model_label": "gemma_4b_local", "harness": "H6_benchmark_only_coarse_json",
                "purpose": "Best local diagnosis candidate (gemma4:e4b)",
                "status": "existing_run", "source_dir": "runs/local_models/stage_l5_gemma4_full",
            },
            {
                "id": "F5-fs", "model_label": "gemma_4b_local", "harness": "H6fs_benchmark_only_coarse_json",
                "purpose": "gemma4:e4b few-shot ablation",
                "status": "existing_run", "source_dir": "runs/local_models/stage_l5_h6fs_gemma4",
            },
            {
                "id": "F5b", "model_label": "gemma_26b_local", "harness": "H6_benchmark_only_coarse_json",
                "purpose": "Expanded gemma4 scale: 26B",
                "status": "needs_run",
            },
            {
                "id": "F5b-fs", "model_label": "gemma_26b_local", "harness": "H6fs_benchmark_only_coarse_json",
                "purpose": "Expanded gemma4 scale: 26B few-shot ablation",
                "status": "needs_run",
            },
            {
                "id": "F5b-full", "model_label": "gemma_26b_local", "harness": "H6full_benchmark_coarse_json",
                "purpose": "Expanded gemma4 scale: 26B full-field harness (dose/unit/freq/eeg/mri/seizure_freq)",
                "status": "needs_run",
            },
            {
                "id": "F5c", "model_label": "gemma_31b_local", "harness": "H6_benchmark_only_coarse_json",
                "purpose": "Expanded gemma4 scale: 31B",
                "status": "needs_run",
            },
            {
                "id": "F5c-fs", "model_label": "gemma_31b_local", "harness": "H6fs_benchmark_only_coarse_json",
                "purpose": "Expanded gemma4 scale: 31B few-shot ablation",
                "status": "needs_run",
            },
            {
                "id": "F5c-full", "model_label": "gemma_31b_local", "harness": "H6full_benchmark_coarse_json",
                "purpose": "Expanded gemma4 scale: 31B full-field harness (dose/unit/freq/eeg/mri/seizure_freq)",
                "status": "needs_run",
            },
            {
                "id": "9b-ref", "model_label": "qwen_9b_local", "harness": "H6fs_benchmark_only_coarse_json",
                "purpose": "Reference: best 9B system (not a final candidate)",
                "status": "existing_run", "source_dir": "runs/local_models/stage_l5_h6fs_9b",
            },
        ],
    }
    write_json(output_root / "candidate_registry.json", candidate_registry)

    write_registry_snapshot(output_root / "model_registry_snapshot.json", Path(args.registry))

    print(f"Setup complete. Freeze and registry written to {output_root}")
    print("Candidates needing a run:")
    for c in candidate_registry["local_candidates"]:
        if c["status"] == "needs_run":
            print(f"  [{c['id']}] {c['model_label']} / {c['harness']}")
    return 0


def _load_call_latencies(source_dir: Path) -> dict[tuple[str, str, str], float | None]:
    """Load per-document latency from an existing call_report.csv."""
    report_path = source_dir / "call_report.csv"
    latencies: dict[tuple[str, str, str], float | None] = {}
    if not report_path.exists():
        return latencies
    with report_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row.get("model_label", ""), row.get("harness_id", ""), row.get("document_id", ""))
            try:
                latencies[key] = float(row["latency_ms"])
            except (KeyError, ValueError, TypeError):
                latencies[key] = None
    return latencies


def command_import_existing(args: argparse.Namespace) -> int:
    """Import and re-score canonical_projection.json files from a prior run directory."""
    source_dir = Path(args.source_dir)
    calls_dir = source_dir / "calls"
    if not calls_dir.exists():
        print(f"ERROR: calls/ directory not found in {source_dir}", file=sys.stderr)
        return 1

    output_root = Path(args.output_root)
    validation_dir = output_root / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)

    gold = load_gold(Path(args.markup_root), Path(args.exect_root))
    schema_path = Path(args.schema)
    latencies = _load_call_latencies(source_dir)

    # Discover all canonical_projection.json files
    # Path: calls/<model_label>/<harness_id>/<doc_id>/canonical_projection.json
    by_condition: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for proj_path in sorted(calls_dir.rglob("canonical_projection.json")):
        parts = proj_path.relative_to(calls_dir).parts
        if len(parts) != 4:
            continue
        model_label, harness_id, doc_id, _ = parts

        if args.models and model_label not in args.models:
            continue

        if doc_id not in gold:
            continue

        try:
            data = json.loads(proj_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  skip {proj_path}: {exc}", file=sys.stderr)
            continue

        doc = preprocess_document(doc_id, Path(args.exect_root))
        doc_score = score_document(data, doc["text"], gold[doc_id], schema_path)

        lat = latencies.get((model_label, harness_id, doc_id))
        if lat is not None:
            doc_score.setdefault("cost_latency", {})["latency_ms"] = lat

        key = (model_label, harness_id)
        by_condition.setdefault(key, []).append(doc_score)

    if not by_condition:
        print(f"No canonical projections found in {source_dir}", file=sys.stderr)
        return 1

    # Score and write per-condition summaries
    summaries_written = []
    for (model_label, harness_id), doc_scores in sorted(by_condition.items()):
        system = f"{model_label}:{harness_id}"
        summary = flatten_summary(system, doc_scores)
        summary["model_label"] = model_label
        summary["harness_id"] = harness_id
        summary["source_dir"] = str(source_dir)
        summary["documents"] = len(doc_scores)

        cond_dir = validation_dir / "imported" / model_label / harness_id
        cond_dir.mkdir(parents=True, exist_ok=True)
        write_json(cond_dir / "scored_summary.json", summary)
        summaries_written.append(summary)
        print(
            f"  Imported {model_label}/{harness_id}: {len(doc_scores)} docs  "
            f"med_f1={summary.get('medication_name_f1', 'n/a'):.3f}  "
            f"sz_f1={summary.get('seizure_type_f1_collapsed', 'n/a'):.3f}  "
            f"dx={summary.get('epilepsy_diagnosis_accuracy', 'n/a'):.3f}"
        )

    print(f"Imported {len(summaries_written)} condition(s) from {source_dir}")
    return 0


def _score_full_field_rows(
    rows: list[dict[str, Any]],
    output_dir: Path,
    exect_root: Path,
    markup_root: Path,
    schema_path: Path,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Score a set of call rows and return per-condition flatten_summary dicts."""
    gold = load_gold(markup_root, exect_root)
    by_condition: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for row in rows:
        model_label = row["model_label"]
        harness_id = row["harness_id"]
        doc_id = row["document_id"]
        if doc_id not in gold:
            continue

        run_root = output_dir / "calls" / model_label / harness_id / doc_id
        raw_path = run_root / "raw_response.txt"
        if not raw_path.exists():
            continue

        text = raw_path.read_text(encoding="utf-8")
        parsed = parse_json_response(text)
        payload = parsed.data if isinstance(parsed.data, dict) else None
        if payload is None:
            continue

        doc = preprocess_document(doc_id, exect_root)
        proj_row = {k: "" if v is None else str(v) for k, v in row.items()}
        projected = projected_canonical(
            doc_id, harness_id, model_label, payload, proj_row, doc,
            require_present_evidence=False,
        )
        (run_root / "canonical_projection.json").write_text(
            json.dumps(projected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        doc_score = score_document(projected, doc["text"], gold[doc_id], schema_path)
        key = (model_label, harness_id)
        by_condition.setdefault(key, []).append(doc_score)

    scores: dict[tuple[str, str], dict[str, Any]] = {}
    for (model_label, harness_id), doc_scores in by_condition.items():
        system = f"{model_label}:{harness_id}"
        summary = flatten_summary(system, doc_scores)
        summary["model_label"] = model_label
        summary["harness_id"] = harness_id
        summary["documents"] = len(doc_scores)
        scores[(model_label, harness_id)] = summary
    return scores


def command_run_validation(args: argparse.Namespace) -> int:
    """Run new local model candidates on the validation split."""
    import os
    os.environ.setdefault("OLLAMA_BASE_URL", args.ollama_base_url)

    conn = check_ollama_connectivity(args.ollama_base_url)
    if conn["status"] != "ok":
        print(f"ERROR: Ollama not reachable at {args.ollama_base_url}: {conn.get('error')}", file=sys.stderr)
        return 1

    available = conn.get("models", [])
    specs = load_model_specs(Path(args.registry))
    model_labels: list[str] = args.models or ["gemma_26b_local", "gemma_31b_local"]
    harness_ids: list[str] = args.harnesses or [
        "H6_benchmark_only_coarse_json",
        "H6fs_benchmark_only_coarse_json",
        "H6full_benchmark_coarse_json",
    ]
    document_ids = load_split_ids(Path(args.splits), "validation", args.limit)

    # Check models are pulled
    for label in model_labels:
        if label not in specs:
            print(f"ERROR: {label} not in registry {args.registry}", file=sys.stderr)
            return 1
        mid = specs[label].provider_model_id
        if not any(mid in m for m in available):
            print(f"ERROR: {mid} not pulled in Ollama. Run: ollama pull {mid}", file=sys.stderr)
            return 1

    output_root = Path(args.output_root)
    validation_dir = output_root / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    write_registry_snapshot(validation_dir / "model_registry_snapshot.json", Path(args.registry))

    call_rows: list[dict[str, Any]] = []
    for model_label in model_labels:
        for harness_id in harness_ids:
            for doc_id in document_ids:
                row = run_local_one(
                    model_label, harness_id, doc_id, validation_dir,
                    Path(args.registry), Path(args.exect_root), Path(args.schema),
                    args.temperature, args.max_output_tokens, args.ollama_base_url,
                    stage_tag="final_full_field_validation",
                )
                call_rows.append(row)
                print(f"{row['status']}: {model_label} {harness_id} {doc_id}", flush=True)

    write_csv(validation_dir / "call_report_new.csv", call_rows)

    scores = _score_full_field_rows(
        call_rows, validation_dir, Path(args.exect_root),
        Path(args.markup_root), Path(args.schema),
    )

    for (model_label, harness_id), summary in scores.items():
        cond_dir = validation_dir / "new_runs" / model_label / harness_id
        cond_dir.mkdir(parents=True, exist_ok=True)
        write_json(cond_dir / "scored_summary.json", summary)
        print(
            f"  Scored {model_label}/{harness_id}: {summary.get('documents')} docs  "
            f"med_f1={summary.get('medication_name_f1', 'n/a'):.3f}  "
            f"sz_f1={summary.get('seizure_type_f1_collapsed', 'n/a'):.3f}  "
            f"dx={summary.get('epilepsy_diagnosis_accuracy', 'n/a'):.3f}"
        )

    print(f"\nRun complete. {len(scores)} condition(s) scored.")
    return 0


def _compute_composite(summary: dict[str, Any]) -> float | None:
    eeg = summary.get("eeg_accuracy")
    mri = summary.get("mri_accuracy")
    inv_vals = [v for v in [eeg, mri] if v is not None]
    inv_score = sum(inv_vals) / len(inv_vals) if inv_vals else None

    fields = {
        "medication_name_f1": summary.get("medication_name_f1"),
        "medication_full_f1": summary.get("medication_full_f1"),
        "seizure_type_f1_collapsed": summary.get("seizure_type_f1_collapsed"),
        "epilepsy_diagnosis_accuracy_collapsed": (
            summary.get("epilepsy_diagnosis_accuracy_collapsed")
            or summary.get("epilepsy_diagnosis_accuracy")
        ),
        "investigation_score": inv_score,
        "current_seizure_frequency_loose_accuracy": summary.get("current_seizure_frequency_loose_accuracy"),
        "temporal_accuracy": summary.get("temporal_accuracy"),
        "schema_valid_rate": summary.get("schema_valid_rate"),
        "quote_validity_rate": summary.get("quote_validity_rate"),
    }
    total_weight = 0.0
    weighted_sum = 0.0
    for field, weight in COMPOSITE_WEIGHTS.items():
        val = fields.get(field)
        if val is not None:
            weighted_sum += weight * val
            total_weight += weight
    return weighted_sum / total_weight if total_weight > 0 else None


def _compute_benchmark_composite(summary: dict[str, Any]) -> float | None:
    """Composite over the 5 fields every H6-family harness actually extracts.
    Use this to compare local H6/H6fs systems fairly against frontier systems.
    """
    dx = (
        summary.get("epilepsy_diagnosis_accuracy_collapsed")
        or summary.get("epilepsy_diagnosis_accuracy")
    )
    fields = {
        "medication_name_f1": summary.get("medication_name_f1"),
        "seizure_type_f1_collapsed": summary.get("seizure_type_f1_collapsed"),
        "epilepsy_diagnosis_accuracy_collapsed_or_plain": dx,
        "eeg_accuracy": summary.get("eeg_accuracy"),
        "mri_accuracy": summary.get("mri_accuracy"),
    }
    total_weight = 0.0
    weighted_sum = 0.0
    for field, weight in BENCHMARK_COMPOSITE_WEIGHTS.items():
        val = fields.get(field)
        if val is not None:
            weighted_sum += weight * val
            total_weight += weight
    return weighted_sum / total_weight if total_weight > 0 else None


def _load_all_summaries(validation_dir: Path) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for subdir in ["imported", "new_runs"]:
        parent = validation_dir / subdir
        if not parent.exists():
            continue
        for summary_path in sorted(parent.rglob("scored_summary.json")):
            try:
                s = json.loads(summary_path.read_text(encoding="utf-8"))
                s["_summary_path"] = str(summary_path)
                summaries.append(s)
            except Exception as exc:
                print(f"  skip {summary_path}: {exc}", file=sys.stderr)
    return summaries


def command_build_report(args: argparse.Namespace) -> int:
    """Assemble all imported and new-run summaries into the final comparison tables."""
    output_root = Path(args.output_root)
    validation_dir = output_root / "validation"

    summaries = _load_all_summaries(validation_dir)
    if not summaries:
        print("No scored summaries found. Run import-existing or run-validation first.", file=sys.stderr)
        return 1

    # Deduplicate: if the same (model_label, harness_id) appears in both imported and new_runs,
    # prefer new_runs (more recent).
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for s in summaries:
        key = (s.get("model_label", ""), s.get("harness_id", ""))
        path = s.get("_summary_path", "")
        if key not in seen or "new_runs" in path:
            seen[key] = s
    summaries = list(seen.values())

    # Primary full-field metrics columns
    primary_cols = [
        "system", "model_label", "harness_id", "documents",
        "medication_name_f1", "medication_full_f1",
        "medication_dose_f1", "medication_dose_unit_f1", "medication_frequency_f1",
        "seizure_type_f1", "seizure_type_f1_collapsed",
        "epilepsy_diagnosis_accuracy", "epilepsy_diagnosis_accuracy_collapsed",
        "eeg_accuracy", "mri_accuracy",
        "current_seizure_frequency_loose_accuracy",
        "current_seizure_frequency_per_letter_accuracy",
        "temporal_accuracy",
        "schema_valid_rate", "quote_presence_rate", "quote_validity_rate",
        "benchmark_composite",
        "composite_score",
        "mean_latency_ms", "model_location", "cost_per_doc_usd",
    ]

    report_rows: list[dict[str, Any]] = []

    # Frontier baselines first
    for b in FRONTIER_BASELINES:
        row = {col: None for col in primary_cols}
        row.update(b)
        row["system"] = b["system"]
        row["benchmark_composite"] = _compute_benchmark_composite(b)
        row["composite_score"] = _compute_composite(b)
        report_rows.append(row)

    # Local model summaries
    def _sort_key(s: dict[str, Any]) -> tuple[float, str, str]:
        bc = _compute_benchmark_composite(s) or 0.0
        return (-bc, s.get("model_label", ""), s.get("harness_id", ""))

    for s in sorted(summaries, key=_sort_key):
        row = {col: None for col in primary_cols}
        row.update(s)
        row["system"] = f"{s.get('model_label', '')} / {s.get('harness_id', '')}"
        row["model_location"] = "local"
        row["cost_per_doc_usd"] = 0.0
        row["benchmark_composite"] = _compute_benchmark_composite(s)
        row["composite_score"] = _compute_composite(s)
        report_rows.append(row)

    write_csv(validation_dir / "comparison_table.csv", report_rows)

    # Complexity table
    complexity_cols = [
        "system", "model_label", "harness_id",
        "model_location", "mean_latency_ms", "cost_per_doc_usd",
        "documents", "composite_score",
    ]
    complexity_rows = [{col: r.get(col) for col in complexity_cols} for r in report_rows]
    write_csv(validation_dir / "complexity_table.csv", complexity_rows)

    # Print summary
    print("\n=== Final Full-Field Comparison (validation split) ===\n")
    header = f"{'System':<47} {'Med F1':>7} {'Sz F1':>7} {'Dx Acc':>7} {'EEG':>6} {'MRI':>6} {'BenchComp':>10} {'FullComp':>9}"
    print(header)
    print("-" * len(header))
    for r in report_rows:
        name = r.get("system", "")[:46]
        med = r.get("medication_name_f1")
        sz = r.get("seizure_type_f1_collapsed")
        dx = r.get("epilepsy_diagnosis_accuracy")
        eeg = r.get("eeg_accuracy")
        mri = r.get("mri_accuracy")
        bc = r.get("benchmark_composite")
        comp = r.get("composite_score")
        def _fmt(v: float | None, w: int = 7) -> str:
            return f"{v:.3f}".rjust(w) if v is not None else "n/a".rjust(w)
        print(
            f"{name:<47} {_fmt(med)} {_fmt(sz)} {_fmt(dx)} {_fmt(eeg, 6)} {_fmt(mri, 6)}"
            f" {_fmt(bc, 10)} {_fmt(comp, 9)}"
        )
    print(f"\nNote: BenchComp = benchmark-field composite (med+sz+dx+eeg+mri, apples-to-apples).")
    print(f"      FullComp  = plan composite (all fields; penalises H6/H6fs for missing dose/freq/quotes).")

    print(f"\ncomparison_table.csv written to {validation_dir}")
    return 0


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--splits", default=str(DEFAULT_SPLITS))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Final full-field evaluation runner (open models)."
    )
    subparsers = parser.add_subparsers(dest="command")

    # setup
    sp_setup = subparsers.add_parser("setup", help="WP1: create freeze and candidate registry files.")
    _add_common_args(sp_setup)

    # import-existing
    sp_import = subparsers.add_parser(
        "import-existing",
        help="Import and re-score canonical projections from a prior run directory.",
    )
    _add_common_args(sp_import)
    sp_import.add_argument(
        "--source-dir", required=True,
        help="Path to a prior local_models run directory (must contain calls/).",
    )
    sp_import.add_argument("--models", nargs="+", default=None, help="Filter to these model labels.")

    # run-validation
    sp_run = subparsers.add_parser(
        "run-validation",
        help="Run new local model candidates on the validation split.",
    )
    _add_common_args(sp_run)
    sp_run.add_argument("--models", nargs="+", default=None)
    sp_run.add_argument("--harnesses", nargs="+", default=None)
    sp_run.add_argument("--limit", type=int, default=None)
    sp_run.add_argument("--temperature", type=float, default=0.0)
    sp_run.add_argument("--max-output-tokens", type=int, default=4096)
    sp_run.add_argument("--ollama-base-url", default="http://localhost:11434/v1")

    # build-report
    sp_report = subparsers.add_parser(
        "build-report",
        help="Assemble all scored summaries into the final comparison table.",
    )
    _add_common_args(sp_report)

    args = parser.parse_args()
    if args.command == "setup":
        return command_setup(args)
    if args.command == "import-existing":
        return command_import_existing(args)
    if args.command == "run-validation":
        return command_run_validation(args)
    if args.command == "build-report":
        return command_build_report(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
