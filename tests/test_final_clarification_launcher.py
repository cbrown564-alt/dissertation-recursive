#!/usr/bin/env python3
"""Tests for selected final-clarification launch command materialization."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from run_final_clarification_conditions import _condition_command, _provider_for_condition


def test_launcher_materializes_api_h6fs_condition() -> None:
    config = yaml.safe_load(Path("configs/final_clarification_matrix.yaml").read_text(encoding="utf-8"))
    aliases = config.get("model_registry_aliases") or {}
    condition = next(item for item in config["selected_run_plan"]["conditions"] if item["id"] == "FC19")
    provider = _provider_for_condition(condition, Path("configs/model_registry.yaml"), aliases)

    command = _condition_command(
        condition,
        provider,
        Path("runs/final_clarification"),
        40,
        Path("configs/final_clarification_matrix.yaml"),
        stub_calls=False,
    )

    assert provider == "openai"
    assert "src/model_expansion.py" in command
    assert "h6-h7-clean-diagnostic" in command
    assert "H6fs_benchmark_only_coarse_json" in command
    assert "--prompt-style" in command
    assert "clinician" in command


def test_launcher_materializes_local_h6fs_condition() -> None:
    config = yaml.safe_load(Path("configs/final_clarification_matrix.yaml").read_text(encoding="utf-8"))
    aliases = config.get("model_registry_aliases") or {}
    condition = next(item for item in config["selected_run_plan"]["conditions"] if item["id"] == "FC04")
    provider = _provider_for_condition(condition, Path("configs/model_registry.yaml"), aliases)

    command = _condition_command(
        condition,
        provider,
        Path("runs/final_clarification"),
        40,
        Path("configs/final_clarification_matrix.yaml"),
        stub_calls=False,
    )

    assert provider == "ollama"
    assert "src/local_models.py" in command
    assert "stage-l5" in command
    assert "qwen_35b_local" in command
