#!/usr/bin/env python3
"""Tests for the shared core helper layer."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.datasets import load_split_ids
from core.io import read_csv_dicts, read_csv_rows, read_json, read_text, write_csv, write_json, write_text
from core.labels import BENCHMARK_EPILEPSY_LABELS, BENCHMARK_SEIZURE_LABELS, benchmark_label_block


def test_text_json_and_csv_helpers_round_trip(tmp_path: Path) -> None:
    text_path = tmp_path / "nested" / "note.txt"
    write_text(text_path, "hello\n")
    assert read_text(text_path) == "hello\n"

    json_path = tmp_path / "nested" / "payload.json"
    write_json(json_path, {"name": "levetiracetam", "dose": 500})
    assert read_json(json_path) == {"name": "levetiracetam", "dose": 500}

    csv_path = tmp_path / "nested" / "rows.csv"
    write_csv(csv_path, [{"id": "EA0001", "score": 1}, {"id": "EA0002", "score": 0}])
    assert read_csv_rows(csv_path) == [["id", "score"], ["EA0001", "1"], ["EA0002", "0"]]
    assert read_csv_dicts(csv_path) == [{"id": "EA0001", "score": "1"}, {"id": "EA0002", "score": "0"}]


def test_load_split_ids_with_limit(tmp_path: Path) -> None:
    split_path = tmp_path / "splits.json"
    write_json(split_path, {"development": ["EA0001", "EA0002", "EA0003"]})
    assert load_split_ids(split_path, "development", None) == ["EA0001", "EA0002", "EA0003"]
    assert load_split_ids(split_path, "development", 2) == ["EA0001", "EA0002"]


def test_benchmark_label_block_contains_shared_contract() -> None:
    block = benchmark_label_block()
    assert "Allowed seizure_type labels:" in block
    assert "Allowed epilepsy_diagnosis_type labels:" in block
    assert "- unknown seizure type" in block
    assert "- focal epilepsy" in block
    assert len(BENCHMARK_SEIZURE_LABELS) == 10
    assert len(BENCHMARK_EPILEPSY_LABELS) == 5
