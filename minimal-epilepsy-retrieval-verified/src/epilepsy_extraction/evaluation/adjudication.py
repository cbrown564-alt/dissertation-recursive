from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


ADJUDICATION_COLUMNS: tuple[str, ...] = (
    "run_id",
    "row_id",
    "source_row_index",
    "harness",
    "architecture_family",
    "model_registry_entry",
    "model",
    "provider",
    "field_family",
    "item_index",
    "emitted_value",
    "reference_value",
    "evidence",
    "value_score",
    "status_temporality_score",
    "normalization_score",
    "evidence_grade",
    "error_tags",
    "adjudicator_note",
)

ADJUDICATION_ERROR_TAGS: frozenset[str] = frozenset(
    {
        "missed_item",
        "spurious_item",
        "wrong_value",
        "wrong_status",
        "wrong_temporality",
        "wrong_normalization",
        "wrong_field_family",
        "unsupported_evidence",
        "overbroad_evidence",
        "missing_evidence",
        "parse_or_schema_error",
        "retrieval_recall_loss",
        "aggregation_conflict",
        "baseline_mapping_error",
        "wrong_temporal_status",
        "unsupported_overclaim",
        "eeg_non_specific",
        "conditional_investigation",
        "investigation_type_confusion",
        "diagnosis_vs_seizure_type",
        "semiology_fragment",
        "pattern_modifier",
        "frequency_anchor_error",
        "medication_status_error",
        "missing_expected_item",
        "schema_valid_but_clinically_wrong",
    }
)


def build_adjudication_rows(run_records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in run_records:
        for run_row in run.get("rows", []) or []:
            if not isinstance(run_row, Mapping):
                continue
            rows.extend(_rows_for_run_row(run, run_row))
    return rows


def write_adjudication_sheet(rows: Sequence[Mapping[str, Any]], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ADJUDICATION_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column, "")) for column in ADJUDICATION_COLUMNS})
    return output_path


