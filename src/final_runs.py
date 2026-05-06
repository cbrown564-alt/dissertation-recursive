#!/usr/bin/env python3
"""Run the matched validation artifact chain for the dissertation outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from direct_baselines import write_json


DEFAULT_RUN_ROOT = Path("runs/final_validation")
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_VALIDATION_DECISION = Path("runs/final_validation/validation_decision.json")
FREEZE_RECORD_NAME = "experiment_freeze.json"
VALIDATION_DECISION_NAME = "validation_decision.json"
ALL_STAGES = [
    "freeze-record",
    "direct",
    "event",
    "evaluation",
    "robustness-generate",
    "robustness-run",
    "robustness-evaluate",
    "secondary-json-yaml",
    "secondary-model-compare",
    "writeup",
    "dashboard",
    "dashboard-validate",
]
FREEZE_INPUTS = [
    "schemas/canonical_extraction.schema.json",
    "data/splits/exectv2_splits.json",
    "data/manifests/dataset_manifest.json",
    "prompts/direct_baselines/s2_direct_json_evidence.md",
    "prompts/direct_baselines/s3_yaml_evidence.md",
    "prompts/event_first/e1_event_extraction.md",
    "prompts/event_first/e3_constrained_aggregation.md",
    "src/direct_baselines.py",
    "src/event_first.py",
    "src/evaluate.py",
    "src/robustness.py",
    "src/secondary_analyses.py",
    "src/writeup_support.py",
    "src/dashboard_export.py",
    "docs/17_experiment_roadmap.md",
]


@dataclass(frozen=True)
class RunPaths:
    root: Path
    direct: Path
    event: Path
    evaluation: Path
    robustness: Path
    secondary_json_yaml: Path
    secondary_model_compare: Path
    writeup: Path
    dashboard_data: Path
    freeze_record: Path
    validation_decision: Path


def run_paths(root: Path) -> RunPaths:
    return RunPaths(
        root=root,
        direct=root / "direct_baselines",
        event=root / "event_first",
        evaluation=root / "evaluation",
        robustness=root / "robustness",
        secondary_json_yaml=root / "secondary_json_yaml",
        secondary_model_compare=root / "secondary_model_compare",
        writeup=root / "writeup",
        dashboard_data=Path("dashboard/public/data/dashboard_data.json"),
        freeze_record=root / FREEZE_RECORD_NAME,
        validation_decision=root / VALIDATION_DECISION_NAME,
    )


def optional_limit_args(limit: int | None) -> list[str]:
    return ["--limit", str(limit)] if limit is not None else []


def selected_stages(args: argparse.Namespace) -> set[str]:
    stages = set(args.stages or ALL_STAGES)
    unknown = sorted(stages - set(ALL_STAGES))
    if unknown:
        raise ValueError(f"unknown stage(s): {', '.join(unknown)}")
    return stages


def command_line(parts: Iterable[object]) -> list[str]:
    return [str(part) for part in parts]


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
    }


def freeze_payload(args: argparse.Namespace, paths: RunPaths, stages: set[str]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Development freeze record for matched dissertation validation/test artifacts.",
        "run_root": str(paths.root),
        "split": args.split,
        "limit": args.limit,
        "provider": args.provider,
        "model": args.model,
        "stages": [stage for stage in ALL_STAGES if stage in stages],
        "frozen_choices": {
            "primary_comparison": ["S2", "E2", "E3"],
            "direct_primary": "S2 direct canonical JSON with evidence",
            "secondary_format_condition": "S3 YAML-to-JSON with evidence",
            "event_first_conditions": {
                "E1": "event extraction",
                "E2": "deterministic event aggregation",
                "E3": "constrained event aggregation",
            },
            "primary_fields": [
                "current ASM name/dose/unit/frequency",
                "seizure frequency with temporal scope",
                "seizure type",
                "EEG result where stated",
                "MRI result where stated",
                "diagnosis/type",
            ],
            "test_policy": "Run held-out test once after validation comparator and rationale are recorded.",
        },
        "inputs": [artifact_record(Path(item)) for item in FREEZE_INPUTS],
    }


def write_freeze_record(args: argparse.Namespace, paths: RunPaths, stages: set[str]) -> None:
    if args.dry_run:
        print(f"would write {paths.freeze_record}")
        return
    write_json(paths.freeze_record, freeze_payload(args, paths, stages))
    print(f"wrote {paths.freeze_record}")


def validate_test_gate(args: argparse.Namespace) -> dict[str, Any]:
    if args.split != "test":
        return {"required": False, "status": "not_applicable"}
    decision_path = Path(args.validation_decision)
    decision = read_json(decision_path)
    if decision is not None:
        comparator = decision.get("selected_event_first_comparator")
        if comparator in {"E2", "E3", "both"} and decision.get("rationale"):
            return {
                "required": True,
                "status": "passed",
                "validation_decision": str(decision_path),
                "selected_event_first_comparator": comparator,
            }
        raise SystemExit(
            f"validation decision at {decision_path} must include "
            "selected_event_first_comparator (E2, E3, or both) and rationale"
        )
    if args.allow_unfrozen_test:
        return {
            "required": True,
            "status": "overridden",
            "validation_decision": str(decision_path),
            "reason": "--allow-unfrozen-test was supplied",
        }
    raise SystemExit(
        "refusing to run the held-out test split before a validation decision is recorded; "
        f"create one with: {sys.executable} src/final_runs.py decide "
        f"--validation-run-root runs/final_validation --comparator E2 --rationale \"...\" "
        "or pass --allow-unfrozen-test for an explicit override"
    )


def run_command(command: list[str], args: argparse.Namespace, failures: list[dict[str, object]]) -> None:
    print("+ " + " ".join(command), flush=True)
    if args.dry_run:
        return
    completed = subprocess.run(command, check=False)
    if completed.returncode == 0:
        return
    failure = {"command": command, "returncode": completed.returncode}
    failures.append(failure)
    if args.strict:
        raise SystemExit(completed.returncode)
    print(f"warning: command exited {completed.returncode}; continuing so downstream artifact checks can record gaps")


def write_manifest(
    args: argparse.Namespace,
    paths: RunPaths,
    stages: set[str],
    failures: list[dict[str, object]],
    test_gate: dict[str, Any],
) -> None:
    if args.dry_run:
        return
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_root": str(paths.root),
        "split": args.split,
        "limit": args.limit,
        "provider": args.provider,
        "model": args.model,
        "stages": [stage for stage in ALL_STAGES if stage in stages],
        "strict": args.strict,
        "test_gate": test_gate,
        "failures": failures,
        "artifacts": {
            "direct_run_dir": str(paths.direct),
            "event_run_dir": str(paths.event),
            "evaluation_dir": str(paths.evaluation),
            "robustness_dir": str(paths.robustness),
            "secondary_json_yaml_dir": str(paths.secondary_json_yaml),
            "secondary_model_compare_dir": str(paths.secondary_model_compare),
            "writeup_dir": str(paths.writeup),
            "dashboard_data": str(paths.dashboard_data),
            "experiment_freeze": str(paths.freeze_record),
            "validation_decision": str(paths.validation_decision),
        },
    }
    write_json(paths.root / "final_run_manifest.json", manifest)
    print(f"wrote {paths.root / 'final_run_manifest.json'}")


def command_build(args: argparse.Namespace) -> int:
    paths = run_paths(Path(args.run_root))
    stages = selected_stages(args)
    test_gate = validate_test_gate(args)
    failures: list[dict[str, object]] = []
    common_split = ["--split", args.split, *optional_limit_args(args.limit)]

    if "freeze-record" in stages:
        write_freeze_record(args, paths, stages)

    if "direct" in stages:
        run_command(
            command_line(
                [
                    sys.executable,
                    "src/direct_baselines.py",
                    "run",
                    *common_split,
                    "--provider",
                    args.provider,
                    "--model",
                    args.model,
                    "--baselines",
                    "S2",
                    "S3",
                    "--output-dir",
                    paths.direct,
                ]
            ),
            args,
            failures,
        )

    if "event" in stages:
        run_command(
            command_line(
                [
                    sys.executable,
                    "src/event_first.py",
                    "run",
                    *common_split,
                    "--provider",
                    args.provider,
                    "--model",
                    args.model,
                    "--pipelines",
                    "E1",
                    "E2",
                    "E3",
                    "--output-dir",
                    paths.event,
                ]
            ),
            args,
            failures,
        )

    if "evaluation" in stages:
        run_command(
            command_line(
                [
                    sys.executable,
                    "src/evaluate.py",
                    "run",
                    *common_split,
                    "--systems",
                    "S2",
                    "E2",
                    "E3",
                    "--direct-run-dir",
                    paths.direct,
                    "--event-run-dir",
                    paths.event,
                    "--output-dir",
                    paths.evaluation,
                ]
            ),
            args,
            failures,
        )

    if "robustness-generate" in stages:
        run_command(
            command_line(
                [
                    sys.executable,
                    "src/robustness.py",
                    "generate",
                    "--split",
                    args.split,
                    "--limit",
                    args.robustness_limit,
                    "--gan-limit",
                    args.gan_limit,
                    "--include-gan",
                    "--output-dir",
                    paths.robustness,
                ]
            ),
            args,
            failures,
        )

    if "robustness-run" in stages:
        run_command(
            command_line(
                [
                    sys.executable,
                    "src/robustness.py",
                    "run-systems",
                    "--provider",
                    args.provider,
                    "--model",
                    args.model,
                    "--output-dir",
                    paths.robustness,
                ]
            ),
            args,
            failures,
        )

    if "robustness-evaluate" in stages:
        run_command(
            command_line(
                [
                    sys.executable,
                    "src/robustness.py",
                    "evaluate",
                    "--clean-direct-run-dir",
                    paths.direct,
                    "--clean-event-run-dir",
                    paths.event,
                    "--output-dir",
                    paths.robustness,
                ]
            ),
            args,
            failures,
        )

    if "secondary-json-yaml" in stages:
        run_command(
            command_line(
                [
                    sys.executable,
                    "src/secondary_analyses.py",
                    "json-yaml",
                    *common_split,
                    "--direct-run-dir",
                    paths.direct,
                    "--output-dir",
                    paths.secondary_json_yaml,
                ]
            ),
            args,
            failures,
        )

    if "secondary-model-compare" in stages:
        condition = f"{args.model_condition_label}:{args.model_family}:E2:{paths.event}"
        run_command(
            command_line(
                [
                    sys.executable,
                    "src/secondary_analyses.py",
                    "model-compare",
                    *common_split,
                    "--condition",
                    condition,
                    "--reference-condition",
                    args.model_condition_label,
                    "--output-dir",
                    paths.secondary_model_compare,
                ]
            ),
            args,
            failures,
        )

    if "writeup" in stages:
        run_command(
            command_line(
                [
                    sys.executable,
                    "src/writeup_support.py",
                    "build",
                    "--evaluation-dir",
                    paths.evaluation,
                    "--robustness-dir",
                    paths.robustness,
                    "--secondary-dir",
                    paths.secondary_json_yaml,
                    "--secondary-dir",
                    paths.secondary_model_compare,
                    "--output-dir",
                    paths.writeup,
                ]
            ),
            args,
            failures,
        )

    if "dashboard" in stages:
        run_command(
            command_line(
                [
                    sys.executable,
                    "src/dashboard_export.py",
                    "build",
                    "--evaluation-dir",
                    paths.evaluation,
                    "--robustness-dir",
                    paths.robustness,
                    "--direct-run-dir",
                    paths.direct,
                    "--event-run-dir",
                    paths.event,
                    "--secondary-dir",
                    paths.secondary_json_yaml,
                    "--secondary-dir",
                    paths.secondary_model_compare,
                    "--output",
                    paths.dashboard_data,
                ]
            ),
            args,
            failures,
        )

    if "dashboard-validate" in stages:
        run_command(
            command_line(
                [
                    sys.executable,
                    "src/dashboard_export.py",
                    "validate",
                    paths.dashboard_data,
                ]
            ),
            args,
            failures,
        )

    write_manifest(args, paths, stages, failures, test_gate)
    return 1 if failures and args.strict else 0


def command_decide(args: argparse.Namespace) -> int:
    validation_root = Path(args.validation_run_root)
    evaluation_summary = read_json(validation_root / "evaluation" / "evaluation_summary.json")
    freeze_record = read_json(validation_root / FREEZE_RECORD_NAME)
    if evaluation_summary is None:
        raise SystemExit(f"missing validation evaluation summary: {validation_root / 'evaluation/evaluation_summary.json'}")
    if freeze_record is None and not args.allow_missing_freeze:
        raise SystemExit(
            f"missing freeze record: {validation_root / FREEZE_RECORD_NAME}; "
            "rerun validation with the freeze-record stage or pass --allow-missing-freeze"
        )

    decision = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation_run_root": str(validation_root),
        "selected_event_first_comparator": args.comparator,
        "rationale": args.rationale,
        "decided_by": args.decided_by,
        "freeze_record": {
            "path": str(validation_root / FREEZE_RECORD_NAME),
            "exists": freeze_record is not None,
            "sha256": sha256_file(validation_root / FREEZE_RECORD_NAME),
        },
        "primary_artifacts": {
            "evaluation_summary": artifact_record(validation_root / "evaluation" / "evaluation_summary.json"),
            "comparison_table": artifact_record(validation_root / "evaluation" / "comparison_table.csv"),
            "document_scores": artifact_record(validation_root / "evaluation" / "document_scores.json"),
            "final_run_manifest": artifact_record(validation_root / "final_run_manifest.json"),
        },
        "summary_snapshot": {
            "split": evaluation_summary.get("split"),
            "systems": [
                row.get("system")
                for row in evaluation_summary.get("summaries", [])
                if isinstance(row, dict) and row.get("system")
            ],
        },
        "test_policy": "No prompt, schema, aggregation, or scoring changes after this decision except documented blocking defects.",
    }
    output = Path(args.output) if args.output else validation_root / VALIDATION_DECISION_NAME
    write_json(output, decision)
    print(f"wrote {output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build matched validation, write-up, and dashboard artifacts.")
    build.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    build.add_argument("--split", default="validation", choices=["development", "validation", "test"])
    build.add_argument("--limit", type=int, help="Limit documents for a smoke run; omit for the full split.")
    build.add_argument("--provider", default="openai", choices=["stub", "openai"])
    build.add_argument("--model", default=DEFAULT_MODEL)
    build.add_argument("--robustness-limit", type=int, default=5)
    build.add_argument("--gan-limit", type=int, default=5)
    build.add_argument("--model-condition-label", default="primary_model")
    build.add_argument("--model-family", default="closed", choices=["open", "closed", "local", "frontier"])
    build.add_argument("--validation-decision", default=str(DEFAULT_VALIDATION_DECISION))
    build.add_argument("--allow-unfrozen-test", action="store_true", help="Allow a test split run without a recorded validation decision.")
    build.add_argument("--stages", nargs="+", choices=ALL_STAGES, help="Run only selected stages.")
    build.add_argument("--dry-run", action="store_true", help="Print commands without running them.")
    build.add_argument("--strict", action="store_true", help="Stop on the first non-zero stage exit.")
    build.set_defaults(func=command_build)

    decide = subparsers.add_parser("decide", help="Record the validation comparator decision before the held-out test run.")
    decide.add_argument("--validation-run-root", default=str(DEFAULT_RUN_ROOT))
    decide.add_argument("--comparator", required=True, choices=["E2", "E3", "both"])
    decide.add_argument("--rationale", required=True)
    decide.add_argument("--decided-by", default="dissertation_author")
    decide.add_argument("--output", help="Decision output path; defaults to VALIDATION_RUN_ROOT/validation_decision.json.")
    decide.add_argument("--allow-missing-freeze", action="store_true")
    decide.set_defaults(func=command_decide)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
