from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelRegistryEntry:
    model_id: str
    display_name: str
    provider: str
    family: str
    tier: str
    context_window: int
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    frozen_at: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "provider": self.provider,
            "family": self.family,
            "tier": self.tier,
            "context_window": self.context_window,
            "cost_per_1k_input": self.cost_per_1k_input,
            "cost_per_1k_output": self.cost_per_1k_output,
            "frozen_at": self.frozen_at,
            "notes": self.notes,
        }


REQUIRED_ENTRY_KEYS = frozenset(
    {"model_id", "display_name", "provider", "family", "tier", "context_window"}
)

VALID_TIERS = frozenset({"frontier", "medium", "small", "open_frontier", "open_medium", "open_small"})


def load_registry(path: str | Path) -> list[ModelRegistryEntry]:
    path = Path(path)
    raw = _parse_yaml_simple(path.read_text(encoding="utf-8"))
    entries = raw.get("models", [])
    if not isinstance(entries, list):
        raise ValueError(f"Registry at {path} must have a top-level 'models' list")
    return [_entry_from_dict(entry, path) for entry in entries]


def get_registry_entry(model_id: str, path: str | Path) -> ModelRegistryEntry | None:
    for entry in load_registry(path):
        if entry.model_id == model_id:
            return entry
    return None


def validate_registry(entries: list[ModelRegistryEntry]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.model_id in seen:
            errors.append(f"Duplicate model_id: {entry.model_id!r}")
        seen.add(entry.model_id)
        if entry.tier not in VALID_TIERS:
            errors.append(
                f"model_id={entry.model_id!r}: unknown tier {entry.tier!r}; expected one of {sorted(VALID_TIERS)}"
            )
        if entry.context_window <= 0:
            errors.append(f"model_id={entry.model_id!r}: context_window must be positive")
    return errors


def _entry_from_dict(raw: dict[str, Any], source: Path) -> ModelRegistryEntry:
    missing = REQUIRED_ENTRY_KEYS - raw.keys()
    if missing:
        raise ValueError(
            f"Registry entry in {source} missing required keys: {sorted(missing)} — entry: {json.dumps(raw)}"
        )
    return ModelRegistryEntry(
        model_id=str(raw["model_id"]),
        display_name=str(raw["display_name"]),
        provider=str(raw["provider"]),
        family=str(raw["family"]),
        tier=str(raw["tier"]),
        context_window=int(raw["context_window"]),
        cost_per_1k_input=float(raw.get("cost_per_1k_input", 0.0)),
        cost_per_1k_output=float(raw.get("cost_per_1k_output", 0.0)),
        frozen_at=str(raw.get("frozen_at", "")),
        notes=str(raw.get("notes", "")),
    )


def _parse_yaml_simple(text: str) -> dict[str, Any]:
    """Minimal YAML parser for flat and list-of-dict structures.

    Avoids adding PyYAML as a runtime dependency. Handles the exact structure of
    model_registry.candidate.yaml: top-level 'models:' key followed by a list of
    indented dash-separated mappings.
    """
    try:
        import yaml  # type: ignore[import]
        return yaml.safe_load(text) or {}
    except ImportError:
        pass
    return _fallback_yaml_parse(text)


def _fallback_yaml_parse(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    result: dict[str, Any] = {}
    models: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_models = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "models:":
            in_models = True
            continue
        if in_models:
            if stripped.startswith("- "):
                if current is not None:
                    models.append(current)
                current = {}
                rest = stripped[2:].strip()
                if rest and ":" in rest:
                    k, _, v = rest.partition(":")
                    current[k.strip()] = _coerce(v.strip())
            elif stripped.startswith("-"):
                if current is not None:
                    models.append(current)
                current = {}
            elif ":" in stripped and current is not None:
                k, _, v = stripped.partition(":")
                current[k.strip()] = _coerce(v.strip())
        elif ":" in stripped:
            k, _, v = stripped.partition(":")
            result[k.strip()] = _coerce(v.strip())

    if current is not None:
        models.append(current)
    if models:
        result["models"] = models
    return result


def _coerce(value: str) -> Any:
    if not value:
        return ""
    if value.lower() == "null":
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value.strip("'\"")
