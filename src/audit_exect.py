#!/usr/bin/env python3
"""ExECT 2 (2025) gold-label quality audit — checks E1 through E8.

Runs all 200 documents and writes per-check CSV outputs plus a summary JSON
to audit/exect/. See docs/29_gold_audit_plan.md for specification.
"""

from __future__ import annotations

import csv
import json
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from intake import DEFAULT_EXECT_ROOT, parse_attribute, parse_textbound, read_text

DEFAULT_MARKUP_ROOT = Path("data/ExECT 2 (2025)/MarkupOutput_200_SyntheticEpilepsyLetters")
DEFAULT_OUTPUT_DIR = Path("audit/exect")

# ── Generic CUIPhrases that lose clinical specificity ─────────────────────────
GENERIC_CUIPHRASES: set[str] = {
    "focal", "generalised", "generalized", "drug", "brain", "transient",
    "occipital", "frontal", "temporal", "parietal", "seizure", "seizures",
    "epilepsy", "epileptic", "unknown", "null", "none", "other",
}


# ──────────────────────────────────────────────────────────────────────────────
# Data models
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class AnnAnnotation:
    doc_id: str
    ann_id: str
    entity_type: str
    start: int
    end: int
    span_text: str
    attributes: dict[str, str] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# Parsers
# ──────────────────────────────────────────────────────────────────────────────

def parse_ann_file(doc_id: str, ann_path: Path, txt_path: Path) -> tuple[list[AnnAnnotation], str]:
    source_text = read_text(txt_path)
    lines = read_text(ann_path).splitlines()

    raw_textbounds: list[tuple[str, str, int, int, str]] = []
    attr_by_target: dict[str, dict[str, str]] = {}

    for line in lines:
        tb = parse_textbound(line)
        if tb is not None:
            raw_textbounds.append(tb)
            continue
        attr = parse_attribute(line)
        if attr is not None:
            _, name, target, value = attr
            attr_by_target.setdefault(target, {})[name] = value

    annotations = []
    for ann_id, entity_type, start, end, span_text in raw_textbounds:
        annotations.append(
            AnnAnnotation(
                doc_id=doc_id,
                ann_id=ann_id,
                entity_type=entity_type,
                start=start,
                end=end,
                span_text=span_text.strip(),
                attributes=attr_by_target.get(ann_id, {}),
            )
        )
    return annotations, source_text


def load_all_annotations(exect_root: Path) -> dict[str, tuple[list[AnnAnnotation], str]]:
    result: dict[str, tuple[list[AnnAnnotation], str]] = {}
    for txt_path in sorted(exect_root.glob("EA*.txt")):
        doc_id = txt_path.stem
        ann_path = txt_path.with_suffix(".ann")
        if ann_path.exists():
            result[doc_id] = parse_ann_file(doc_id, ann_path, txt_path)
    return result


