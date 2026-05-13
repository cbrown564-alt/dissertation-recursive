#!/usr/bin/env python3
"""Tests for final clarification matrix helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from describe_final_clarification_matrix import summarize_matrix


def test_final_clarification_matrix_names_required_axes() -> None:
    config = yaml.safe_load(Path("configs/final_clarification_matrix.yaml").read_text(encoding="utf-8"))
    summary = summarize_matrix(config)

    assert "internal" in summary["prompt_styles"]
    assert "clinician" in summary["prompt_styles"]
    assert "relaxed_projection" in summary["projection_policies"]
    assert "temporality_challenge" in summary["evaluation_slices"]
    assert "projection_delta_rows" in summary["required_outputs"]
    assert summary["full_factorial_conditions"] > 0


def test_selected_run_plan_is_downselected_and_costed() -> None:
    config = yaml.safe_load(Path("configs/final_clarification_matrix.yaml").read_text(encoding="utf-8"))
    summary = summarize_matrix(config)
    selected = summary["selected_run_plan"]

    assert selected["condition_count"] < summary["full_factorial_conditions"]
    assert selected["documents_per_condition"] == 40
    assert selected["total_document_runs"] == 40 * selected["condition_count"]
    assert selected["estimated_api_cost_usd"] > 0
    assert selected["unpriced_condition_count"] > 0
    assert any(row["model"] == "gemini_3_flash" and row["registry_model"] == "gemini_3_1_flash" for row in selected["conditions"])
