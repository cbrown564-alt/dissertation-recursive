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
from core.io import write_csv
from model_registry import load_model_specs


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
        "selected_run_plan": summarize_selected_run_plan(config),
    }


def _resolve_model_label(model: str, aliases: dict[str, str]) -> str:
    return aliases.get(model, model)


def _estimate_condition_cost_usd(
    *,
    model: str,
    harness: str,
    documents: int,
    token_estimates: dict[str, Any],
    registry_path: Path,
    aliases: dict[str, str],
) -> dict[str, Any]:
    estimates = token_estimates.get(harness) or {}
    input_tokens_per_doc = int(estimates.get("input_tokens") or 0)
    output_tokens_per_doc = int(estimates.get("output_tokens") or 0)
    calls_per_doc = int(estimates.get("calls_per_document") or 1)
    registry_model = _resolve_model_label(model, aliases)
    specs = load_model_specs(registry_path)
    spec = specs.get(registry_model)
    input_price = spec.pricing.get("input_per_million") if spec else None
    output_price = spec.pricing.get("output_per_million") if spec else None
    input_tokens = documents * input_tokens_per_doc
    output_tokens = documents * output_tokens_per_doc
    if input_price is None or output_price is None:
        estimated_cost_usd = None
        cost_status = "local_or_unpriced"
    else:
        estimated_cost_usd = round(
            (input_tokens / 1_000_000) * float(input_price)
            + (output_tokens / 1_000_000) * float(output_price),
            4,
        )
        cost_status = "estimated"
    return {
        "registry_model": registry_model,
        "provider": spec.provider if spec else "unknown",
        "calls": documents * calls_per_doc,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "cost_status": cost_status,
    }


def summarize_selected_run_plan(
    config: dict[str, Any],
    registry_path: Path = Path("configs/model_registry.yaml"),
) -> dict[str, Any]:
    plan = config.get("selected_run_plan") or {}
    conditions = plan.get("conditions") or []
    documents = int(plan.get("documents_per_condition") or 0)
    token_estimates = plan.get("token_estimates_per_document") or {}
    aliases = config.get("model_registry_aliases") or {}
    rows: list[dict[str, Any]] = []
    total_calls = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_estimated_cost = 0.0
    unpriced_conditions = 0
    for condition in conditions:
        estimate = _estimate_condition_cost_usd(
            model=str(condition.get("model")),
            harness=str(condition.get("harness")),
            documents=documents,
            token_estimates=token_estimates,
            registry_path=registry_path,
            aliases=aliases,
        )
        row = {
            "id": condition.get("id"),
            "tier": condition.get("tier"),
            "model": condition.get("model"),
            "registry_model": estimate["registry_model"],
            "provider": estimate["provider"],
            "harness": condition.get("harness"),
            "prompt_style": condition.get("prompt_style"),
            "projection_policy": condition.get("projection_policy"),
            "documents": documents,
            "calls": estimate["calls"],
            "input_tokens": estimate["input_tokens"],
            "output_tokens": estimate["output_tokens"],
            "estimated_cost_usd": estimate["estimated_cost_usd"],
            "cost_status": estimate["cost_status"],
            "rationale": condition.get("rationale"),
        }
        rows.append(row)
        total_calls += int(estimate["calls"])
        total_input_tokens += int(estimate["input_tokens"])
        total_output_tokens += int(estimate["output_tokens"])
        if estimate["estimated_cost_usd"] is None:
            unpriced_conditions += 1
        else:
            total_estimated_cost += float(estimate["estimated_cost_usd"])
    tiers = sorted({str(row["tier"]) for row in rows if row.get("tier")})
    return {
        "version": plan.get("version"),
        "documents_per_condition": documents,
        "condition_count": len(rows),
        "total_document_runs": documents * len(rows),
        "total_calls": total_calls,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "estimated_api_cost_usd": round(total_estimated_cost, 4),
        "unpriced_condition_count": unpriced_conditions,
        "tiers": tiers,
        "conditions": rows,
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
            "## Selected Run Plan",
            f"Conditions: {summary.get('selected_run_plan', {}).get('condition_count', 0)}",
            f"Documents per condition: {summary.get('selected_run_plan', {}).get('documents_per_condition', 0)}",
            f"Total document-runs: {summary.get('selected_run_plan', {}).get('total_document_runs', 0)}",
            f"Total model calls: {summary.get('selected_run_plan', {}).get('total_calls', 0)}",
            f"Estimated API cost: ${summary.get('selected_run_plan', {}).get('estimated_api_cost_usd', 0)}",
            f"Unpriced/local conditions: {summary.get('selected_run_plan', {}).get('unpriced_condition_count', 0)}",
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
    selected = summary.get("selected_run_plan") or {}
    write_json(output_dir / "selected_run_plan.json", selected)
    write_csv(output_dir / "selected_run_plan.csv", selected.get("conditions") or [])
    write_text(output_dir / "matrix_summary.md", markdown_summary(summary))
    print(
        "wrote matrix summary with "
        f"{summary['full_factorial_conditions']} full-factorial conditions "
        f"and {selected.get('condition_count', 0)} selected conditions to {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
