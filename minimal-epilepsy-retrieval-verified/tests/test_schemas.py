import json

from epilepsy_extraction.schemas import (
    CORE_FIELD_FAMILIES,
    BudgetMetadata,
    DatasetSlice,
    EvidenceGrade,
    ExtractionPayload,
    FINAL_EXTRACTION_REQUIRED_KEYS,
    FieldCoverageStatus,
    FieldFamily,
    FinalExtraction,
    RunRecord,
    SupportAssessment,
    failed_component_coverage,
    field_coverage,
    full_contract_coverage,
    missing_final_payload_keys,
    read_extraction_payload,
    resolve_code_version,
    validate_final_payload_keys,
    write_extraction_payload,
    write_run_record,
)


def test_support_assessment_full_credit_requires_exact_or_overlapping_span() -> None:
    assert SupportAssessment(EvidenceGrade.EXACT_SPAN).full_credit
    assert SupportAssessment(EvidenceGrade.OVERLAPPING_SPAN).full_credit
    assert not SupportAssessment(EvidenceGrade.SECTION_LEVEL).full_credit


def test_extraction_payload_defaults_to_not_implemented_coverage() -> None:
    payload = ExtractionPayload(
        pipeline_id="deterministic_baseline",
        final=FinalExtraction(),
    )

    assert payload.field_coverage["seizure_frequency"] == FieldCoverageStatus.NOT_IMPLEMENTED
    assert {field.value for field in CORE_FIELD_FAMILIES}.issubset(payload.field_coverage)


def test_write_run_record_creates_json(tmp_path) -> None:
    record = RunRecord(
        run_id="smoke",
        harness="deterministic_baseline",
        schema_version="1.0.0",
        dataset=DatasetSlice(
            dataset_id="synthetic_fixture",
            dataset_path="data/example.json",
            data_hash="abc123",
            row_ids=["1"],
            inclusion_criteria="fixture",
        ),
        model="none",
        provider="deterministic",
        temperature=0.0,
        prompt_version="none",
        code_version="test",
        budget=BudgetMetadata(),
    )

    output = write_run_record(record, tmp_path / "run.json")

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["dataset"]["n"] == 1
    assert data["harness"] == "deterministic_baseline"


def test_write_extraction_payload_round_trips_json(tmp_path) -> None:
    payload = ExtractionPayload(
        pipeline_id="deterministic_baseline",
        final=FinalExtraction(seizure_frequency={"value": "2 per month"}),
    )

    output = write_extraction_payload(payload, tmp_path / "payload.json")
    data = read_extraction_payload(output)

    assert data["pipeline_id"] == "deterministic_baseline"
    assert data["final"]["seizure_frequency"]["value"] == "2 per month"
    assert set(FINAL_EXTRACTION_REQUIRED_KEYS).issubset(data["final"])


def test_validate_final_payload_keys_reports_missing_required_keys() -> None:
    missing = missing_final_payload_keys({"seizure_frequency": {}})

    assert "current_medications" in missing
    try:
        validate_final_payload_keys({"seizure_frequency": {}})
    except ValueError as exc:
        assert "current_medications" in str(exc)
    else:
        raise AssertionError("Expected missing final payload keys to raise")


def test_field_coverage_helpers_mark_statuses() -> None:
    coverage = field_coverage(
        implemented=[FieldFamily.SEIZURE_FREQUENCY],
        partial=["current_medications"],
        failed=[FieldFamily.INVESTIGATIONS],
    )

    assert coverage["seizure_frequency"] == FieldCoverageStatus.IMPLEMENTED
    assert coverage["current_medications"] == FieldCoverageStatus.PARTIAL
    assert coverage["investigations"] == FieldCoverageStatus.FAILED
    assert full_contract_coverage()["rescue_medication"] == FieldCoverageStatus.IMPLEMENTED
    assert failed_component_coverage(["epilepsy_classification"])["epilepsy_classification"] == FieldCoverageStatus.FAILED


def test_resolve_code_version_prefers_explicit_value() -> None:
    assert resolve_code_version("test-version") == "test-version"
