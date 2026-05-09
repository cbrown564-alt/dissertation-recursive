import json
import subprocess
import sys
from pathlib import Path

from epilepsy_extraction.data import compute_file_sha256, load_synthetic_subset, select_fixed_slice
from epilepsy_extraction.harnesses import run_retrieval_field_extractors
from epilepsy_extraction.providers import MockProvider
from epilepsy_extraction.schemas import DatasetSlice
from epilepsy_extraction.schemas.contracts import CORE_FIELD_FAMILIES, ArchitectureFamily


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "synthetic_subset_fixture.json"

_FULL_RESPONSE = json.dumps(
    {
        "seizure_frequency": {"value": "2 per month"},
        "current_medications": [{"name": "lamotrigine", "dose": "100 mg bd"}],
        "investigations": [],
        "seizure_types": [],
        "seizure_features": [],
        "seizure_pattern_modifiers": [],
        "epilepsy_type": None,
        "epilepsy_syndrome": None,
        "citations": [{"quote": "two seizures per month"}],
        "confidence": {"seizure_frequency": 0.9},
        "warnings": ["field_warning"],
    }
)


def _records(limit: int = 1):
    return select_fixed_slice(load_synthetic_subset(FIXTURE_PATH), limit=limit)


def _dataset(records):
    return DatasetSlice(
        dataset_id="fixture",
        dataset_path=str(FIXTURE_PATH),
        data_hash=compute_file_sha256(FIXTURE_PATH),
        row_ids=[r.row_id for r in records],
        inclusion_criteria="fixture",
    )


def test_retrieval_field_extractors_makes_one_call_per_field_family() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run = run_retrieval_field_extractors(records, _dataset(records), "rfe", "test", provider)

    assert len(provider.requests) == len(CORE_FIELD_FAMILIES)
    assert run.harness == "retrieval_field_extractors"


def test_retrieval_field_extractors_budget_reflects_calls_per_row() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run = run_retrieval_field_extractors(records, _dataset(records), "rfe", "test", provider)

    assert run.budget.llm_calls_per_row == len(CORE_FIELD_FAMILIES)


def test_retrieval_field_extractors_records_retrieval_artifacts() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run = run_retrieval_field_extractors(records, _dataset(records), "rfe", "test", provider)

    artifacts = run.rows[0]["retrieval_artifacts"]
    assert isinstance(artifacts, dict)
    for family in CORE_FIELD_FAMILIES:
        assert family.value in artifacts


def test_retrieval_field_extractors_preserves_evidence_confidence_and_warnings() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run = run_retrieval_field_extractors(records, _dataset(records), "rfe", "test", provider)

    final = run.rows[0]["payload"]["final"]
    assert final["citations"]
    assert final["confidence"]["seizure_frequency"] == 0.9
    assert "field_warning" in final["warnings"]


def test_retrieval_field_extractors_architecture_family() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run = run_retrieval_field_extractors(records, _dataset(records), "rfe", "test", provider)

    assert run.architecture_family == ArchitectureFamily.RETRIEVAL_FIELD_PIPELINE.value


def test_retrieval_field_extractors_handles_invalid_json() -> None:
    records = _records()
    provider = MockProvider(["not json"] * len(CORE_FIELD_FAMILIES))

    run = run_retrieval_field_extractors(records, _dataset(records), "rfe", "test", provider)

    assert run.rows[0]["payload"]["invalid_output"] is True


def test_retrieval_field_extractors_requests_include_field_family_metadata() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run_retrieval_field_extractors(records, _dataset(records), "rfe", "test", provider)

    families_seen = {req.metadata.get("field_family") for req in provider.requests}
    assert families_seen == {f.value for f in CORE_FIELD_FAMILIES}


def test_retrieval_field_extractors_cli_from_replay_file(tmp_path) -> None:
    replay_responses = [
        {
            "content": _FULL_RESPONSE,
            "usage": {"input_tokens": 30, "output_tokens": 10},
        }
    ] * len(CORE_FIELD_FAMILIES)
    replay = tmp_path / "replay.json"
    replay.write_text(json.dumps(replay_responses), encoding="utf-8")
    output = tmp_path / "rfe.json"

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_experiment.py"),
            str(FIXTURE_PATH),
            "--harness",
            "retrieval_field_extractors",
            "--limit",
            "1",
            "--run-id",
            "rfe_test",
            "--output",
            str(output),
            "--replay",
            str(replay),
            "--code-version",
            "test",
        ],
        check=True,
        cwd=ROOT,
    )

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["harness"] == "retrieval_field_extractors"
    assert data["budget"]["llm_calls_per_row"] == len(CORE_FIELD_FAMILIES)
