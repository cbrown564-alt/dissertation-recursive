"""Tests for locked M-C3 broader-field scoring rules."""

from __future__ import annotations

from pathlib import Path

from epilepsy_agents.broader_field_schema import TIER1A_JSON_SCHEMA, tier1a_user_prompt
from epilepsy_agents.mc3 import score_adjudication_csv, scored_field_keys, shadow_field_keys


REPO_ROOT = Path(__file__).parent.parent


def test_locked_subset_keys():
    assert scored_field_keys() == ["current_medications", "investigations"]
    assert shadow_field_keys() == ["seizure_types"]


def test_completed_adjudication_scores_locked_subset():
    score = score_adjudication_csv(
        REPO_ROOT / "docs" / "adjudication" / "h008_guideline_matched_25rows_scoring.csv"
    )

    assert score["phase"] == "M-C3"
    assert score["sourceRowCount"] == 25
    assert score["totalScoredItems"] == 92

    medications = score["fields"]["current_medications"]
    assert medications["totalItems"] == 44
    assert medications["valueCorrect"] == 42
    assert medications["statusCorrect"] == 44
    assert medications["lockedSupportedItems"] == 42

    investigations = score["fields"]["investigations"]
    assert investigations["totalItems"] == 48
    assert investigations["valueCorrect"] == 43
    assert investigations["valuePartial"] == 3
    assert investigations["statusCorrect"] == 45
    assert investigations["normalizationCorrect"] == 46
    assert investigations["lockedSupportedItems"] == 42

    assert score["shadow"]["seizure_types"]["totalItems"] == 42
    assert score["shadow"]["seizure_types"]["scored"] is False


def test_investigation_schema_has_status_and_non_diagnostic_prompt_rule():
    investigation_schema = TIER1A_JSON_SCHEMA["properties"]["investigations"]["items"]

    assert "status" in investigation_schema["required"]
    assert "status" in investigation_schema["properties"]

    prompt = tier1a_user_prompt("Synthetic letter text.")
    assert "non_diagnostic" in prompt
    assert "completed, planned, historical, pending, conditional, uncertain" in prompt
    assert "Do not map non-diagnostic EEG wording to normal" in prompt
    assert "explicitly names or clearly describes a test" in prompt
