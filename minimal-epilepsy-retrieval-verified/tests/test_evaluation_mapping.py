from epilepsy_extraction.evaluation import (
    ErrorTag,
    FIELD_FAMILY_TO_SCHEMA_KEYS,
    LITERATURE_ALIGNED_NAMES,
    SCHEMA_KEY_TO_FIELD_FAMILY,
    field_family_for_schema_key,
    literature_name,
)
from epilepsy_extraction.schemas.contracts import FieldFamily


def test_schema_key_to_field_family_covers_core_keys() -> None:
    assert field_family_for_schema_key("seizure_frequency") is FieldFamily.SEIZURE_FREQUENCY
    assert field_family_for_schema_key("current_medications") is FieldFamily.CURRENT_MEDICATIONS
    assert field_family_for_schema_key("investigations") is FieldFamily.INVESTIGATIONS
    assert field_family_for_schema_key("seizure_types") is FieldFamily.SEIZURE_CLASSIFICATION
    assert field_family_for_schema_key("epilepsy_type") is FieldFamily.EPILEPSY_CLASSIFICATION


def test_schema_key_to_field_family_returns_none_for_unknown() -> None:
    assert field_family_for_schema_key("nonexistent_field") is None


def test_field_family_to_schema_keys_is_inverse_of_reverse_map() -> None:
    for family, keys in FIELD_FAMILY_TO_SCHEMA_KEYS.items():
        for key in keys:
            assert SCHEMA_KEY_TO_FIELD_FAMILY[key] is family


def test_literature_aligned_names_covers_all_families() -> None:
    for family in FieldFamily:
        name = literature_name(family)
        assert name and isinstance(name, str)
        assert name != family.value or family not in LITERATURE_ALIGNED_NAMES


def test_literature_name_seizure_frequency_matches_expected() -> None:
    assert literature_name(FieldFamily.SEIZURE_FREQUENCY) == "Seizure frequency"
    assert literature_name(FieldFamily.CURRENT_MEDICATIONS) == "Current anti-seizure medications"


def test_error_tag_values_are_strings() -> None:
    for tag in ErrorTag:
        assert isinstance(tag.value, str)
        assert tag.value


def test_error_tag_covers_plan_specified_categories() -> None:
    tags = {t.value for t in ErrorTag}
    assert "wrong_value" in tags
    assert "wrong_status" in tags
    assert "wrong_temporality" in tags
    assert "wrong_normalization" in tags
    assert "unsupported_evidence" in tags
    assert "retrieval_recall_loss" in tags
    assert "aggregation_conflict" in tags
    assert "baseline_mapping_error" in tags
