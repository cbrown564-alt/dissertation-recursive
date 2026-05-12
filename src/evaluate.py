#!/usr/bin/env python3
"""Evaluate direct and event-first canonical outputs against ExECTv2 gold labels."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from core.io import write_csv, write_json
from core.scoring import (
    DEFAULT_MARKUP_ROOT,
    GoldDocument,
    aggregate_set_metric,
    build_field_prf_table,
    classify_frequency_annotation,
    evidence_overlaps_gold,
    extraction_path,
    flatten_summary,
    gold_frequency_part_candidates,
    load_gold,
    load_json,
    medication_name_tuple,
    medication_tuple,
    normalize_value,
    score_document,
    set_prf,
)
from core.datasets import load_split_ids
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, read_text
from validate_extraction import DEFAULT_SCHEMA


DEFAULT_OUTPUT_DIR = Path("runs/evaluation")
DEFAULT_DIRECT_RUN_DIR = Path("runs/direct_baselines")
DEFAULT_EVENT_RUN_DIR = Path("runs/event_first")
DEFAULT_RECOVERY_RUN_DIR = Path("runs/recovery/phase4_prompt_contract")
DEFAULT_FREQUENCY_WORKSTREAM_DIR = Path("runs/frequency_workstream")


def format_metric(value: Any) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) else "n/a"


def evaluate_systems_for_split(
    split: str,
    systems: list[str],
    direct_run_dir: Path,
    event_run_dir: Path,
    recovery_run_dir: Path,
    markup_root: Path,
    exect_root: Path,
    splits_path: Path,
    schema_path: Path,
    limit: int | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    document_ids = load_split_ids(splits_path, split, limit)
    gold = load_gold(markup_root, exect_root)
    all_scores: dict[str, list[dict[str, Any]]] = {system: [] for system in systems}
    args = argparse.Namespace(
        direct_run_dir=str(direct_run_dir),
        event_run_dir=str(event_run_dir),
        recovery_run_dir=str(recovery_run_dir),
    )
    for system in systems:
        for document_id in document_ids:
            data = load_json(extraction_path(system, document_id, args))
            source_text = read_text(exect_root / f"{document_id}.txt")
            document_gold = gold.get(document_id, GoldDocument(document_id=document_id))
            score = score_document(data, source_text, document_gold, schema_path)
            score["document_id"] = document_id
            score["system"] = system
            all_scores[system].append(score)
    summaries = [flatten_summary(system, all_scores[system]) for system in systems]
    return all_scores, summaries


def write_evaluation_outputs(
    output_dir: Path,
    split: str,
    systems: list[str],
    all_scores: dict[str, list[dict[str, Any]]],
    summaries: list[dict[str, Any]],
) -> None:
    write_json(output_dir / "evaluation_summary.json", {"split": split, "systems": systems, "summaries": summaries})
    write_json(output_dir / "document_scores.json", all_scores)
    write_csv(output_dir / "comparison_table.csv", summaries)
    write_csv(output_dir / "field_prf_table.csv", build_field_prf_table(all_scores))


def command_frequency_audit(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    stage_dir = output_dir / "stage_f0"
    markup_root = Path(args.markup_root)
    exect_root = Path(args.exect_root)
    gold = load_gold(markup_root, exect_root)
    validation_ids = load_split_ids(Path(args.splits), "validation", None)

    rows: list[dict[str, Any]] = []
    missed_surfaces: dict[str, int] = {}
    temporal_only_docs: list[str] = []
    for document_id in validation_ids:
        document_gold = gold.get(document_id, GoldDocument(document_id=document_id))
        annotations = document_gold.seizure_frequencies
        annotation_types = [classify_frequency_annotation(item) for item in annotations]
        candidate_parts = gold_frequency_part_candidates(document_gold)
        parse_success = bool(candidate_parts)
        for item in annotations:
            surface = normalize_value(item.get("surface"))
            surface_parts = parse_frequency_expression(surface)
            if surface and surface_parts.get("class") in {"", "unparsed"}:
                missed_surfaces[surface] = missed_surfaces.get(surface, 0) + 1
        has_rate_like = any(kind in {"rate", "seizure_free", "count_only"} for kind in annotation_types)
        if annotations and not has_rate_like:
            temporal_only_docs.append(document_id)
        rows.append(
            {
                "doc_id": document_id,
                "n_annotations": len(annotations),
                "annotation_types": "|".join(annotation_types),
                "parse_success": parse_success,
                "n_parsable_candidates": len(candidate_parts),
                "surfaces": " || ".join(normalize_value(item.get("surface")) for item in annotations if item.get("surface")),
            }
        )

    write_csv(stage_dir / "gold_distribution.csv", rows)
    common_misses = sorted(missed_surfaces.items(), key=lambda item: (-item[1], item[0]))[:10]
    zero = sum(1 for row in rows if row["n_annotations"] == 0)
    one = sum(1 for row in rows if row["n_annotations"] == 1)
    multiple = sum(1 for row in rows if row["n_annotations"] >= 2)
    parse_failures = sum(1 for row in rows if row["n_annotations"] and not row["parse_success"])
    decision = [
        "# Stage F0 Scoring Decision",
        "",
        "Chosen option: Option 1, per-letter binary scoring.",
        "",
        "Rationale: this is the lowest-cost benchmark-aligned metric in the workstream and can be applied to existing single-value outputs without new model calls.",
        "",
        "Implementation notes:",
        "- `current_seizure_frequency_per_letter_accuracy` is scored at document level.",
        "- A document is correct when the extracted `current_seizure_frequency.value` loosely matches any gold seizure-frequency annotation candidate for that letter.",
        "- Gold candidates include structured CSV count/period attributes and parsable raw annotation spans, so seizure-free spans can be matched when the CSV attributes are sparse.",
        "- Letters with no gold seizure-frequency annotation score false for this benchmark metric, which exposes the oracle ceiling for a positive-only per-letter target.",
        "",
        "Validation gold audit:",
        f"- Documents: {len(rows)}",
        f"- 0 annotations: {zero}",
        f"- 1 annotation: {one}",
        f"- 2+ annotations: {multiple}",
        f"- Annotated documents with no parsable candidate: {parse_failures}",
        f"- Temporal/comparative-only documents: {', '.join(temporal_only_docs) if temporal_only_docs else 'none'}",
        "",
        "Most common raw-span parse misses:",
    ]
    decision.extend(f"- {surface}: {count}" for surface, count in common_misses)
    (stage_dir / "scoring_decision.md").parent.mkdir(parents=True, exist_ok=True)
    (stage_dir / "scoring_decision.md").write_text("\n".join(decision) + "\n", encoding="utf-8")

    print(f"wrote {stage_dir / 'gold_distribution.csv'}")
    print(f"wrote {stage_dir / 'scoring_decision.md'}")
    return 0


def command_frequency_rescore(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    stage_dir = output_dir / "stage_f1"
    systems = args.systems
    rows: list[dict[str, Any]] = []
    run_specs = [
        ("final_validation", "validation", Path("runs/final_validation/direct_baselines"), Path("runs/final_validation/event_first")),
        ("final_test", "test", Path("runs/final_test/direct_baselines"), Path("runs/final_test/event_first")),
    ]
    for run_name, split, direct_dir, event_dir in run_specs:
        all_scores, summaries = evaluate_systems_for_split(
            split,
            systems,
            direct_dir,
            event_dir,
            Path(args.recovery_run_dir),
            Path(args.markup_root),
            Path(args.exect_root),
            Path(args.splits),
            Path(args.schema),
        )
        write_evaluation_outputs(stage_dir / run_name, split, systems, all_scores, summaries)
        corrected_dir = Path("runs/recovery/corrected_metrics") / split
        if corrected_dir.exists():
            write_evaluation_outputs(corrected_dir, split, systems, all_scores, summaries)
        for summary in summaries:
            loose = summary.get("current_seizure_frequency_loose_accuracy")
            per_letter = summary.get("current_seizure_frequency_per_letter_accuracy")
            if isinstance(loose, (int, float)) and isinstance(per_letter, (int, float)) and per_letter < loose:
                raise ValueError(f"{run_name} {summary['system']} per-letter accuracy {per_letter} < loose accuracy {loose}")
            rows.append(
                {
                    "run": run_name,
                    "split": split,
                    "system": summary["system"],
                    "loose_acc": loose,
                    "per_letter_acc": per_letter,
                    "benchmark_gap": per_letter - 0.68 if isinstance(per_letter, (int, float)) else None,
                }
            )
    write_csv(stage_dir / "rescored_existing_runs.csv", rows)
    print(f"wrote {stage_dir / 'rescored_existing_runs.csv'}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    systems = args.systems
    output_dir = Path(args.output_dir)
    all_scores, summaries = evaluate_systems_for_split(
        args.split,
        systems,
        Path(args.direct_run_dir),
        Path(args.event_run_dir),
        Path(args.recovery_run_dir),
        Path(args.markup_root),
        Path(args.exect_root),
        Path(args.splits),
        Path(args.schema),
        args.limit,
    )
    write_evaluation_outputs(output_dir, args.split, systems, all_scores, summaries)

    for row in summaries:
        print(
            f"{row['system']}: docs={row['documents_available']}/{row['documents_expected']} "
            f"schema={format_metric(row['schema_valid_rate'])} "
            f"quote_valid={format_metric(row['quote_validity_rate'])} "
            f"med_full_f1={format_metric(row['medication_full_f1'])}"
        )
    print(f"wrote {output_dir / 'evaluation_summary.json'}")
    print(f"wrote {output_dir / 'comparison_table.csv'}")
    print(f"wrote {output_dir / 'field_prf_table.csv'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Score existing canonical run outputs.")
    run.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    run.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    run.add_argument("--splits", default=str(DEFAULT_SPLITS))
    run.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    run.add_argument("--split", default="validation", choices=["development", "validation", "test"])
    run.add_argument("--limit", type=int)
    run.add_argument("--systems", nargs="+", default=["S2", "E2", "E3"], choices=["S2", "S3", "S4", "S5", "E2", "E3"])
    run.add_argument("--direct-run-dir", default=str(DEFAULT_DIRECT_RUN_DIR))
    run.add_argument("--event-run-dir", default=str(DEFAULT_EVENT_RUN_DIR))
    run.add_argument("--recovery-run-dir", default=str(DEFAULT_RECOVERY_RUN_DIR))
    run.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    run.set_defaults(func=command_run)

    audit = subparsers.add_parser("frequency-audit", help="Run Stage F0 seizure-frequency gold audit.")
    audit.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    audit.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    audit.add_argument("--splits", default=str(DEFAULT_SPLITS))
    audit.add_argument("--output-dir", default=str(DEFAULT_FREQUENCY_WORKSTREAM_DIR))
    audit.set_defaults(func=command_frequency_audit)

    rescore = subparsers.add_parser("frequency-rescore", help="Run Stage F1 seizure-frequency rescoring.")
    rescore.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    rescore.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    rescore.add_argument("--splits", default=str(DEFAULT_SPLITS))
    rescore.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    rescore.add_argument("--systems", nargs="+", default=["S2", "E2", "E3"], choices=["S2", "S3", "S4", "S5", "E2", "E3"])
    rescore.add_argument("--recovery-run-dir", default=str(DEFAULT_RECOVERY_RUN_DIR))
    rescore.add_argument("--output-dir", default=str(DEFAULT_FREQUENCY_WORKSTREAM_DIR))
    rescore.set_defaults(func=command_frequency_rescore)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
