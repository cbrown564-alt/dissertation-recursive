from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class VersionedTextAsset:
    asset_id: str
    version: str
    path: str
    content: str


@dataclass(frozen=True)
class VersionedJsonAsset:
    asset_id: str
    version: str
    path: str
    content: dict[str, Any]


PROMPT_REGISTRY = {
    "retrieval_field_extractor": ("retrieval/field_extractor_v1.md", "retrieval_field_extractor_v1"),
    "clines_field_extractor": ("clines_inspired/field_extractor_v1.md", "clines_inspired_field_extractor_v1"),
    "clines_verifier": ("clines_inspired/verification_v1.md", "clines_inspired_verification_v1"),
}

SCHEMA_REGISTRY = {
    "final_extraction": ("final_extraction_v1.json", "final_extraction_v1"),
}

def load_prompt(prompt_id: str) -> VersionedTextAsset:
    relative_path, version = PROMPT_REGISTRY[prompt_id]
    path = REPO_ROOT / "prompts" / relative_path
    return VersionedTextAsset(
        asset_id=prompt_id,
        version=version,
        path=path.relative_to(REPO_ROOT).as_posix(),
        content=path.read_text(encoding="utf-8"),
    )

def load_schema(schema_id: str) -> VersionedJsonAsset:
    relative_path, version = SCHEMA_REGISTRY[schema_id]
    path = REPO_ROOT / "schemas" / relative_path
    return VersionedJsonAsset(
        asset_id=schema_id,
        version=version,
        path=path.relative_to(REPO_ROOT).as_posix(),
        content=json.loads(path.read_text(encoding="utf-8")),
    )
