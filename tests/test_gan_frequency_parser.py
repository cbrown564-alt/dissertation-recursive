"""Smoke tests for gan_frequency label parser, category mappings, and retrieval harnesses.

Covers the label forms listed in PARSER_CONTRACT, the edge cases
from the minimal-repo comparison (WP2 acceptance criteria), and
the retrieval span selector and prompt constructors.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gan_frequency import (
    GanExample,
    label_to_categories,
    label_to_monthly_frequency,
    retrieve_frequency_spans,
    gan_retrieval_highlight_prompt,
    gan_retrieval_only_ablation_prompt,
    UNKNOWN_X,
)


def _cats(label: str) -> tuple[str, str]:
    c = label_to_categories(label)
    return c["pragmatic"], c["purist"]


def test_3_to_4_per_month() -> None:
    x = label_to_monthly_frequency("3 to 4 per month")
    assert 3.0 <= x <= 4.0, x
    assert _cats("3 to 4 per month") == ("frequent", "(1/M,1/W)")


def test_hyphen_range_per_month() -> None:
    # "3-4 per month" normalizes hyphens to spaces → "3 4 per month"
    x = label_to_monthly_frequency("3-4 per month")
    assert 3.0 <= x <= 4.0, x
    assert _cats("3-4 per month") == ("frequent", "(1/M,1/W)")


def test_cluster_per_month() -> None:
    x = label_to_monthly_frequency("2 cluster per month, 6 per cluster")
    assert abs(x - 12.0) < 0.1, x
    assert _cats("2 cluster per month, 6 per cluster")[0] == "frequent"


def test_seizure_free_12_month() -> None:
    assert label_to_monthly_frequency("seizure free for 12 month") == 0.0
    assert _cats("seizure free for 12 month") == ("NS", "NS")


def test_seizure_free_multiple_month() -> None:
    assert label_to_monthly_frequency("seizure free for multiple month") == 0.0
    assert _cats("seizure free for multiple month") == ("NS", "NS")


def test_unknown() -> None:
    assert label_to_monthly_frequency("unknown") == UNKNOWN_X
    assert _cats("unknown") == ("UNK", "UNK")


def test_no_seizure_frequency_reference() -> None:
    assert label_to_monthly_frequency("no seizure frequency reference") == UNKNOWN_X
    assert _cats("no seizure frequency reference") == ("UNK", "UNK")


def test_1_per_month_is_infrequent() -> None:
    assert _cats("1 per month") == ("infrequent", "1/M")


def test_2_per_month_is_frequent() -> None:
    assert _cats("2 per month") == ("frequent", "(1/M,1/W)")


def test_1_per_week_is_frequent() -> None:
    assert _cats("1 per week")[0] == "frequent"


# --- Retrieval span selector ---

_EXAMPLE = GanExample(
    document_id="test_doc",
    source_row_index=0,
    text=(
        "Dear Dr Smith,\n"
        "Thank you for reviewing this patient.\n"
        "She has been having 3 seizures per month.\n"
        "She remains on levetiracetam 500mg twice daily.\n"
        "She has been seizure-free for the last 6 months.\n"
    ),
    gold_label="3 per month",
    evidence_reference="3 seizures per month",
    analysis="",
)

_NO_FREQ_EXAMPLE = GanExample(
    document_id="test_doc_no_freq",
    source_row_index=1,
    text="Dear Dr Jones,\nThank you for seeing this patient with epilepsy.\nMedication unchanged.",
    gold_label="no seizure frequency reference",
    evidence_reference="",
    analysis="",
)


def test_retrieve_spans_finds_frequency_sentence() -> None:
    spans = retrieve_frequency_spans(_EXAMPLE.text)
    assert any("3 seizures per month" in s for s in spans), spans


def test_retrieve_spans_finds_seizure_free_sentence() -> None:
    spans = retrieve_frequency_spans(_EXAMPLE.text)
    assert any("seizure-free" in s.lower() for s in spans), spans


def test_retrieve_spans_empty_for_no_frequency_text() -> None:
    spans = retrieve_frequency_spans(_NO_FREQ_EXAMPLE.text)
    assert spans == [], spans


def test_retrieval_highlight_prompt_includes_spans_and_full_letter() -> None:
    spans = retrieve_frequency_spans(_EXAMPLE.text)
    prompt = gan_retrieval_highlight_prompt(_EXAMPLE, spans)
    assert "Retrieved candidate spans" in prompt
    assert "Full clinical letter" in prompt
    assert _EXAMPLE.text in prompt
    for span in spans:
        assert span in prompt


def test_retrieval_highlight_prompt_no_spans_has_fallback_note() -> None:
    prompt = gan_retrieval_highlight_prompt(_EXAMPLE, [])
    assert "none found" in prompt
    assert "Full clinical letter" in prompt


def test_retrieval_only_ablation_with_spans_excludes_full_letter() -> None:
    spans = ["She has been having 3 seizures per month."]
    prompt = gan_retrieval_only_ablation_prompt(_EXAMPLE, spans, fallback_used=False)
    assert "Retrieved seizure frequency spans" in prompt
    assert _EXAMPLE.text not in prompt


def test_retrieval_only_ablation_fallback_includes_full_letter() -> None:
    prompt = gan_retrieval_only_ablation_prompt(_EXAMPLE, [], fallback_used=True)
    assert "full-letter fallback" in prompt
    assert _EXAMPLE.text in prompt
