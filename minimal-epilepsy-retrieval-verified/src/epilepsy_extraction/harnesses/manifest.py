from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from epilepsy_extraction.schemas import RunRecord
from epilepsy_extraction.schemas.contracts import ArchitectureFamily


REQUIRED_MANIFEST_KEYS = frozenset(
    {
        "manifest_id",
        "harness_id",
        "version",
        "architecture_family",
        "allowed_modules",
        "prompt_versions",
        "schema_version",
        "context_policy",
        "output_contract",
        "repair_policy",
        "verifier_policy",
        "aggregation_policy",
        "budget_limits",
        "gold_label_isolation",
        "artifact_retention",
    }
)


@dataclass(frozen=True)
class HarnessManifest:
    manifest_id: str
    harness_id: str
    version: str
    architecture_family: str
    allowed_modules: list[str] = field(default_factory=list)
    prompt_versions: dict[str, str] = field(default_factory=dict)
    schema_version: str = ""
    provider: str = ""
    model_registry_entry: str = ""
    context_policy: dict[str, Any] = field(default_factory=dict)
    output_contract: dict[str, Any] = field(default_factory=dict)
    repair_policy: dict[str, Any] = field(default_factory=dict)
    verifier_policy: dict[str, Any] = field(default_factory=dict)
    aggregation_policy: dict[str, Any] = field(default_factory=dict)
    budget_limits: dict[str, Any] = field(default_factory=dict)
    gold_label_isolation: dict[str, Any] = field(default_factory=dict)
    artifact_retention: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""
    manifest_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "harness_id": self.harness_id,
            "version": self.version,
            "architecture_family": self.architecture_family,
            "allowed_modules": list(self.allowed_modules),
            "prompt_versions": dict(self.prompt_versions),
            "schema_version": self.schema_version,
            "provider": self.provider,
            "model_registry_entry": self.model_registry_entry,
            "context_policy": dict(self.context_policy),
            "output_contract": dict(self.output_contract),
            "repair_policy": dict(self.repair_policy),
            "verifier_policy": dict(self.verifier_policy),
            "aggregation_policy": dict(self.aggregation_policy),
            "budget_limits": dict(self.budget_limits),
            "gold_label_isolation": dict(self.gold_label_isolation),
            "artifact_retention": dict(self.artifact_retention),
            "source_path": self.source_path,
            "manifest_hash": self.manifest_hash,
        }


def default_manifest_path(harness_id: str, root: str | Path = ".") -> Path:
    return Path(root) / "config" / "harnesses" / f"{harness_id}.yaml"


def load_harness_manifest(path: str | Path) -> HarnessManifest:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    raw = _parse_manifest_text(text)
    if not isinstance(raw, dict):
        raise ValueError(f"Harness manifest at {path} must be a mapping")
    manifest_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    manifest = _manifest_from_dict(raw, path, manifest_hash)
    errors = validate_harness_manifest(manifest)
    if errors:
        raise ValueError("Harness manifest validation errors:\n" + "\n".join(f"  {e}" for e in errors))
    return manifest


def validate_harness_manifest(manifest: HarnessManifest) -> list[str]:
    errors: list[str] = []
    if not manifest.manifest_id.strip():
        errors.append("manifest_id is required")
    if not manifest.harness_id.strip():
        errors.append("harness_id is required")
    if not manifest.version.strip():
        errors.append("version is required")
    try:
        ArchitectureFamily(manifest.architecture_family)
    except ValueError:
        errors.append(
            f"architecture_family={manifest.architecture_family!r} is not one of "
            f"{[item.value for item in ArchitectureFamily]}"
        )
    if not manifest.schema_version.strip():
        errors.append("schema_version is required")
    if not isinstance(manifest.allowed_modules, list):
        errors.append("allowed_modules must be a list")
    for field_name in (
        "context_policy",
        "output_contract",
        "repair_policy",
        "verifier_policy",
        "aggregation_policy",
        "budget_limits",
        "gold_label_isolation",
        "artifact_retention",
    ):
        if not isinstance(getattr(manifest, field_name), dict):
            errors.append(f"{field_name} must be a mapping")
    if manifest.gold_label_isolation.get("model_visible") is not False:
        errors.append("gold_label_isolation.model_visible must be false")
    return errors


def attach_manifest_to_run(record: RunRecord, manifest: HarnessManifest | None) -> RunRecord:
    if manifest is None:
        return record
    complexity = dict(record.complexity)
    complexity.setdefault("manifest", manifest.to_dict())
    artifact_paths = dict(record.artifact_paths)
    if manifest.source_path:
        artifact_paths.setdefault("manifest", manifest.source_path)
    return replace(
        record,
        manifest_id=manifest.manifest_id,
        manifest_hash=manifest.manifest_hash,
        architecture_family=record.architecture_family or manifest.architecture_family,
        model_registry_entry=record.model_registry_entry or manifest.model_registry_entry or None,
        complexity=complexity,
        artifact_paths=artifact_paths,
    )


def _manifest_from_dict(raw: dict[str, Any], source: Path, manifest_hash: str) -> HarnessManifest:
    missing = REQUIRED_MANIFEST_KEYS - raw.keys()
    if missing:
        raise ValueError(f"Harness manifest {source} missing required keys: {sorted(missing)}")
    return HarnessManifest(
        manifest_id=str(raw["manifest_id"]),
        harness_id=str(raw["harness_id"]),
        version=str(raw["version"]),
        architecture_family=str(raw["architecture_family"]),
        allowed_modules=[str(item) for item in raw.get("allowed_modules", [])],
        prompt_versions={str(k): str(v) for k, v in dict(raw.get("prompt_versions", {})).items()},
        schema_version=str(raw["schema_version"]),
        provider=str(raw.get("provider", "")),
        model_registry_entry=str(raw.get("model_registry_entry", "")),
        context_policy=dict(raw.get("context_policy", {})),
        output_contract=dict(raw.get("output_contract", {})),
        repair_policy=dict(raw.get("repair_policy", {})),
        verifier_policy=dict(raw.get("verifier_policy", {})),
        aggregation_policy=dict(raw.get("aggregation_policy", {})),
        budget_limits=dict(raw.get("budget_limits", {})),
        gold_label_isolation=dict(raw.get("gold_label_isolation", {})),
        artifact_retention=dict(raw.get("artifact_retention", {})),
        source_path=str(source),
        manifest_hash=manifest_hash,
    )


def _parse_manifest_text(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        import yaml  # type: ignore[import]

        return yaml.safe_load(text) or {}
    except ImportError:
        raise ValueError(
            "Harness manifests must be JSON-compatible when PyYAML is unavailable"
        ) from None
