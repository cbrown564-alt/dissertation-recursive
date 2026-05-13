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
