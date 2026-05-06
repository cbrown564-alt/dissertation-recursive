#!/usr/bin/env python3
"""Run the matched validation artifact chain for the dissertation outputs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from direct_baselines import write_json


DEFAULT_RUN_ROOT = Path("runs/final_validation")
DEFAULT_MODEL = "gpt-4.1-mini"
ALL_STAGES = [
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


def write_manifest(args: argparse.Namespace, paths: RunPaths, stages: set[str], failures: list[dict[str, object]]) -> None:
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
        },
    }
    write_json(paths.root / "final_run_manifest.json", manifest)
    print(f"wrote {paths.root / 'final_run_manifest.json'}")


def command_build(args: argparse.Namespace) -> int:
    paths = run_paths(Path(args.run_root))
    stages = selected_stages(args)
    failures: list[dict[str, object]] = []
    common_split = ["--split", args.split, *optional_limit_args(args.limit)]

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

    write_manifest(args, paths, stages, failures)
    return 1 if failures and args.strict else 0


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
    build.add_argument("--stages", nargs="+", choices=ALL_STAGES, help="Run only selected stages.")
    build.add_argument("--dry-run", action="store_true", help="Print commands without running them.")
    build.add_argument("--strict", action="store_true", help="Stop on the first non-zero stage exit.")
    build.set_defaults(func=command_build)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
