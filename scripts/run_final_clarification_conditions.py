#!/usr/bin/env python3
"""Materialize and optionally run selected final-clarification conditions."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.io import write_json, write_text
from model_registry import load_model_specs


API_RUNNER_HARNESSES = {
    "H6_benchmark_only_coarse_json",
    "H6fs_benchmark_only_coarse_json",
    "H7_extract_then_normalize",
    "D3_candidate_plus_verifier",
    "H8_evidence_later",
}
LOCAL_RUNNER_HARNESSES = {
    "H6_benchmark_only_coarse_json",
    "H6fs_benchmark_only_coarse_json",
    "H6full_benchmark_coarse_json",
    "H7_extract_then_normalize",
    "H6fs_ev_resolver",
}


def _load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _selected_conditions(config: dict[str, Any]) -> list[dict[str, Any]]:
    plan = config.get("selected_run_plan") or {}
    conditions = plan.get("conditions") or []
    if not isinstance(conditions, list):
        raise ValueError("selected_run_plan.conditions must be a list")
    return [condition for condition in conditions if isinstance(condition, dict)]


def _filter_conditions(
    conditions: list[dict[str, Any]],
    ids: list[str] | None,
    tiers: list[str] | None,
    models: list[str] | None,
    harnesses: list[str] | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    result = []
    for condition in conditions:
        if ids and condition.get("id") not in ids:
            continue
        if tiers and condition.get("tier") not in tiers:
            continue
        if models and condition.get("model") not in models:
            continue
        if harnesses and condition.get("harness") not in harnesses:
            continue
        result.append(condition)
    return result[:limit] if limit else result


def _provider_for_condition(condition: dict[str, Any], registry_path: Path, aliases: dict[str, str]) -> str:
    specs = load_model_specs(registry_path)
    model_label = aliases.get(str(condition["model"]), str(condition["model"]))
    spec = specs.get(model_label)
    return spec.provider if spec else "unknown"


def _condition_command(
    condition: dict[str, Any],
    provider: str,
    output_dir: Path,
    docs_per_condition: int,
    config_path: Path,
    stub_calls: bool,
) -> list[str]:
    condition_dir = output_dir / str(condition["id"])
    model = str(condition["model"])
    harness = str(condition["harness"])
    prompt_style = str(condition.get("prompt_style") or "internal")
    base_args = [
        "--splits",
        "data/splits/exectv2_splits.json",
        "--split",
        "validation",
        "--limit",
        str(docs_per_condition),
        "--models",
        model,
        "--harnesses",
        harness,
        "--prompt-style",
        prompt_style,
        "--output-dir",
        str(condition_dir),
    ]
    if provider == "ollama":
        if harness not in LOCAL_RUNNER_HARNESSES:
            raise ValueError(f"local runner does not support harness {harness}")
        return [sys.executable, "src/local_models.py", "stage-l5", *base_args]
    if harness not in API_RUNNER_HARNESSES:
        raise ValueError(f"API diagnostic runner does not support harness {harness}")
    command = [sys.executable, "src/model_expansion.py", "h6-h7-clean-diagnostic", *base_args]
    if stub_calls:
        command.append("--stub-calls")
    if provider == "google":
        command.extend(["--google-thinking-budget", "0"])
    return command


def _command_to_text(command: list[str]) -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in command)


def _write_manifest(output_dir: Path, rows: list[dict[str, Any]], selected_ids: list[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "launch_manifest.json",
        {
            "selected_condition_ids": selected_ids,
            "conditions": rows,
        },
    )
    csv_path = output_dir / "launch_commands.csv"
    if rows:
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8")
    lines = ["# Final Clarification Launch Commands", ""]
    for row in rows:
        lines.extend([f"## {row['id']}", "", f"```bash\n{row['command']}\n```", ""])
    write_text(output_dir / "launch_commands.md", "\n".join(lines))


def _has_provider_credentials(provider: str) -> bool:
    if provider == "openai":
        return bool(os.environ.get("OPENAI_API_KEY"))
    if provider == "google":
        return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    if provider == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/final_clarification_matrix.yaml")
    parser.add_argument("--registry", default="configs/model_registry.yaml")
    parser.add_argument("--output-dir", default="runs/final_clarification")
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--tiers", nargs="+")
    parser.add_argument("--models", nargs="+")
    parser.add_argument("--harnesses", nargs="+")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--execute", action="store_true", help="Run selected conditions after writing launch files.")
    parser.add_argument("--stub-calls", action="store_true", help="Use provider stubs for API conditions.")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    registry_path = Path(args.registry)
    output_dir = Path(args.output_dir)
    config = _load_config(config_path)
    plan = config.get("selected_run_plan") or {}
    docs_per_condition = int(plan.get("documents_per_condition") or 40)
    aliases = config.get("model_registry_aliases") or {}
    conditions = _filter_conditions(
        _selected_conditions(config),
        args.ids,
        args.tiers,
        args.models,
        args.harnesses,
        args.limit,
    )

    rows: list[dict[str, Any]] = []
    for condition in conditions:
        provider = _provider_for_condition(condition, registry_path, aliases)
        command = _condition_command(condition, provider, output_dir, docs_per_condition, config_path, args.stub_calls)
        rows.append(
            {
                "id": condition["id"],
                "tier": condition.get("tier"),
                "model": condition.get("model"),
                "provider": provider,
                "harness": condition.get("harness"),
                "prompt_style": condition.get("prompt_style"),
                "projection_policy": condition.get("projection_policy"),
                "output_dir": str(output_dir / str(condition["id"])),
                "command": _command_to_text(command),
            }
        )

    _write_manifest(output_dir, rows, [str(condition["id"]) for condition in conditions])
    print(f"wrote {len(rows)} launch command(s) to {output_dir}")
    if not args.execute:
        return 0

    for row, condition in zip(rows, conditions, strict=False):
        provider = row["provider"]
        if not args.stub_calls and not _has_provider_credentials(provider):
            message = f"missing credentials for provider {provider}; skipping {row['id']}"
            if args.continue_on_error:
                print(message)
                continue
            raise RuntimeError(message)
        command = _condition_command(condition, provider, output_dir, docs_per_condition, config_path, args.stub_calls)
        print(f"running {row['id']}: {_command_to_text(command)}", flush=True)
        completed = subprocess.run(command, cwd=Path.cwd())
        if completed.returncode != 0:
            if args.continue_on_error:
                print(f"{row['id']} failed with exit code {completed.returncode}")
                continue
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
