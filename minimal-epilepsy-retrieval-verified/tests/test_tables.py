import csv
import json
import subprocess
import sys
from pathlib import Path

from epilepsy_extraction.evaluation.tables import TABLE_ORDER, build_result_tables


ROOT = Path(__file__).resolve().parents[1]
RUN_PATH = ROOT / "results" / "runs" / "exect_lite_smoke.json"
REGISTRY_PATH = ROOT / "config" / "model_registry.candidate.yaml"


def _run_record() -> dict:
    return json.loads(RUN_PATH.read_text(encoding="utf-8"))


def test_build_result_tables_in_evaluation_contract_order() -> None:
    tables = build_result_tables([_run_record()], model_registry_path=REGISTRY_PATH)

    assert tuple(tables) == TABLE_ORDER
    coverage = tables["architecture_harness_coverage"]
    assert coverage[0]["run_id"] == "exect_lite_smoke"
    assert coverage[0]["field_family"] == "seizure_frequency"
    assert any(row["coverage_status"] == "not_attempted" for row in coverage)


def test_baseline_comparability_preserves_not_attempted_fields() -> None:
    tables = build_result_tables([_run_record()])
    baseline_rows = tables["baseline_comparability"]

    not_attempted = [
        row for row in baseline_rows if row["field_family"] == "rescue_medication"
    ][0]
    assert not_attempted["coverage_status"] == "not_attempted"
    assert not_attempted["comparability_notes"] == "field_not_attempted"


def test_budget_and_parse_tables_surface_run_metadata() -> None:
    tables = build_result_tables([_run_record()])

    budget = tables["budget_complexity"][0]
    assert budget["harness"] == "exect_lite_cleanroom_baseline"
    assert budget["dataset_n"] == 2

    parse = tables["parse_validity"][0]
    assert parse["component"] == "seizure_frequency"
    assert parse["valid_rate"] == 1.0


def test_harness_complexity_table_handles_future_harness_native_metadata() -> None:
    record = _run_record()
    record["harness_manifest"] = {"id": "exect_lite.v1", "hash": "abc123"}
    record["complexity"] = {
        "modules": ["rules", "mapper"],
        "workflow_units": ["seizure_frequency", "investigations"],
    }
    record["harness_events"] = [
        {"event_type": "context_built"},
        {"event_type": "provider_call_started"},
        {"event_type": "parse_repaired"},
        {"event_type": "verification_completed"},
        {"event_type": "escalation_decision"},
    ]

    tables = build_result_tables([record])
    complexity = tables["harness_complexity"][0]

    assert complexity["manifest_id"] == "exect_lite.v1"
    assert complexity["manifest_hash"] == "abc123"
    assert complexity["modules_invoked"] == 2
    assert complexity["workflow_units"] == 2
    assert complexity["provider_calls"] == 1
    assert complexity["event_count"] == 5
    assert complexity["parse_repair_attempts"] == 1
    assert complexity["verifier_passes"] == 1
    assert complexity["escalation_decisions"] == 1
    assert complexity["complexity_status"] == "harness_native"


def test_summarize_results_writes_json_and_csv_tables(tmp_path) -> None:
    output_dir = tmp_path / "tables"

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "summarize_results.py"),
            str(RUN_PATH),
            "--tables-dir",
            str(output_dir),
            "--model-registry",
            str(REGISTRY_PATH),
        ],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    summary = json.loads(completed.stdout)
    assert summary["run_records"] == 1

    coverage_json = output_dir / "architecture_harness_coverage.json"
    coverage_csv = output_dir / "architecture_harness_coverage.csv"
    harness_complexity_json = output_dir / "harness_complexity.json"
    assert coverage_json.exists()
    assert coverage_csv.exists()
    assert harness_complexity_json.exists()

    rows = json.loads(coverage_json.read_text(encoding="utf-8"))
    assert rows[0]["run_id"] == "exect_lite_smoke"

    with coverage_csv.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows[0]["run_id"] == "exect_lite_smoke"
