from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from epilepsy_extraction.evaluation.labels import ParsedLabel, parse_label
from epilepsy_extraction.schemas import Prediction


@dataclass(frozen=True)
class EvaluationRow:
    source_row_index: int
    gold_label: str
    predicted_label: str
    exact_match: bool
    gold_monthly_rate: float | None
    predicted_monthly_rate: float | None
    monthly_rate_match: bool
    gold_pragmatic_class: str
    predicted_pragmatic_class: str
    gold_purist_class: str
    predicted_purist_class: str
    confidence: float


def monthly_rate_match(
    gold: float | None,
    predicted: float | None,
    tolerance: float = 0.15,
) -> bool:
    if gold is None or predicted is None:
        return gold is predicted
    if gold == 1000.0 or predicted == 1000.0:
        return gold == predicted
    if gold == 0.0 or predicted == 0.0:
        return gold == predicted
    return abs(gold - predicted) <= abs(gold) * tolerance


def parse_validity_summary(component_results: Iterable[tuple[str, bool]]) -> dict[str, object]:
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    for component, is_valid in component_results:
        totals[component]["total"] += 1
        if is_valid:
            totals[component]["valid"] += 1
        else:
            totals[component]["invalid"] += 1

    return {
        component: {
            "valid": counts["valid"],
            "invalid": counts["invalid"],
            "total": counts["total"],
            "valid_rate": counts["valid"] / counts["total"] if counts["total"] else 0.0,
        }
        for component, counts in sorted(totals.items())
    }


def evaluate_prediction(
    source_row_index: int,
    gold_label: str,
    prediction: Prediction,
) -> EvaluationRow:
    gold = parse_label(gold_label)
    predicted = _parsed_prediction(prediction)
    return EvaluationRow(
        source_row_index=source_row_index,
        gold_label=gold_label,
        predicted_label=prediction.label,
        exact_match=gold_label.strip().lower() == prediction.label.strip().lower(),
        gold_monthly_rate=gold.monthly_rate,
        predicted_monthly_rate=predicted.monthly_rate,
        monthly_rate_match=monthly_rate_match(gold.monthly_rate, predicted.monthly_rate),
        gold_pragmatic_class=gold.pragmatic_class,
        predicted_pragmatic_class=predicted.pragmatic_class,
        gold_purist_class=gold.purist_class,
        predicted_purist_class=predicted.purist_class,
        confidence=prediction.confidence,
    )


def classification_report(gold: Iterable[str], predicted: Iterable[str]) -> dict[str, object]:
    gold_list = list(gold)
    predicted_list = list(predicted)
    labels = sorted(set(gold_list) | set(predicted_list))
    per_class: dict[str, dict[str, float]] = {}
    totals = Counter()

    for label in labels:
        tp = sum(1 for g, p in zip(gold_list, predicted_list) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold_list, predicted_list) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold_list, predicted_list) if g == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        support = sum(1 for g in gold_list if g == label)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
        totals.update(tp=tp, fp=fp, fn=fn, support=support)

    micro_precision = totals["tp"] / (totals["tp"] + totals["fp"]) if totals["tp"] + totals["fp"] else 0.0
    micro_recall = totals["tp"] / (totals["tp"] + totals["fn"]) if totals["tp"] + totals["fn"] else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if micro_precision + micro_recall
        else 0.0
    )
    macro_f1 = sum(row["f1"] for row in per_class.values()) / len(per_class) if per_class else 0.0
    weighted_f1 = (
        sum(row["f1"] * row["support"] for row in per_class.values()) / len(gold_list)
        if gold_list
        else 0.0
    )
    return {
        "micro_f1": micro_f1,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "per_class": per_class,
    }


def summarize(rows: list[EvaluationRow]) -> dict[str, object]:
    exact = sum(row.exact_match for row in rows) / len(rows) if rows else 0.0
    monthly = sum(row.monthly_rate_match for row in rows) / len(rows) if rows else 0.0
    pragmatic = classification_report(
        [row.gold_pragmatic_class for row in rows],
        [row.predicted_pragmatic_class for row in rows],
    )
    purist = classification_report(
        [row.gold_purist_class for row in rows],
        [row.predicted_purist_class for row in rows],
    )
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        confusion[row.gold_pragmatic_class][row.predicted_pragmatic_class] += 1
    return {
        "n": len(rows),
        "exact_label_accuracy": exact,
        "monthly_rate_accuracy_tolerance_15pct": monthly,
        "pragmatic": pragmatic,
        "purist": purist,
        "pragmatic_confusion": {key: dict(value) for key, value in confusion.items()},
    }


def _parsed_prediction(prediction: Prediction) -> ParsedLabel:
    if (
        prediction.parsed_monthly_rate is not None
        and prediction.pragmatic_class is not None
        and prediction.purist_class is not None
    ):
        return ParsedLabel(
            original=prediction.label,
            monthly_rate=prediction.parsed_monthly_rate,
            pragmatic_class=prediction.pragmatic_class,
            purist_class=prediction.purist_class,
            kind=parse_label(prediction.label).kind,
        )
    return parse_label(prediction.label)