def read_csv_rows(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            with path.open("r", encoding=encoding, newline="") as fh:
                return [[cell.strip() for cell in row] for row in csv.reader(fh)]
        except UnicodeDecodeError:
            continue
    return []


# ──────────────────────────────────────────────────────────────────────────────
# E1: Span boundary integrity
# ──────────────────────────────────────────────────────────────────────────────

def check_span_integrity(ann: AnnAnnotation, source_text: str) -> dict[str, Any]:
    start, end = ann.start, ann.end
    span = ann.span_text
    source_slice = source_text[start:end] if 0 <= start < end <= len(source_text) else ""

    def _norm(t: str) -> str:
        return t.replace("-", " ").strip().lower()

    norm_span = _norm(span)
    norm_slice = _norm(source_slice)

    if norm_span == norm_slice:
        issue_type = "clean"
        severity = "ok"
    elif source_slice and source_slice.rstrip("-").strip() == span.rstrip("-").strip():
        issue_type = "trailing_separator"
        severity = "low"
    elif source_slice and source_slice.lstrip("-").strip() == span.lstrip("-").strip():
        issue_type = "leading_separator"
        severity = "low"
    elif source_slice and norm_slice.startswith(norm_span) and len(norm_span) < len(norm_slice):
        issue_type = "truncated_span"
        severity = "medium"
    elif source_slice and norm_span.startswith(norm_slice) and len(norm_slice) < len(norm_span):
        issue_type = "span_longer_than_source"
        severity = "medium"
    elif source_slice and (norm_span in norm_slice or norm_slice in norm_span):
        issue_type = "partial_overlap"
        severity = "medium"
    elif not source_slice:
        issue_type = "offset_out_of_range"
        severity = "high"
    else:
        # Check off-by-one
        slice_minus1 = _norm(source_text[max(0, start - 1): end])
        slice_plus1 = _norm(source_text[start: min(len(source_text), end + 1)])
        if norm_span == slice_minus1 or norm_span == slice_plus1:
            issue_type = "off_by_one"
            severity = "low"
        else:
            issue_type = "mismatch"
            severity = "high"

    missing_chars = max(0, len(_norm(source_slice)) - len(norm_span)) if issue_type == "truncated_span" else 0

    return {
        "doc_id": ann.doc_id,
        "ann_id": ann.ann_id,
        "entity_type": ann.entity_type,
        "start": start,
        "end": end,
        "span_text": span[:80],
        "source_slice": source_slice[:80],
        "issue_type": issue_type,
        "severity": severity,
        "missing_chars": missing_chars,
    }


def run_e1(all_anns: dict[str, tuple[list[AnnAnnotation], str]]) -> list[dict[str, Any]]:
    rows = []
    for doc_id, (anns, source_text) in all_anns.items():
        for ann in anns:
            rows.append(check_span_integrity(ann, source_text))
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# E2: Duplicate and conflicting labels
# ──────────────────────────────────────────────────────────────────────────────

def _overlap_chars(a: AnnAnnotation, b: AnnAnnotation) -> int:
    return max(0, min(a.end, b.end) - max(a.start, b.start))


def _overlap_fraction(a: AnnAnnotation, b: AnnAnnotation) -> float:
    chars = _overlap_chars(a, b)
    span_len = min(a.end - a.start, b.end - b.start)
    return chars / span_len if span_len else 0.0


def _numeric_attrs(ann: AnnAnnotation) -> dict[str, str]:
    numeric_keys = {
        "DrugDose", "NumberOfSeizures", "LowerNumberOfSeizures",
        "UpperNumberOfSeizures", "NumberOfTimePeriods", "Certainty",
        "Frequency", "OnsetAge",
    }
    return {k: v for k, v in ann.attributes.items() if k in numeric_keys}


def detect_conflicts(anns: list[AnnAnnotation]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_type: dict[str, list[AnnAnnotation]] = {}
    for ann in anns:
        by_type.setdefault(ann.entity_type, []).append(ann)

    for entity_type, group in by_type.items():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                frac = _overlap_fraction(a, b)
                if frac < 0.3:
                    continue
                a_nums = _numeric_attrs(a)
                b_nums = _numeric_attrs(b)
                shared_keys = set(a_nums) & set(b_nums)
                conflicts = [k for k in shared_keys if a_nums[k] != b_nums[k]]
                a_cui = a.attributes.get("CUIPhrase", "")
                b_cui = b.attributes.get("CUIPhrase", "")
                cui_mismatch = a_cui and b_cui and a_cui != b_cui

                if conflicts:
                    tier = "tier1_numeric_conflict"
                elif cui_mismatch:
                    tier = "tier2_cuiphrase_mismatch"
                elif frac >= 0.99 and not conflicts and not cui_mismatch:
                    tier = "tier3_exact_duplicate"
                else:
                    tier = "tier2_cuiphrase_mismatch" if cui_mismatch else "tier3_overlap_no_conflict"

                rows.append({
                    "doc_id": a.doc_id,
                    "entity_type": entity_type,
                    "ann_id_a": a.ann_id,
                    "ann_id_b": b.ann_id,
                    "start_a": a.start,
                    "end_a": a.end,
                    "start_b": b.start,
                    "end_b": b.end,
                    "overlap_fraction": round(frac, 3),
                    "conflicting_attributes": "; ".join(conflicts),
                    "a_values": "; ".join(f"{k}={a_nums[k]}" for k in conflicts),
                    "b_values": "; ".join(f"{k}={b_nums[k]}" for k in conflicts),
                    "cuiphrase_a": a_cui,
                    "cuiphrase_b": b_cui,
                    "tier": tier,
                })
    return rows


def run_e2(all_anns: dict[str, tuple[list[AnnAnnotation], str]]) -> list[dict[str, Any]]:
    rows = []
    for doc_id, (anns, _) in all_anns.items():
        rows.extend(detect_conflicts(anns))
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# E3: CUIPhrase specificity
# ──────────────────────────────────────────────────────────────────────────────

def classify_cuiphrase(phrase: str) -> str:
    if not phrase or phrase.lower() in {"null", "none", ""}:
        return "missing"
    normalized = phrase.strip().lower().rstrip("-")
    if normalized in GENERIC_CUIPHRASES:
        return "generic"
    if re.search(r"[()[\]{}]", normalized):
        return "malformed"
    if len(normalized) <= 4:
        return "generic"
    return "specific"


def run_e3(all_anns: dict[str, tuple[list[AnnAnnotation], str]]) -> list[dict[str, Any]]:
    rows = []
    for doc_id, (anns, _) in all_anns.items():
        for ann in anns:
            cui_phrase = ann.attributes.get("CUIPhrase", "")
            cui = ann.attributes.get("CUI", "")
            rows.append({
                "doc_id": doc_id,
                "ann_id": ann.ann_id,
                "entity_type": ann.entity_type,
                "cuiphrase": cui_phrase,
                "cui": cui,
                "cuiphrase_class": classify_cuiphrase(cui_phrase),
                "span_text": ann.span_text[:60],
            })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# E4: Medication attribute completeness and consistency
# ──────────────────────────────────────────────────────────────────────────────

def _span_contains_number(span: str, dose: str) -> bool:
    if not dose:
        return False
    nums_in_span = re.findall(r"\d+\.?\d*", span)
    try:
        dose_val = float(dose)
    except ValueError:
        return False
    return any(abs(float(n) - dose_val) < 0.01 for n in nums_in_span)


def check_prescription(ann: AnnAnnotation) -> dict[str, Any]:
    attrs = ann.attributes
    drug_name = attrs.get("DrugName", "")
    drug_dose = attrs.get("DrugDose", "")
    dose_unit = attrs.get("DoseUnit", "")
    frequency = attrs.get("Frequency", "")
    cui_phrase = attrs.get("CUIPhrase", "")
    span = ann.span_text

    dose_in_span = _span_contains_number(span, drug_dose) if drug_dose else None

    return {
        "doc_id": ann.doc_id,
        "ann_id": ann.ann_id,
        "span_text": span[:80],
        "drug_name": drug_name,
        "drug_dose": drug_dose,
        "dose_unit": dose_unit,
        "frequency": frequency,
        "cuiphrase": cui_phrase,
        "has_drug_name": bool(drug_name and drug_name.lower() not in {"null", "none"}),
        "has_dose": bool(drug_dose and drug_dose.lower() not in {"null", "none"}),
        "has_dose_unit": bool(dose_unit and dose_unit.lower() not in {"null", "none"}),
        "has_frequency": bool(frequency and frequency.lower() not in {"null", "none"}),
        "dose_in_span": dose_in_span,
    }


def run_e4(all_anns: dict[str, tuple[list[AnnAnnotation], str]]) -> list[dict[str, Any]]:
    rows = []
    for doc_id, (anns, _) in all_anns.items():
        prescriptions = [ann for ann in anns if ann.entity_type == "Prescription"]
        for ann in prescriptions:
            rows.append(check_prescription(ann))
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# E5: SeizureFrequency attribute completeness and temporal consistency
# ──────────────────────────────────────────────────────────────────────────────

def check_seizure_frequency(ann: AnnAnnotation) -> dict[str, Any]:
    attrs = ann.attributes
    exact_n = attrs.get("NumberOfSeizures", "")
    lower_n = attrs.get("LowerNumberOfSeizures", "")
    upper_n = attrs.get("UpperNumberOfSeizures", "")
    time_period = attrs.get("TimePeriod", "")
    n_time_periods = attrs.get("NumberOfTimePeriods", "")
    point_in_time = attrs.get("PointInTime", "")
    time_since = attrs.get("TimeSince_or_TimeOfEvent", "")
    freq_change = attrs.get("FrequencyChange", "")
    cui_phrase = attrs.get("CUIPhrase", "")

    has_count = bool(exact_n or lower_n or upper_n)
    has_period = bool(time_period)
    has_temporal_scope = bool(point_in_time or time_since or freq_change)

    # Seizure-free: NumberOfSeizures == 0
    try:
        is_seizure_free = exact_n and int(exact_n) == 0
    except (ValueError, TypeError):
        is_seizure_free = False

    # Active: any non-zero count
    try:
        is_active = any(
            int(v) > 0
            for v in [exact_n, lower_n, upper_n]
            if v and v.lower() not in {"null", "none"}
        )
    except (ValueError, TypeError):
        is_active = False

    issues = []
    if has_count and not has_period and not has_temporal_scope:
        issues.append("count_without_period_or_scope")
    if not has_count and not has_period and not has_temporal_scope and not freq_change:
        issues.append("no_count_no_period_no_scope")
    if not cui_phrase or cui_phrase.lower() in {"null", "none"}:
        issues.append("missing_cuiphrase")

    return {
        "doc_id": ann.doc_id,
        "ann_id": ann.ann_id,
        "span_text": ann.span_text[:80],
        "exact_n": exact_n,
        "lower_n": lower_n,
        "upper_n": upper_n,
        "time_period": time_period,
        "n_time_periods": n_time_periods,
        "point_in_time": point_in_time,
        "time_since": time_since,
        "freq_change": freq_change,
        "cuiphrase": cui_phrase,
        "has_count": has_count,
        "has_period": has_period,
        "has_temporal_scope": has_temporal_scope,
        "is_seizure_free": bool(is_seizure_free),
        "is_active": is_active,
        "issues": "; ".join(issues),
    }


def detect_sf_contradictions(doc_id: str, anns: list[AnnAnnotation]) -> list[dict[str, Any]]:
    sf_anns = [ann for ann in anns if ann.entity_type == "SeizureFrequency"]
    rows: list[dict[str, Any]] = []
    seizure_free = []
    active = []
    for ann in sf_anns:
        check = check_seizure_frequency(ann)
        if check["is_seizure_free"]:
            seizure_free.append(ann)
        elif check["is_active"]:
            active.append(ann)
    if seizure_free and active:
        for sf_ann in seizure_free:
            for act_ann in active:
                sf_scope = sf_ann.attributes.get("TimeSince_or_TimeOfEvent") or sf_ann.attributes.get("PointInTime")
                act_scope = act_ann.attributes.get("TimeSince_or_TimeOfEvent") or act_ann.attributes.get("PointInTime")
                rows.append({
                    "doc_id": doc_id,
                    "ann_id_seizure_free": sf_ann.ann_id,
                    "ann_id_active": act_ann.ann_id,
                    "sf_span": sf_ann.span_text[:60],
                    "active_span": act_ann.span_text[:60],
                    "sf_temporal_scope": sf_scope or "",
                    "active_temporal_scope": act_scope or "",
                    "resolvable_by_scope": bool(sf_scope and act_scope and sf_scope != act_scope),
                })
    return rows


def run_e5(all_anns: dict[str, tuple[list[AnnAnnotation], str]]) -> tuple[list[dict], list[dict]]:
    completeness_rows: list[dict[str, Any]] = []
    contradiction_rows: list[dict[str, Any]] = []
    for doc_id, (anns, _) in all_anns.items():
        sf_anns = [ann for ann in anns if ann.entity_type == "SeizureFrequency"]
        for ann in sf_anns:
            completeness_rows.append(check_seizure_frequency(ann))
        contradiction_rows.extend(detect_sf_contradictions(doc_id, anns))
    return completeness_rows, contradiction_rows


# ──────────────────────────────────────────────────────────────────────────────
# E6: CSV vs .ann consistency
# ──────────────────────────────────────────────────────────────────────────────

def run_e6(all_anns: dict[str, tuple[list[AnnAnnotation], str]], markup_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    # Build index of .ann span positions per doc for each entity type
    ann_index: dict[str, dict[str, set[tuple[int, int]]]] = {}
    for doc_id, (anns, _) in all_anns.items():
        ann_index[doc_id] = {}
        for ann in anns:
            ann_index[doc_id].setdefault(ann.entity_type, set()).add((ann.start, ann.end))

    csv_checks: list[tuple[str, str, int, int, int]] = [
        ("MarkupPrescriptions.csv", "Prescription", 1, 2, 0),
        ("MarkupSeizureFrequency.csv", "SeizureFrequency", 1, 2, 0),
        ("MarkupDiagnosis.csv", "Diagnosis", 1, 2, 0),
        ("MarkupInvestigations.csv", "Investigations", 1, 2, 0),
        ("MarkupPatientHistory.csv", "PatientHistory", 1, 2, 0),
        ("MakupBirthHist.csv", "BirthHistory", 1, 2, 0),
        ("MarkupOnset.csv", "Onset", 1, 2, 0),
        ("MarkupEpiCause.csv", "EpilepsyCause", 1, 2, 0),
        ("MarkupWhenDiag.csv", "WhenDiagnosed", 1, 2, 0),
    ]

    for csv_file, entity_type, start_col, end_col, doc_col in csv_checks:
        csv_rows = read_csv_rows(markup_root / csv_file)
        for row in csv_rows:
            if len(row) <= max(start_col, end_col, doc_col):
                continue
            doc_id_raw = row[doc_col]
            doc_id = Path(doc_id_raw).stem
            start_str, end_str = row[start_col], row[end_col]
            if not (start_str.lstrip("-").isdigit() and end_str.lstrip("-").isdigit()):
                continue
            start, end = int(start_str), int(end_str)

            if doc_id not in ann_index:
                issue = "doc_not_in_ann"
            elif entity_type not in ann_index[doc_id]:
                issue = "entity_type_not_in_doc"
            elif (start, end) not in ann_index[doc_id][entity_type]:
                # Tolerate ±2 chars for boundary drift
                found = any(
                    abs(s - start) <= 2 and abs(e - end) <= 2
                    for s, e in ann_index[doc_id].get(entity_type, set())
                )
                issue = "offset_near_match" if found else "offset_mismatch"
            else:
                issue = "ok"

            if issue != "ok":
                rows.append({
                    "csv_file": csv_file,
                    "entity_type": entity_type,
                    "doc_id": doc_id,
                    "csv_start": start,
                    "csv_end": end,
                    "issue": issue,
                })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# E7: Cross-document annotation consistency
# ──────────────────────────────────────────────────────────────────────────────

def run_e7(all_anns: dict[str, tuple[list[AnnAnnotation], str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    entity_types_with_negation = {"Diagnosis", "PatientHistory", "BirthHistory", "EpilepsyCause"}
    entity_counts_per_doc: dict[str, int] = {}

    for doc_id, (anns, _) in all_anns.items():
        entity_counts_per_doc[doc_id] = len(anns)
        by_type: dict[str, list[AnnAnnotation]] = {}
        for ann in anns:
            by_type.setdefault(ann.entity_type, []).append(ann)

        for entity_type, group in by_type.items():
            total = len(group)
            missing_negation = sum(1 for a in group if entity_type in entity_types_with_negation and not a.attributes.get("Negation"))
            missing_certainty = sum(1 for a in group if not a.attributes.get("Certainty"))
            missing_cui = sum(1 for a in group if not a.attributes.get("CUI"))
            rows.append({
                "doc_id": doc_id,
                "entity_type": entity_type,
                "count": total,
                "missing_negation": missing_negation,
                "missing_certainty": missing_certainty,
                "missing_cui": missing_cui,
                "negation_rate": round((total - missing_negation) / total, 3) if total else None,
                "certainty_rate": round((total - missing_certainty) / total, 3) if total else None,
                "cui_rate": round((total - missing_cui) / total, 3) if total else None,
            })

    # Flag outlier documents (entity count < mean - 2SD)
    counts = list(entity_counts_per_doc.values())
    mean_count = statistics.mean(counts)
    sd_count = statistics.stdev(counts) if len(counts) > 1 else 0.0
    threshold = mean_count - 2 * sd_count
    for row in rows:
        doc_total = entity_counts_per_doc[row["doc_id"]]
        row["doc_total_annotations"] = doc_total
        row["is_annotation_outlier"] = doc_total < threshold

    return rows


# ──────────────────────────────────────────────────────────────────────────────
# E8: Source letter quality
# ──────────────────────────────────────────────────────────────────────────────

ENCODING_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("utf8_double_encode_a", re.compile(r"Ã")),
    ("utf8_double_encode_i", re.compile(r"ï¿½")),
    ("utf8_double_encode_e", re.compile(r"â€")),
    ("utf8_nbsp", re.compile(r"Â")),
    ("replacement_char", re.compile(r"�")),
]

MALE_PRONOUNS = re.compile(r"\b(he|his|him|himself)\b", re.IGNORECASE)
FEMALE_PRONOUNS = re.compile(r"\b(she|her|hers|herself)\b", re.IGNORECASE)


def check_letter_quality(doc_id: str, source_text: str) -> dict[str, Any]:
    artefacts: list[str] = []
    for name, pattern in ENCODING_PATTERNS:
        if pattern.search(source_text):
            artefacts.append(name)

    male_count = len(MALE_PRONOUNS.findall(source_text))
    female_count = len(FEMALE_PRONOUNS.findall(source_text))
    pronoun_mismatch = male_count > 0 and female_count > 0

    has_greeting = bool(re.search(r"\bDear\b", source_text[:100], re.IGNORECASE))
    char_count = len(source_text)
    too_short = char_count < 200

    return {
        "doc_id": doc_id,
        "char_count": char_count,
        "encoding_artefacts": "; ".join(artefacts),
        "has_encoding_artefacts": bool(artefacts),
        "male_pronoun_count": male_count,
        "female_pronoun_count": female_count,
        "pronoun_mismatch": pronoun_mismatch,
        "has_greeting": has_greeting,
        "too_short": too_short,
    }


def run_e8(all_anns: dict[str, tuple[list[AnnAnnotation], str]]) -> list[dict[str, Any]]:
    return [check_letter_quality(doc_id, source_text) for doc_id, (_, source_text) in all_anns.items()]


# ──────────────────────────────────────────────────────────────────────────────
# Output helpers
# ──────────────────────────────────────────────────────────────────────────────

def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        val = str(row.get(key, ""))
        counts[val] = counts.get(val, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


# ──────────────────────────────────────────────────────────────────────────────
# Summary builder
# ──────────────────────────────────────────────────────────────────────────────

def build_summary(
    all_anns: dict[str, tuple[list[AnnAnnotation], str]],
    e1: list[dict],
    e2: list[dict],
    e3: list[dict],
    e4: list[dict],
    e5_completeness: list[dict],
    e5_contradictions: list[dict],
    e6: list[dict],
    e7: list[dict],
    e8: list[dict],
) -> dict[str, Any]:
    total_docs = len(all_anns)
    total_anns = sum(len(anns) for anns, _ in all_anns.values())

    # E1
    e1_issues = [r for r in e1 if r["issue_type"] != "clean"]
    e1_by_type = count_by(e1_issues, "issue_type")
    e1_by_entity = count_by(e1_issues, "entity_type")

    # E2
    e2_tier1 = [r for r in e2 if r["tier"] == "tier1_numeric_conflict"]
    e2_tier2 = [r for r in e2 if r["tier"] == "tier2_cuiphrase_mismatch"]
    e2_tier3 = [r for r in e2 if r["tier"] == "tier3_exact_duplicate"]

    # E3
    e3_by_class = count_by(e3, "cuiphrase_class")
    e3_generic = [r for r in e3 if r["cuiphrase_class"] == "generic"]
    e3_malformed = [r for r in e3 if r["cuiphrase_class"] == "malformed"]

    # E4
    e4_missing_dose = sum(1 for r in e4 if not r["has_dose"])
    e4_missing_unit = sum(1 for r in e4 if not r["has_dose_unit"])
    e4_missing_freq = sum(1 for r in e4 if not r["has_frequency"])
    e4_dose_not_in_span = sum(1 for r in e4 if r["has_dose"] and r["dose_in_span"] is False)

    # E5
    e5_with_issues = [r for r in e5_completeness if r["issues"]]
    e5_missing_cui = [r for r in e5_completeness if "missing_cuiphrase" in r.get("issues", "")]

    # E6
    e6_by_issue = count_by(e6, "issue")

    # E7 — aggregate attribute presence rates by entity type
    e7_by_type: dict[str, dict[str, Any]] = {}
    for row in e7:
        et = row["entity_type"]
        if et not in e7_by_type:
            e7_by_type[et] = {"total_annotations": 0, "missing_negation": 0, "missing_certainty": 0, "missing_cui": 0}
        e7_by_type[et]["total_annotations"] += row["count"]
        e7_by_type[et]["missing_negation"] += row["missing_negation"]
        e7_by_type[et]["missing_certainty"] += row["missing_certainty"]
        e7_by_type[et]["missing_cui"] += row["missing_cui"]
    for et, data in e7_by_type.items():
        n = data["total_annotations"]
        data["negation_population_rate"] = round((n - data["missing_negation"]) / n, 3) if n else None
        data["certainty_population_rate"] = round((n - data["missing_certainty"]) / n, 3) if n else None
        data["cui_population_rate"] = round((n - data["missing_cui"]) / n, 3) if n else None

    # E8
    e8_with_artefacts = sum(1 for r in e8 if r["has_encoding_artefacts"])
    e8_pronoun_mismatch = sum(1 for r in e8 if r["pronoun_mismatch"])
    e8_too_short = sum(1 for r in e8 if r["too_short"])

    return {
        "total_documents": total_docs,
        "total_annotations": total_anns,
        "E1_span_boundary": {
            "total_annotations": len(e1),
            "clean": sum(1 for r in e1 if r["issue_type"] == "clean"),
            "with_issues": len(e1_issues),
            "issue_rate": round(len(e1_issues) / len(e1), 4) if e1 else None,
            "by_issue_type": e1_by_type,
            "by_entity_type": e1_by_entity,
        },
        "E2_conflicts": {
            "tier1_numeric_conflicts": len(e2_tier1),
            "tier2_cuiphrase_mismatch": len(e2_tier2),
            "tier3_exact_duplicates": len(e2_tier3),
            "total_pairs": len(e2),
            "docs_with_tier1_conflict": len({r["doc_id"] for r in e2_tier1}),
        },
        "E3_cuiphrase_quality": {
            "total_annotations": len(e3),
            "by_class": e3_by_class,
            "generic_rate": round(len(e3_generic) / len(e3), 4) if e3 else None,
            "malformed_rate": round(len(e3_malformed) / len(e3), 4) if e3 else None,
            "top_generic_phrases": [r["cuiphrase"] for r in e3_generic[:20]],
        },
        "E4_prescriptions": {
            "total_prescriptions": len(e4),
            "missing_dose": e4_missing_dose,
            "missing_dose_rate": round(e4_missing_dose / len(e4), 4) if e4 else None,
            "missing_unit": e4_missing_unit,
            "missing_frequency": e4_missing_freq,
            "dose_not_in_span": e4_dose_not_in_span,
            "dose_not_in_span_rate": round(e4_dose_not_in_span / len(e4), 4) if e4 else None,
        },
        "E5_seizure_frequency": {
            "total_sf_annotations": len(e5_completeness),
            "with_issues": len(e5_with_issues),
            "issue_rate": round(len(e5_with_issues) / len(e5_completeness), 4) if e5_completeness else None,
            "missing_cuiphrase": len(e5_missing_cui),
            "sf_vs_active_contradictions": len(e5_contradictions),
            "contradiction_docs": len({r["doc_id"] for r in e5_contradictions}),
        },
        "E6_csv_ann_consistency": {
            "total_mismatch_rows": len(e6),
            "by_issue": e6_by_issue,
        },
        "E7_cross_doc_consistency": {
            "by_entity_type": e7_by_type,
            "outlier_docs": sorted({r["doc_id"] for r in e7 if r.get("is_annotation_outlier")}),
        },
        "E8_letter_quality": {
            "total_docs": len(e8),
            "with_encoding_artefacts": e8_with_artefacts,
            "artefact_rate": round(e8_with_artefacts / len(e8), 4) if e8 else None,
            "pronoun_mismatch": e8_pronoun_mismatch,
            "too_short": e8_too_short,
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    exect_root = Path(args.exect_root)
    markup_root = Path(args.markup_root)
    output_dir = Path(args.output_dir)

    print("Loading all .ann files...")
    all_anns = load_all_annotations(exect_root)
    print(f"  {len(all_anns)} documents, {sum(len(a) for a, _ in all_anns.values())} annotations")

    print("E1: Span boundary integrity...")
    e1 = run_e1(all_anns)
    write_csv(output_dir / "E1_span_boundary.csv", e1)
    e1_issues = sum(1 for r in e1 if r["issue_type"] != "clean")
    print(f"  {e1_issues}/{len(e1)} annotations have boundary issues")

    print("E2: Duplicate and conflicting labels...")
    e2 = run_e2(all_anns)
    write_csv(output_dir / "E2_duplicates_conflicts.csv", e2)
    e2_t1 = sum(1 for r in e2 if r["tier"] == "tier1_numeric_conflict")
    print(f"  {len(e2)} overlapping pairs; {e2_t1} tier-1 numeric conflicts")

    print("E3: CUIPhrase specificity...")
    e3 = run_e3(all_anns)
    write_csv(output_dir / "E3_cuiphrase_quality.csv", e3)
    e3_generic = sum(1 for r in e3 if r["cuiphrase_class"] == "generic")
    print(f"  {e3_generic}/{len(e3)} CUIPhrases are generic or missing")

    print("E4: Medication attributes...")
    e4 = run_e4(all_anns)
    write_csv(output_dir / "E4_prescriptions.csv", e4)
    print(f"  {len(e4)} prescription annotations checked")

    print("E5: SeizureFrequency completeness and contradictions...")
    e5_completeness, e5_contradictions = run_e5(all_anns)
    write_csv(output_dir / "E5_seizure_frequency_completeness.csv", e5_completeness)
    write_csv(output_dir / "E5_seizure_frequency_contradictions.csv", e5_contradictions)
    print(f"  {len(e5_completeness)} SF annotations; {len(e5_contradictions)} seizure-free vs active contradictions")

    print("E6: CSV vs .ann consistency...")
    e6 = run_e6(all_anns, markup_root)
    write_csv(output_dir / "E6_csv_ann_consistency.csv", e6)
    print(f"  {len(e6)} CSV rows without matching .ann offset")

    print("E7: Cross-document annotation consistency...")
    e7 = run_e7(all_anns)
    write_csv(output_dir / "E7_cross_doc_consistency.csv", e7)

    print("E8: Source letter quality...")
    e8 = run_e8(all_anns)
    write_csv(output_dir / "E8_letter_quality.csv", e8)
    e8_artefacts = sum(1 for r in e8 if r["has_encoding_artefacts"])
    print(f"  {e8_artefacts}/{len(e8)} letters have encoding artefacts")

    print("Building summary...")
    summary = build_summary(all_anns, e1, e2, e3, e4, e5_completeness, e5_contradictions, e6, e7, e8)
    write_json(output_dir / "summary.json", summary)

    # Manual review queue: high-severity items across all checks
    review_rows: list[dict[str, Any]] = []
    for r in e1:
        if r["severity"] == "high":
            review_rows.append({"check": "E1", "priority": "high", "doc_id": r["doc_id"], "detail": f"{r['entity_type']} {r['issue_type']}: ann='{r['span_text'][:40]}' src='{r['source_slice'][:40]}'"})
    for r in e2:
        if r["tier"] == "tier1_numeric_conflict":
            review_rows.append({"check": "E2", "priority": "high", "doc_id": r["doc_id"], "detail": f"{r['entity_type']} conflict: {r['conflicting_attributes']} — a={r['a_values']} b={r['b_values']}"})
    for r in e5_contradictions:
        if not r["resolvable_by_scope"]:
            review_rows.append({"check": "E5", "priority": "high", "doc_id": r["doc_id"], "detail": f"SF contradiction: seizure-free '{r['sf_span'][:40]}' vs active '{r['active_span'][:40]}'"})
    write_csv(output_dir / "manual_review_queue.csv", review_rows)

    print(f"\nAll outputs written to {output_dir}/")
    print(f"Summary: {output_dir / 'summary.json'}")
    print(f"Manual review queue: {len(review_rows)} high-priority items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
