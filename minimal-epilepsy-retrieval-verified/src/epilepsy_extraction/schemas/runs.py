from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class RunStatus(str, Enum):
    CANONICAL = "canonical"
    SUPPORTING = "supporting"
    ARCHIVE = "archive"
    SMOKE = "smoke"


@dataclass(frozen=True)
class DatasetSlice:
    dataset_id: str
    dataset_path: str
    data_hash: str
    row_ids: list[str]
    inclusion_criteria: str
    row_order: str = "source"
    random_seed: int | None = None

    @property
    def n(self) -> int:
        return len(self.row_ids)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["n"] = self.n
        return data


@dataclass(frozen=True)
class BudgetMetadata:
    llm_calls_per_row: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    estimated_cost_usd: float = 0.0


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    harness: str
    schema_version: str
    dataset: DatasetSlice
    model: str
    provider: str
    temperature: float
    prompt_version: str
    code_version: str
    budget: BudgetMetadata
    status: RunStatus = RunStatus.SMOKE
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    field_coverage: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    rows: list[dict[str, Any]] = field(default_factory=list)
    parse_validity: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    artifact_paths: dict[str, str] = field(default_factory=dict)
    architecture_family: str = ""
    model_registry_entry: str | None = None
    complexity: dict[str, Any] = field(default_factory=dict)
    external_baseline: bool = False
    mapping_version: str = ""
    manifest_id: str = ""
    manifest_hash: str = ""
    harness_events: list[dict[str, Any]] = field(default_factory=list)
    event_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["dataset"] = self.dataset.to_dict()
        return data


def write_run_record(record: RunRecord, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def git_code_version(cwd: str | Path = ".") -> str | None:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(cwd),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        dirty = subprocess.call(
            ["git", "diff", "--quiet"],
            cwd=Path(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return f"{commit}-dirty" if dirty else commit


def resolve_code_version(
    explicit: str | None = None,
    cwd: str | Path = ".",
    fallback: str = "unknown",
) -> str:
    if explicit:
        return explicit
    return git_code_version(cwd) or fallback
