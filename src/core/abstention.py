"""Helpers for explicit seizure-type abstention and granularity scoring."""

from __future__ import annotations

from typing import Any

UNKNOWN_SEIZURE_TYPE = "unknown seizure type"
SEIZURE_FREE = "seizure free"


def _normalize_label_set(labels: set[str] | list[str] | tuple[str, ...]) -> set[str]:
    return {str(label).strip() for label in labels if str(label).strip()}


def _specific_labels(labels: set[str]) -> set[str]:
    return {label for label in labels if label not in {UNKNOWN_SEIZURE_TYPE, SEIZURE_FREE}}


def classify_seizure_type_abstention(
    predicted_labels: set[str] | list[str] | tuple[str, ...],
    gold_labels: set[str] | list[str] | tuple[str, ...],
    predicted_collapsed_labels: set[str] | list[str] | tuple[str, ...],
    gold_collapsed_labels: set[str] | list[str] | tuple[str, ...],
) -> dict[str, Any]:
    """Classify seizure-type behavior under separate abstention and granularity views.

    The goal is not to adjudicate whether an inferred specific label is clinically
    reasonable. It is to expose when the benchmark expects abstention, when the
    model abstains too aggressively, and when a disagreement is only at the
    fine-grained label level rather than the collapsed benchmark category level.
    """

    predicted = _normalize_label_set(predicted_labels)
    gold = _normalize_label_set(gold_labels)
    predicted_collapsed = _normalize_label_set(predicted_collapsed_labels)
    gold_collapsed = _normalize_label_set(gold_collapsed_labels)

    predicted_specific = _specific_labels(predicted)
    gold_specific = _specific_labels(gold)

    gold_requires_abstention = UNKNOWN_SEIZURE_TYPE in gold and not gold_specific
    predicted_abstains = UNKNOWN_SEIZURE_TYPE in predicted and not predicted_specific
    gold_has_specific_type = bool(gold_specific)
    predicted_has_specific_type = bool(predicted_specific)
    strict_match = predicted == gold
    collapsed_match = predicted_collapsed == gold_collapsed
    any_prediction = bool(predicted)

    if gold_requires_abstention:
        if predicted_abstains:
            category = "correct_abstention"
        elif predicted_has_specific_type:
            category = "unsupported_specificity"
        elif not any_prediction:
            category = "missed_abstention"
        else:
            category = "other_abstention_error"
    elif gold_has_specific_type:
        if predicted_abstains:
            category = "over_abstention"
        elif strict_match:
            category = "specificity_match"
        elif collapsed_match and predicted_collapsed:
            category = "granularity_mismatch"
        elif not any_prediction:
            category = "missing_specific_prediction"
        else:
            category = "specificity_error"
    else:
        category = "non_abstention_case"

    return {
        "gold_requires_abstention": gold_requires_abstention,
        "predicted_abstention": predicted_abstains,
        "gold_has_specific_type": gold_has_specific_type,
        "predicted_has_specific_type": predicted_has_specific_type,
        "strict_match": strict_match,
        "collapsed_match": collapsed_match,
        "category": category,
        "predicted_specific_labels": sorted(predicted_specific),
        "gold_specific_labels": sorted(gold_specific),
        "predicted_labels": sorted(predicted),
        "gold_labels": sorted(gold),
        "predicted_collapsed_labels": sorted(predicted_collapsed),
        "gold_collapsed_labels": sorted(gold_collapsed),
    }
