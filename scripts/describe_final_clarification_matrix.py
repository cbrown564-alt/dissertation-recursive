#!/usr/bin/env python3
"""Summarize the final clarification matrix config."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.io import write_json, write_text


def _flatten_model_groups(models: dict[str, list[str]]) -> list[str]:
    result: list[str] = []
    for group in models.values():
        result.extend(group or [])
    return result


def _flatten_harness_groups(harnesses: dict[str, list[str]]) -> list[str]:
    result: list[str] = []
    for group in harnesses.values():
        result.extend(group or [])
    return result


def summarize_matrix(config: dict[str, Any]) -> dict[str, Any]:
    models = _flatten_model_groups(config.get("models") or {})
    harnesses = _flatten_harness_groups(config.get("harnesses") or {})
    prompt_styles = config.get("prompt_styles") or []
    projection_policies = list((config.get("projection_policies") or {}).keys())
    full_factorial_conditions = len(models) * len(harnesses) * len(prompt_styles) * len(projection_policies)
    return {
        "version": config.get("version"),
        "model_count": len(models),
        "harness_count": len(harnesses),
        "prompt_style_count": len(prompt_styles),
        "projection_policy_count": len(projection_policies),
        "full_factorial_conditions": full_factorial_conditions,
        "models": models,
        "harnesses": harnesses,
        "prompt_styles": prompt_styles,
        "projection_policies": projection_policies,
        "evaluation_slices": sorted((config.get("evaluation_slices") or {}).keys()),
        "required_outputs": config.get("required_outputs") or [],
    }


def markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Final Clarification Matrix",
            "",
            f"Version: {summary.get('version')}",
            f"Models: {summary.get('model_count')}",
            f"Harnesses: {summary.get('harness_count')}",
            f"Prompt styles: {summary.get('prompt_style_count')}",
            f"Projection policies: {summary.get('projection_policy_count')}",
            f"Full factorial conditions: {summary.get('full_factorial_conditions')}",
            "",
            "## Evaluation Slices",
            *[f"- {name}" for name in summary.get("evaluation_slices", [])],
            "",
            "## Required Outputs",
            *[f"- {name}" for name in summary.get("required_outputs", [])],
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/final_clarification_matrix.yaml")
    parser.add_argument("--output-dir", default="runs/final_clarification_matrix")
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    summary = summarize_matrix(config)
    output_dir = Path(args.output_dir)
    write_json(output_dir / "matrix_summary.json", summary)
    write_text(output_dir / "matrix_summary.md", markdown_summary(summary))
    print(f"wrote matrix summary with {summary['full_factorial_conditions']} full-factorial conditions to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
