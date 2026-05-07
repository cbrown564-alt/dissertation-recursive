#!/usr/bin/env python3
"""Versioned model registry for the powerful-model expansion study."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import date, timezone, datetime
from pathlib import Path
from typing import Any

import yaml


DEFAULT_REGISTRY = Path("configs/model_registry.yaml")


@dataclass(frozen=True)
class ModelSpec:
    label: str
    provider: str
    provider_model_id: str
    api_surface: str
    sdk_package: str | None
    sdk_version: str | None
    context_window_tokens: int | None
    max_output_tokens: int | None
    structured_output: str | None
    temperature: float
    seed_supported: bool
    pricing: dict[str, float | None]
    pricing_snapshot_date: str | None
    region: str | None
    billing_currency: str | None
    deprecation_or_alias_behavior: str | None
    raw: dict[str, Any]


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"registry must be a YAML object: {path}")
    return data


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    """Load the registry as plain data for snapshots and manifest embedding."""

    data = _read_yaml(path)
    if not isinstance(data.get("models"), dict):
        raise ValueError(f"registry must contain a models object: {path}")
    return data


def load_model_specs(path: Path = DEFAULT_REGISTRY) -> dict[str, ModelSpec]:
    registry = load_registry(path)
    snapshot_date = registry.get("pricing_snapshot_date")
    specs: dict[str, ModelSpec] = {}
    for label, raw_model in registry["models"].items():
        if not isinstance(raw_model, dict):
            raise ValueError(f"model entry must be an object: {label}")
        for required in ["provider", "provider_model_id", "api_surface"]:
            if not raw_model.get(required):
                raise ValueError(f"model {label} missing required field: {required}")
        specs[label] = ModelSpec(
            label=label,
            provider=str(raw_model["provider"]),
            provider_model_id=str(raw_model["provider_model_id"]),
            api_surface=str(raw_model["api_surface"]),
            sdk_package=raw_model.get("sdk_package"),
            sdk_version=raw_model.get("sdk_version"),
            context_window_tokens=raw_model.get("context_window_tokens"),
            max_output_tokens=raw_model.get("max_output_tokens"),
            structured_output=raw_model.get("structured_output"),
            temperature=float(raw_model.get("temperature", 0.0)),
            seed_supported=bool(raw_model.get("seed_supported", False)),
            pricing={
                "input_per_million": raw_model.get("input_price_per_million"),
                "output_per_million": raw_model.get("output_price_per_million"),
                "cache_read_per_million": raw_model.get("cache_read_price_per_million"),
                "cache_write_per_million": raw_model.get("cache_write_price_per_million"),
            },
            pricing_snapshot_date=str(snapshot_date) if snapshot_date else None,
            region=raw_model.get("region"),
            billing_currency=raw_model.get("billing_currency", registry.get("currency")),
            deprecation_or_alias_behavior=raw_model.get("deprecation_or_alias_behavior"),
            raw=copy.deepcopy(raw_model),
        )
    return specs


def registry_snapshot(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    snapshot = load_registry(path)
    snapshot["snapshot_created_at"] = datetime.now(timezone.utc).isoformat()
    snapshot["snapshot_created_date"] = date.today().isoformat()
    return snapshot


def write_registry_snapshot(path: Path, registry_path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    snapshot = registry_snapshot(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return snapshot
