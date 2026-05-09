import json
import subprocess
import sys
from pathlib import Path

from epilepsy_extraction.data import compute_file_sha256, load_synthetic_subset, select_fixed_slice
from epilepsy_extraction.harnesses import run_clines_epilepsy_modular, run_clines_epilepsy_verified
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
        "warnings": [],
    }
)

_VERIFICATION_RESPONSE = json.dumps(
    {
        "verifications": {
            "seizure_frequency": {
                "grade": "exact_span",
                "supporting_quote": "two seizures per month",
                "notes": "",
            }
        },
        "overall_confidence": 0.88,
        "warnings": [],
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


# --- clines_epilepsy_modular ---

def test_modular_makes_one_call_per_field_family() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run = run_clines_epilepsy_modular(records, _dataset(records), "mod", "test", provider)

    assert len(provider.requests) == len(CORE_FIELD_FAMILIES)
    assert run.harness == "clines_epilepsy_modular"


def test_modular_architecture_family() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run = run_clines_epilepsy_modular(records, _dataset(records), "mod", "test", provider)

    assert run.architecture_family == ArchitectureFamily.CLINES_INSPIRED_MODULAR.value


def test_modular_budget_reflects_calls_per_row() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run = run_clines_epilepsy_modular(records, _dataset(records), "mod", "test", provider)

    assert run.budget.llm_calls_per_row == len(CORE_FIELD_FAMILIES)


def test_modular_preserves_modular_artifacts() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run = run_clines_epilepsy_modular(records, _dataset(records), "mod", "test", provider)

    artifacts = run.rows[0]["modular_artifacts"]
    assert "chunks" in artifacts
    for family in CORE_FIELD_FAMILIES:
        assert family.value in artifacts
        fam_art = artifacts[family.value]
        assert "status_annotation" in fam_art
        assert "verification" in fam_art


def test_modular_frequency_normalization_in_artifacts() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run = run_clines_epilepsy_modular(records, _dataset(records), "mod", "test", provider)

    freq_norm = run.rows[0]["modular_artifacts"]["seizure_frequency"]["frequency_normalization"]
    assert isinstance(freq_norm, dict)


def test_modular_invalid_json_marks_invalid_output() -> None:
    records = _records()
    provider = MockProvider(["not json"] * len(CORE_FIELD_FAMILIES))

    run = run_clines_epilepsy_modular(records, _dataset(records), "mod", "test", provider)

    assert run.rows[0]["payload"]["invalid_output"] is True


def test_modular_requests_include_field_family_metadata() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run_clines_epilepsy_modular(records, _dataset(records), "mod", "test", provider)

    families_seen = {req.metadata.get("field_family") for req in provider.requests}
    assert families_seen == {f.value for f in CORE_FIELD_FAMILIES}


def test_modular_complexity_field_populated() -> None:
    records = _records()
    provider = MockProvider([_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES))

    run = run_clines_epilepsy_modular(records, _dataset(records), "mod", "test", provider)

    assert "modules" in run.complexity
    assert "chunking" in run.complexity["modules"]


# --- clines_epilepsy_verified ---

def test_verified_makes_extra_verification_call() -> None:
    records = _records()
    # N family calls + 1 verification call
    responses = [_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES) + [_VERIFICATION_RESPONSE]
    provider = MockProvider(responses)

    run = run_clines_epilepsy_verified(records, _dataset(records), "ver", "test", provider)

    assert len(provider.requests) == len(CORE_FIELD_FAMILIES) + 1
    assert run.harness == "clines_epilepsy_verified"


def test_verified_budget_is_n_families_plus_one() -> None:
    records = _records()
    responses = [_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES) + [_VERIFICATION_RESPONSE]
    provider = MockProvider(responses)

    run = run_clines_epilepsy_verified(records, _dataset(records), "ver", "test", provider)

    assert run.budget.llm_calls_per_row == len(CORE_FIELD_FAMILIES) + 1


def test_verified_stores_provider_verification_artifact() -> None:
    records = _records()
    responses = [_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES) + [_VERIFICATION_RESPONSE]
    provider = MockProvider(responses)

    run = run_clines_epilepsy_verified(records, _dataset(records), "ver", "test", provider)

    artifacts = run.rows[0]["modular_artifacts"]
    assert "provider_verification" in artifacts
    assert artifacts["provider_verification"]["parse_valid"] is True
    assert "verifications" in artifacts["provider_verification"]


def test_verified_architecture_family() -> None:
    records = _records()
    responses = [_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES) + [_VERIFICATION_RESPONSE]
    provider = MockProvider(responses)

    run = run_clines_epilepsy_verified(records, _dataset(records), "ver", "test", provider)

    assert run.architecture_family == ArchitectureFamily.CLINES_INSPIRED_MODULAR.value


def test_verified_handles_bad_verification_json() -> None:
    records = _records()
    responses = [_FULL_RESPONSE] * len(CORE_FIELD_FAMILIES) + ["not json"]
    provider = MockProvider(responses)

    run = run_clines_epilepsy_verified(records, _dataset(records), "ver", "test", provider)

    pv = run.rows[0]["modular_artifacts"]["provider_verification"]
    assert pv["parse_valid"] is False


# --- CLI integration for clines_epilepsy_modular ---

def test_modular_cli_from_replay_file(tmp_path) -> None:
    replay_responses = [
        {
            "content": _FULL_RESPONSE,
            "usage": {"input_tokens": 30, "output_tokens": 10},
        }
    ] * len(CORE_FIELD_FAMILIES)
    replay = tmp_path / "replay.json"
    replay.write_text(json.dumps(replay_responses), encoding="utf-8")
    output = tmp_path / "modular.json"

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_experiment.py"),
            str(FIXTURE_PATH),
            "--harness",
            "clines_epilepsy_modular",
            "--limit",
            "1",
            "--run-id",
            "mod_test",
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
    assert data["harness"] == "clines_epilepsy_modular"
    assert data["budget"]["llm_calls_per_row"] == len(CORE_FIELD_FAMILIES)