def read_adjudication_sheet(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    _validate_columns(rows, path)
    _validate_error_tags(rows)
    return rows


def summarize_adjudication(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    completed = sum(1 for row in rows if _is_completed(row))
    field_counts = Counter(str(row.get("field_family", "")) for row in rows)
    evidence_counts = Counter(_blank_to_status(row.get("evidence_grade")) for row in rows)
    error_counts: Counter[str] = Counter()
    score_counts: dict[str, Counter[str]] = {
        "value_score": Counter(),
        "status_temporality_score": Counter(),
        "normalization_score": Counter(),
    }

    for row in rows:
        for tag in _split_tags(row.get("error_tags", "")):
            error_counts[tag] += 1
        for score_name, counts in score_counts.items():
            counts[_blank_to_status(row.get(score_name))] += 1

    return {
        "rows": total,
        "completed_rows": completed,
        "not_adjudicated_rows": total - completed,
        "completion_rate": completed / total if total else 0.0,
        "field_family_counts": dict(sorted(field_counts.items())),
        "evidence_grade_counts": dict(sorted(evidence_counts.items())),
        "error_tag_counts": dict(sorted(error_counts.items())),
        "score_counts": {name: dict(sorted(counts.items())) for name, counts in score_counts.items()},
    }


def write_adjudication_summary(summary: Mapping[str, Any], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def load_run_records(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    return [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]


def _rows_for_run_row(run: Mapping[str, Any], run_row: Mapping[str, Any]) -> list[dict[str, Any]]:
    payload = run_row.get("payload", {})
    payload = payload if isinstance(payload, Mapping) else {}
    final = payload.get("final", {})
    final = final if isinstance(final, Mapping) else {}
    evaluation = run_row.get("evaluation", {})
    evaluation = evaluation if isinstance(evaluation, Mapping) else {}
    base = {
        "run_id": run.get("run_id", ""),
        "row_id": run_row.get("row_id", ""),
        "source_row_index": run_row.get("source_row_index", evaluation.get("source_row_index", "")),
        "harness": run.get("harness", ""),
        "architecture_family": run.get("architecture_family", ""),
        "model_registry_entry": run.get("model_registry_entry", ""),
        "model": run.get("model", ""),
        "provider": run.get("provider", ""),
    }

    rows: list[dict[str, Any]] = []
    seizure_frequency = final.get("seizure_frequency", {})
    if isinstance(seizure_frequency, Mapping):
        rows.append(
            _adjudication_row(
                base,
                field_family="seizure_frequency",
                item_index=0,
                emitted_value=_value_from_mapping(seizure_frequency),
                reference_value=evaluation.get("gold_label", ""),
                evidence=_first_evidence(final.get("citations"), run_row.get("prediction")),
            )
        )

    rows.extend(
        _item_rows(
            base,
            "current_medications",
            final.get("current_medications"),
            reference_value="",
        )
    )
    rows.extend(_item_rows(base, "investigations", final.get("investigations"), reference_value=""))
    rows.extend(_item_rows(base, "seizure_classification", final.get("seizure_types"), reference_value=""))
    rows.extend(_item_rows(base, "seizure_classification", final.get("seizure_features"), reference_value=""))
    rows.extend(
        _item_rows(base, "seizure_classification", final.get("seizure_pattern_modifiers"), reference_value="")
    )
    rows.extend(_optional_mapping_row(base, "epilepsy_classification", final.get("epilepsy_type"), 0))
    rows.extend(_optional_mapping_row(base, "epilepsy_classification", final.get("epilepsy_syndrome"), 1))
    return rows


def _item_rows(
    base: Mapping[str, Any],
    field_family: str,
    items: Any,
    reference_value: str,
) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            rows.append(
                _adjudication_row(
                    base,
                    field_family=field_family,
                    item_index=index,
                    emitted_value=str(item),
                    reference_value=reference_value,
                    evidence="",
                )
            )
            continue
        rows.append(
            _adjudication_row(
                base,
                field_family=field_family,
                item_index=index,
                emitted_value=_value_from_mapping(item),
                reference_value=reference_value,
                evidence=_evidence_from_mapping(item),
            )
        )
    return rows


def _optional_mapping_row(
    base: Mapping[str, Any],
    field_family: str,
    item: Any,
    item_index: int,
) -> list[dict[str, Any]]:
    if item is None:
        return []
    if isinstance(item, Mapping):
        emitted_value = _value_from_mapping(item)
        evidence = _evidence_from_mapping(item)
    else:
        emitted_value = str(item)
        evidence = ""
    return [
        _adjudication_row(
            base,
            field_family=field_family,
            item_index=item_index,
            emitted_value=emitted_value,
            reference_value="",
            evidence=evidence,
        )
    ]


def _adjudication_row(
    base: Mapping[str, Any],
    field_family: str,
    item_index: int,
    emitted_value: str,
    reference_value: Any,
    evidence: str,
) -> dict[str, Any]:
    return {
        **base,
        "field_family": field_family,
        "item_index": item_index,
        "emitted_value": emitted_value,
        "reference_value": reference_value or "",
        "evidence": evidence,
        "value_score": "",
        "status_temporality_score": "",
        "normalization_score": "",
        "evidence_grade": "",
        "error_tags": "",
        "adjudicator_note": "",
    }


def _value_from_mapping(item: Mapping[str, Any]) -> str:
    for key in ("value", "label", "name", "type", "normalized_value", "result", "description"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return json.dumps(dict(item), sort_keys=True)


def _evidence_from_mapping(item: Mapping[str, Any]) -> str:
    evidence = item.get("evidence")
    if isinstance(evidence, Mapping):
        return str(evidence.get("quote", ""))
    if evidence not in (None, ""):
        return str(evidence)
    citations = item.get("citations")
    return _first_quote(citations)


def _first_evidence(citations: Any, prediction: Any) -> str:
    quote = _first_quote(citations)
    if quote:
        return quote
    if isinstance(prediction, Mapping):
        return _first_quote(prediction.get("evidence"))
    return ""


def _first_quote(value: Any) -> str:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, Mapping):
            return str(first.get("quote", ""))
        return str(first)
    if isinstance(value, Mapping):
        return str(value.get("quote", ""))
    return ""


def _validate_columns(rows: Sequence[Mapping[str, Any]], path: str | Path) -> None:
    if not rows:
        return
    missing = set(ADJUDICATION_COLUMNS) - set(rows[0].keys())
    if missing:
        raise ValueError(f"Adjudication sheet {path} missing required columns: {sorted(missing)}")


def _validate_error_tags(rows: Sequence[Mapping[str, Any]]) -> None:
    unknown = sorted({tag for row in rows for tag in _split_tags(row.get("error_tags", ""))} - ADJUDICATION_ERROR_TAGS)
    if unknown:
        raise ValueError(f"Unknown adjudication error tags: {unknown}")


def _split_tags(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    return [tag.strip() for tag in str(value).replace("|", ";").split(";") if tag.strip()]


def _is_completed(row: Mapping[str, Any]) -> bool:
    return any(
        str(row.get(column, "")).strip()
        for column in (
            "value_score",
            "status_temporality_score",
            "normalization_score",
            "evidence_grade",
            "error_tags",
            "adjudicator_note",
        )
    )


def _blank_to_status(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "not_adjudicated"


def _csv_value(value: Any) -> str:
    if isinstance(value, list | dict):
        return json.dumps(value, sort_keys=True)
    return "" if value is None else str(value)
