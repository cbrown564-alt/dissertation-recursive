#!/usr/bin/env python3
"""Gan (2026) gold-label quality audit — checks G1 through G8.

G1–G4 and G8 run on all 1,500 records programmatically.
G5–G7 run on a 500-record stratified sample.

Outputs per-check CSVs to audit/gan/ plus a summary JSON.
See docs/29_gold_audit_plan.md for specification.
"""

from __future__ import annotations

import csv
import json
import random
import re
from pathlib import Path
from typing import Any

from gan_frequency import (
    GanExample,
    UNKNOWN_X,
    load_gan_examples,
    label_to_monthly_frequency,
    normalize_label,
    pragmatic_category_from_x,
    purist_category_from_x,
)

DEFAULT_GAN_PATH = Path("data/Gan (2026)/synthetic_data_subset_1500.json")
DEFAULT_OUTPUT_DIR = Path("audit/gan")

# Specific-duration patterns for seizure-free precision check
_SPECIFIC_DURATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(\d+)\s*(month|months)\b", re.IGNORECASE),
    re.compile(r"\b(\d+)\s*(year|years)\b", re.IGNORECASE),
    re.compile(r"\b(\d+)\s*(week|weeks)\b", re.IGNORECASE),
    re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(month|months|year|years|week|weeks)\b", re.IGNORECASE),
    re.compile(r"\b(eighteen|fifteen|sixteen|seventeen|twenty)\s*(month|months)\b", re.IGNORECASE),
]

_CLUSTER_TERMS = re.compile(
    r"\b(cluster|clusters|batch|burst|series of seizures|group of seizures|clustering)\b",
    re.IGNORECASE,
)

_ENCODING_ARTEFACTS: list[tuple[str, re.Pattern[str]]] = [
    ("utf8_double_A", re.compile(r"Ã")),
    ("utf8_fffd", re.compile(r"ï¿½")),
    ("utf8_double_e", re.compile(r"â€")),
    ("utf8_nbsp", re.compile(r"Â")),
    ("replacement_char", re.compile(r"[^\x00-\x7F -ɏ]")),
]

MALE_PRONOUNS = re.compile(r"\b(he|his|him|himself)\b", re.IGNORECASE)
FEMALE_PRONOUNS = re.compile(r"\b(she|her|hers|herself)\b", re.IGNORECASE)

WRITTEN_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "twenty": 20, "twenty-four": 24,
}


# ──────────────────────────────────────────────────────────────────────────────
# Load raw JSON (we need fields beyond what GanExample captures)
# ──────────────────────────────────────────────────────────────────────────────

def load_raw_records(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON list: {path}")
    return data


def extract_record_fields(record: dict[str, Any], index: int) -> dict[str, Any]:
    block = record.get("check__Seizure Frequency Number") or {}
    labels = block.get("seizure_frequency_number") or []
    reference = block.get("reference") or []
    return {
        "source_row_index": int(record.get("source_row_index", index)),
        "document_id": f"GAN{record.get('source_row_index', index)}",
        "gold_label_raw": labels[0] if labels else "",
        "gold_label": normalize_label(labels[0]) if labels else "",
        "reference_0": normalize_label(reference[0]) if len(reference) > 0 else "",
        "reference_1": str(reference[1]) if len(reference) > 1 else "",
        "analysis": str(block.get("analysis") or ""),
        "text": str(record.get("clinic_date") or ""),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Stratified sample
# ──────────────────────────────────────────────────────────────────────────────

def stratified_sample(records: list[dict[str, Any]], n: int = 500, seed: int = 42) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    strata: dict[str, list[dict[str, Any]]] = {"NS": [], "infrequent": [], "frequent": [], "UNK": []}
    for rec in records:
        x = label_to_monthly_frequency(rec["gold_label"])
        cat = pragmatic_category_from_x(x)
        strata.setdefault(cat, []).append(rec)

    targets = {"NS": 65, "infrequent": 175, "frequent": 180, "UNK": 80}
    sample: list[dict[str, Any]] = []
    for cat, target in targets.items():
        bucket = strata.get(cat, [])
        drawn = rng.sample(bucket, min(target, len(bucket)))
        sample.extend(drawn)

    # If short (due to small strata), top up from remainder
    if len(sample) < n:
        sampled_ids = {r["document_id"] for r in sample}
        remainder = [r for r in records if r["document_id"] not in sampled_ids]
        sample.extend(rng.sample(remainder, min(n - len(sample), len(remainder))))

    return sample


# ──────────────────────────────────────────────────────────────────────────────
# G1: Reference field consistency (all 1,500)
# ──────────────────────────────────────────────────────────────────────────────

def classify_ref_mismatch(label: str, ref0: str) -> str:
    if not label or not ref0:
        return "missing_field"
    if label == ref0:
        return "match"
    # Classify direction
    sf_label = label.startswith("seizure free")
    sf_ref = ref0.startswith("seizure free")
    unk_label = label in {"unknown", "no seizure frequency reference"}
    unk_ref = ref0 in {"unknown", "no seizure frequency reference"}

    if unk_ref and not unk_label:
        return "ref_unknown_label_specific"
    if not unk_ref and unk_label and not sf_label:
        return "ref_specific_label_unknown"
    if sf_ref and not sf_label:
        return "ref_seizure_free_label_rate"
    if sf_label and not sf_ref:
        return "ref_rate_label_seizure_free"
    if unk_ref and sf_label:
        return "ref_unknown_label_seizure_free"
    return "ref_rate_differs"


def run_g1(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for rec in records:
        label = rec["gold_label"]
        ref0 = rec["reference_0"]
        mismatch_type = classify_ref_mismatch(label, ref0)
        x_label = label_to_monthly_frequency(label)
        x_ref0 = label_to_monthly_frequency(ref0) if ref0 else UNKNOWN_X
        rows.append({
            "document_id": rec["document_id"],
            "source_row_index": rec["source_row_index"],
            "gold_label": label,
            "reference_0": ref0,
            "mismatch_type": mismatch_type,
            "is_mismatch": mismatch_type not in {"match", "missing_field"},
            "gold_pragmatic": pragmatic_category_from_x(x_label),
            "ref0_pragmatic": pragmatic_category_from_x(x_ref0),
            "category_changes": pragmatic_category_from_x(x_label) != pragmatic_category_from_x(x_ref0),
            "reference_1_excerpt": rec["reference_1"][:120],
        })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# G2: Label parsability and category consistency (all 1,500)
# ──────────────────────────────────────────────────────────────────────────────

_VALID_LABEL_PATTERNS = [
    re.compile(r"^[\d.]+ (?:to [\d.]+ )?per (?:[\d.]+ )?(day|week|month|year)s?$"),
    re.compile(r"^multiple per (?:day|week|month|year)$"),
    re.compile(r"^[\d.]+ cluster per (?:[\d.]+ )?(day|week|month|year)s?, [\d.a-z ]+ per cluster$"),
    re.compile(r"^seizure free for ([\d.]+ (month|year)s?|multiple (month|year)s?)$"),
    re.compile(r"^unknown$"),
    re.compile(r"^no seizure frequency reference$"),
]


def check_label_parsability(label: str) -> dict[str, Any]:
    x = label_to_monthly_frequency(label)
    is_unknown_label = label in {"unknown", "no seizure frequency reference"}
    parse_returns_unknown = x == UNKNOWN_X
    unparsable = parse_returns_unknown and not is_unknown_label

    matches_known_pattern = any(p.match(label) for p in _VALID_LABEL_PATTERNS)
    pragma = pragmatic_category_from_x(x)
    purist = purist_category_from_x(x)

    # Flag category paradoxes: seizure-free label → not NS
    sf_label = label.startswith("seizure free")
    category_paradox = (sf_label and pragma != "NS") or (is_unknown_label and pragma != "UNK")

    return {
        "label": label,
        "x_per_month": x if x != UNKNOWN_X else None,
        "pragmatic": pragma,
        "purist": purist,
        "matches_pattern": matches_known_pattern,
        "parse_returns_unknown_x": parse_returns_unknown,
        "unparsable": unparsable,
        "category_paradox": category_paradox,
    }


def run_g2(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for rec in records:
        check = check_label_parsability(rec["gold_label"])
        rows.append({
            "document_id": rec["document_id"],
            "source_row_index": rec["source_row_index"],
            "gold_label": rec["gold_label"],
            **check,
        })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# G3: Seizure-free precision audit (all 1,500)
# ──────────────────────────────────────────────────────────────────────────────

def _find_specific_duration(text: str) -> tuple[str, str]:
    for pattern in _SPECIFIC_DURATION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0), match.group(1)
    return "", ""


def run_g3(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for rec in records:
        label = rec["gold_label"]
        if label not in {"seizure free for multiple month", "seizure free for multiple year"}:
            continue
        combined_text = rec["reference_1"] + " " + rec["analysis"]
        duration_phrase, duration_value = _find_specific_duration(combined_text)
        rows.append({
            "document_id": rec["document_id"],
            "source_row_index": rec["source_row_index"],
            "gold_label": label,
            "has_specific_duration_in_evidence": bool(duration_phrase),
            "specific_duration_found": duration_phrase,
            "duration_value": duration_value,
            "reference_1_excerpt": rec["reference_1"][:120],
            "analysis_excerpt": rec["analysis"][:200],
        })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# G4: "Multiple" as count precision (all 1,500)
# ──────────────────────────────────────────────────────────────────────────────

_MULTIPLE_COUNT_PATTERN = re.compile(r"^multiple per (day|week|month|year)$")
_SPECIFIC_COUNT_IN_TEXT = re.compile(
    r"\b(\d+(?:\s*(?:to|-)\s*\d+)?)\s*(?:seizures?|episodes?|events?|fits?|attacks?)\s*(?:per|a|each|every)",
    re.IGNORECASE,
)


def run_g4(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for rec in records:
        label = rec["gold_label"]
        if not _MULTIPLE_COUNT_PATTERN.match(label):
            continue
        combined = rec["reference_1"] + " " + rec["analysis"]
        specific_match = _SPECIFIC_COUNT_IN_TEXT.search(combined)
        rows.append({
            "document_id": rec["document_id"],
            "source_row_index": rec["source_row_index"],
            "gold_label": label,
            "has_specific_count_in_evidence": bool(specific_match),
            "specific_count_found": specific_match.group(0)[:60] if specific_match else "",
            "reference_1_excerpt": rec["reference_1"][:120],
            "analysis_excerpt": rec["analysis"][:200],
        })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# G5: Analysis-to-label consistency (500-record sample)
# ──────────────────────────────────────────────────────────────────────────────

_ARITHMETIC_PATTERN = re.compile(
    r"(\d+)\s*seizures?\s*(?:over|in|across|during|within)\s*(?:approximately\s*)?(\d+)\s*(month|week|year|day)s?",
    re.IGNORECASE,
)

_SEIZURE_FREE_SINCE = re.compile(
    r"\bno\s+(?:further\s+)?(?:seizures?|events?|episodes?|attacks?)\s+since\b",
    re.IGNORECASE,
)

_HISTORICAL_MARKERS = re.compile(
    r"\b(?:previously|historically|in the past|prior to|before)\b",
    re.IGNORECASE,
)

_CURRENT_MARKERS = re.compile(
    r"\b(?:currently|at present|now|recent|most recent|at this clinic)\b",
    re.IGNORECASE,
)


def _label_to_simple_rate(label: str) -> tuple[float | None, str]:
    """Parse label to (seizures_per_period, period_unit) for arithmetic check."""
    m = re.match(r"^([\d.]+) per (\d+ )?(day|week|month|year)$", label)
    if m:
        count = float(m.group(1))
        period_n = float(m.group(2)) if m.group(2) else 1.0
        return count / period_n, m.group(3)
    return None, ""


def check_analysis_consistency(rec: dict[str, Any]) -> dict[str, Any]:
    label = rec["gold_label"]
    analysis = rec["analysis"]
    reference_1 = rec["reference_1"]

    # Arithmetic consistency
    arith_match = _ARITHMETIC_PATTERN.search(analysis)
    arithmetic_consistent = None
    arithmetic_label_rate = None
    arithmetic_analysis_rate = None

    if arith_match:
        n_seizures = int(arith_match.group(1))
        n_periods = int(arith_match.group(2))
        period_unit = arith_match.group(3).lower()
        arithmetic_analysis_rate = f"{n_seizures} per {n_periods} {period_unit}"
        expected_norm = normalize_label(arithmetic_analysis_rate)
        arithmetic_consistent = (label == expected_norm or label.startswith(f"{n_seizures} per {n_periods}"))
        arithmetic_label_rate = label

    # Seizure-free override present but label is a rate
    sf_override_conflict = bool(
        _SEIZURE_FREE_SINCE.search(analysis)
        and not label.startswith("seizure free")
        and label not in {"unknown", "no seizure frequency reference"}
    )

    # Label is seizure-free but analysis discusses active seizures
    reverse_sf_conflict = bool(
        label.startswith("seizure free")
        and re.search(r"\b(\d+|multiple|several|frequent|occasional)\s*(?:seizures?|events?|episodes?)\b", analysis, re.IGNORECASE)
        and not _SEIZURE_FREE_SINCE.search(analysis)
    )

    # Historical vs current flag
    has_historical = bool(_HISTORICAL_MARKERS.search(analysis))
    has_current = bool(_CURRENT_MARKERS.search(analysis))
    temporal_ambiguity = has_historical and not has_current

    # Unknown label but analysis contains a specific rate
    specific_rate_in_unk = False
    if label == "unknown":
        specific_rate_in_unk = bool(arith_match or re.search(r"\d+\s*per\s*\d*\s*(day|week|month|year)", analysis, re.IGNORECASE))

    issues = []
    if arith_match and arithmetic_consistent is False:
        issues.append("arithmetic_mismatch")
    if sf_override_conflict:
        issues.append("seizure_free_in_analysis_but_label_is_rate")
    if reverse_sf_conflict:
        issues.append("label_seizure_free_but_analysis_has_active_seizures")
    if temporal_ambiguity:
        issues.append("historical_language_may_affect_current_label")
    if specific_rate_in_unk:
        issues.append("unknown_label_but_specific_rate_in_analysis")

    return {
        "document_id": rec["document_id"],
        "source_row_index": rec["source_row_index"],
        "gold_label": label,
        "gold_pragmatic": pragmatic_category_from_x(label_to_monthly_frequency(label)),
        "arithmetic_match_found": bool(arith_match),
        "arithmetic_analysis_rate": arithmetic_analysis_rate or "",
        "arithmetic_consistent": arithmetic_consistent,
        "sf_override_conflict": sf_override_conflict,
        "reverse_sf_conflict": reverse_sf_conflict,
        "temporal_ambiguity": temporal_ambiguity,
        "specific_rate_in_unknown_label": specific_rate_in_unk,
        "issues": "; ".join(issues),
        "analysis_excerpt": analysis[:250],
        "reference_1_excerpt": reference_1[:120],
    }


def run_g5(sample: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [check_analysis_consistency(rec) for rec in sample]


# ──────────────────────────────────────────────────────────────────────────────
# G6: Cluster handling (500-record sample)
# ──────────────────────────────────────────────────────────────────────────────

def check_cluster_handling(rec: dict[str, Any]) -> dict[str, Any] | None:
    label = rec["gold_label"]
    combined = rec["reference_1"] + " " + rec["analysis"]
    if not _CLUSTER_TERMS.search(combined):
        return None

    is_cluster_label = "cluster per" in label
    x_label = label_to_monthly_frequency(label)
    pragma_label = pragmatic_category_from_x(x_label)

    # Estimate what cluster label might give (if plain rate, approximate cluster total)
    # We can only do this if we find both cluster frequency and per-cluster count
    cluster_freq_match = re.search(
        r"(\d+)\s*cluster(?:s)?\s*(?:per|every|a)\s*(\d+\s*)?(week|month|day|year)",
        combined, re.IGNORECASE,
    )
    per_cluster_match = re.search(
        r"(\d+)\s*(?:seizures?|events?|episodes?)\s*(?:per|in|each)\s*cluster",
        combined, re.IGNORECASE,
    )

    category_change_possible = False
    cluster_rate_estimate = ""
    if cluster_freq_match and per_cluster_match and not is_cluster_label:
        # Rough estimate: cluster_freq * per_cluster = total seizures
        try:
            n_clusters = float(cluster_freq_match.group(1))
            per_cluster = float(per_cluster_match.group(1))
            period_n_str = (cluster_freq_match.group(2) or "1").strip()
            period_n = float(period_n_str) if period_n_str else 1.0
            unit = cluster_freq_match.group(3).lower()
            from gan_frequency import monthly_factor
            factor = monthly_factor(unit) or 1.0
            total_monthly = n_clusters * per_cluster * factor / period_n
            pragma_cluster = pragmatic_category_from_x(total_monthly)
            category_change_possible = pragma_cluster != pragma_label
            cluster_rate_estimate = f"{total_monthly:.2f}/month → {pragma_cluster}"
        except (ValueError, TypeError):
            pass

    return {
        "document_id": rec["document_id"],
        "source_row_index": rec["source_row_index"],
        "gold_label": label,
        "gold_pragmatic": pragma_label,
        "is_cluster_label": is_cluster_label,
        "cluster_term_in_evidence": True,
        "category_change_if_cluster_preserved": category_change_possible,
        "cluster_rate_estimate": cluster_rate_estimate,
        "reference_1_excerpt": rec["reference_1"][:120],
        "analysis_excerpt": rec["analysis"][:200],
    }


def run_g6(sample: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for rec in sample:
        result = check_cluster_handling(rec)
        if result is not None:
            rows.append(result)
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# G7: Contradictory letter contents (500-record sample)
# ──────────────────────────────────────────────────────────────────────────────

_NO_FURTHER_SEIZURES = re.compile(
    r"\bno\s+(?:further\s+)?(?:seizures?|events?|episodes?|attacks?|fits?)\b",
    re.IGNORECASE,
)

_ACTIVE_SEIZURES = re.compile(
    r"\b(?:continues?\s+to\s+have|still\s+has|ongoing|having|experiencing)\s+(?:seizures?|events?|episodes?)\b",
    re.IGNORECASE,
)

_DAILY_FREQ = re.compile(r"\b(?:daily|every\s+day|each\s+day)\b", re.IGNORECASE)
_WEEKLY_FREQ = re.compile(r"\b(?:weekly|every\s+week|per\s+week)\b", re.IGNORECASE)

_NON_EPILEPTIC = re.compile(
    r"\b(?:non-epileptic|dissociative|functional\s+neurological|psychogenic|NES|NEAD)\b",
    re.IGNORECASE,
)


def check_letter_contradictions(rec: dict[str, Any]) -> dict[str, Any]:
    label = rec["gold_label"]
    text = rec["text"]
    analysis = rec["analysis"]
    combined = text + " " + analysis

    has_no_further = bool(_NO_FURTHER_SEIZURES.search(combined))
    has_active = bool(_ACTIVE_SEIZURES.search(combined))
    contradiction_active_vs_sf = has_no_further and has_active

    # Daily/weekly frequency but label is seizure-free or unknown
    has_high_freq_statement = bool(_DAILY_FREQ.search(combined) or _WEEKLY_FREQ.search(combined))
    freq_sf_mismatch = has_high_freq_statement and label.startswith("seizure free")

    has_non_epileptic = bool(_NON_EPILEPTIC.search(combined))
    # Non-epileptic + seizure-free label might be counting non-epileptic as seizure-free
    non_epileptic_sf_ambiguity = has_non_epileptic and label.startswith("seizure free")

    # "Since last assessment" without a date
    no_date_sf = bool(
        re.search(r"\bsince\s+(?:the\s+)?(?:last|previous)\s+(?:clinic|visit|assessment|appointment)\b", combined, re.IGNORECASE)
        and label in {"seizure free for multiple month", "seizure free for multiple year"}
        and not re.search(r"\b\d{4}\b|\b\d{1,2}/\d{1,2}\b", combined)
    )

    issues = []
    severity = "acceptable"
    if contradiction_active_vs_sf and freq_sf_mismatch:
        issues.append("active_seizures_and_sf_in_same_letter")
        severity = "irresolvable"
    elif contradiction_active_vs_sf:
        issues.append("no_further_seizures_contradicts_active_language")
        severity = "annotator_dependent"
    elif freq_sf_mismatch:
        issues.append("daily_or_weekly_frequency_with_seizure_free_label")
        severity = "annotator_dependent"
    if non_epileptic_sf_ambiguity:
        issues.append("seizure_free_may_include_non_epileptic_events")
        severity = max(severity, "annotator_dependent", key=lambda s: ["acceptable", "annotator_dependent", "irresolvable"].index(s))
    if no_date_sf:
        issues.append("seizure_free_since_last_visit_without_date")

    return {
        "document_id": rec["document_id"],
        "source_row_index": rec["source_row_index"],
        "gold_label": label,
        "gold_pragmatic": pragmatic_category_from_x(label_to_monthly_frequency(label)),
        "contradiction_active_vs_sf": contradiction_active_vs_sf,
        "freq_sf_mismatch": freq_sf_mismatch,
        "non_epileptic_sf_ambiguity": non_epileptic_sf_ambiguity,
        "no_date_seizure_free": no_date_sf,
        "severity": severity,
        "issues": "; ".join(issues),
        "text_excerpt": text[:200],
        "analysis_excerpt": analysis[:200],
    }


def run_g7(sample: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [check_letter_contradictions(rec) for rec in sample]


# ──────────────────────────────────────────────────────────────────────────────
# G8: Encoding and synthetic artefacts (all 1,500)
# ──────────────────────────────────────────────────────────────────────────────

def run_g8(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for rec in records:
        text = rec["text"]
        found_artefacts = [name for name, pattern in _ENCODING_ARTEFACTS if pattern.search(text)]
        male = len(MALE_PRONOUNS.findall(text))
        female = len(FEMALE_PRONOUNS.findall(text))
        rows.append({
            "document_id": rec["document_id"],
            "source_row_index": rec["source_row_index"],
            "encoding_artefacts": "; ".join(found_artefacts),
            "has_encoding_artefacts": bool(found_artefacts),
            "male_pronoun_count": male,
            "female_pronoun_count": female,
            "pronoun_mismatch": male > 0 and female > 0,
            "text_length": len(text),
        })
    return rows


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
    records: list[dict[str, Any]],
    sample: list[dict[str, Any]],
    g1: list[dict],
    g2: list[dict],
    g3: list[dict],
    g4: list[dict],
    g5: list[dict],
    g6: list[dict],
    g7: list[dict],
    g8: list[dict],
) -> dict[str, Any]:
    total = len(records)
    sample_n = len(sample)

    # Label distribution (full 1,500)
    label_dist: dict[str, int] = {}
    pragma_dist: dict[str, int] = {}
    for r in g2:
        label_dist[r["gold_label"]] = label_dist.get(r["gold_label"], 0) + 1
        pragma_dist[r["pragmatic"]] = pragma_dist.get(r["pragmatic"], 0) + 1

    # G1
    g1_mismatches = [r for r in g1 if r["is_mismatch"]]
    g1_category_changes = [r for r in g1_mismatches if r["category_changes"]]

    # G2
    g2_unparsable = [r for r in g2 if r["unparsable"]]
    g2_paradox = [r for r in g2 if r["category_paradox"]]

    # G3
    g3_with_duration = [r for r in g3 if r["has_specific_duration_in_evidence"]]

    # G4
    g4_with_count = [r for r in g4 if r["has_specific_count_in_evidence"]]

    # G5 (sample only)
    g5_with_issues = [r for r in g5 if r["issues"]]
    g5_arith_mismatch = [r for r in g5 if r.get("arithmetic_consistent") is False]
    g5_sf_conflict = [r for r in g5 if r.get("sf_override_conflict")]

    # G6 (sample only)
    g6_category_change = [r for r in g6 if r.get("category_change_if_cluster_preserved")]

    # G7 (sample only)
    g7_irresolvable = [r for r in g7 if r["severity"] == "irresolvable"]
    g7_annotator_dep = [r for r in g7 if r["severity"] == "annotator_dependent"]

    # G8
    g8_artefacts = [r for r in g8 if r["has_encoding_artefacts"]]
    g8_pronoun = [r for r in g8 if r["pronoun_mismatch"]]

    return {
        "total_records": total,
        "sample_size": sample_n,
        "label_distribution": dict(sorted(label_dist.items(), key=lambda x: -x[1])[:30]),
        "pragmatic_distribution": pragma_dist,
        "G1_reference_consistency": {
            "total_records": len(g1),
            "mismatches": len(g1_mismatches),
            "mismatch_rate": round(len(g1_mismatches) / len(g1), 4) if g1 else None,
            "category_changing_mismatches": len(g1_category_changes),
            "by_mismatch_type": count_by(g1_mismatches, "mismatch_type"),
        },
        "G2_label_parsability": {
            "total_records": len(g2),
            "unparsable_labels": len(g2_unparsable),
            "unparsable_rate": round(len(g2_unparsable) / len(g2), 4) if g2 else None,
            "category_paradoxes": len(g2_paradox),
        },
        "G3_seizure_free_precision": {
            "total_multiple_month_year": len(g3),
            "with_specific_duration_in_evidence": len(g3_with_duration),
            "precision_opportunity_rate": round(len(g3_with_duration) / len(g3), 4) if g3 else None,
        },
        "G4_multiple_count_precision": {
            "total_multiple_count_labels": len(g4),
            "with_specific_count_in_evidence": len(g4_with_count),
            "precision_opportunity_rate": round(len(g4_with_count) / len(g4), 4) if g4 else None,
        },
        "G5_analysis_consistency": {
            "sample_size": len(g5),
            "with_any_issue": len(g5_with_issues),
            "issue_rate": round(len(g5_with_issues) / len(g5), 4) if g5 else None,
            "arithmetic_mismatches": len(g5_arith_mismatch),
            "seizure_free_conflicts": len(g5_sf_conflict),
            "by_issue_type": count_by([{"i": issue} for r in g5 for issue in r["issues"].split("; ") if issue], "i"),
        },
        "G6_cluster_handling": {
            "sample_size": len(sample),
            "cluster_mention_cases": len(g6),
            "cluster_mention_rate": round(len(g6) / len(sample), 4) if sample else None,
            "category_changing_collapses": len(g6_category_change),
        },
        "G7_letter_contradictions": {
            "sample_size": len(g7),
            "irresolvable": len(g7_irresolvable),
            "annotator_dependent": len(g7_annotator_dep),
            "irresolvable_rate": round(len(g7_irresolvable) / len(g7), 4) if g7 else None,
            "by_severity": count_by(g7, "severity"),
        },
        "G8_encoding_artefacts": {
            "total_records": len(g8),
            "with_encoding_artefacts": len(g8_artefacts),
            "artefact_rate": round(len(g8_artefacts) / len(g8), 4) if g8 else None,
            "pronoun_mismatches": len(g8_pronoun),
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gan-path", default=str(DEFAULT_GAN_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--sample-seed", type=int, default=42)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    print("Loading Gan records...")
    raw_records_json = json.loads(Path(args.gan_path).read_text(encoding="utf-8"))
    records = [extract_record_fields(r, i) for i, r in enumerate(raw_records_json) if isinstance(r, dict)]
    print(f"  {len(records)} records loaded")

    print(f"Drawing stratified sample (n={args.sample_size})...")
    sample = stratified_sample(records, n=args.sample_size, seed=args.sample_seed)
    print(f"  Sample: {len(sample)} records")

    print("G1: Reference field consistency (all records)...")
    g1 = run_g1(records)
    write_csv(output_dir / "G1_reference_consistency.csv", g1)
    g1_mismatch = sum(1 for r in g1 if r["is_mismatch"])
    g1_cat_change = sum(1 for r in g1 if r["category_changes"])
    print(f"  {g1_mismatch}/{len(g1)} mismatches; {g1_cat_change} change pragmatic category")

    print("G2: Label parsability (all records)...")
    g2 = run_g2(records)
    write_csv(output_dir / "G2_label_parsability.csv", g2)
    g2_unparsable = sum(1 for r in g2 if r["unparsable"])
    print(f"  {g2_unparsable} unparsable labels")

    print("G3: Seizure-free precision (all records)...")
    g3 = run_g3(records)
    write_csv(output_dir / "G3_seizure_free_precision.csv", g3)
    g3_specific = sum(1 for r in g3 if r["has_specific_duration_in_evidence"])
    print(f"  {g3_specific}/{len(g3)} 'multiple month/year' labels have specific duration in evidence")

    print("G4: Multiple-count precision (all records)...")
    g4 = run_g4(records)
    write_csv(output_dir / "G4_multiple_count_precision.csv", g4)
    g4_specific = sum(1 for r in g4 if r["has_specific_count_in_evidence"])
    print(f"  {g4_specific}/{len(g4)} 'multiple per period' labels have specific count in evidence")

    print("G5: Analysis consistency (sample)...")
    g5 = run_g5(sample)
    write_csv(output_dir / "G5_analysis_consistency.csv", g5)
    g5_issues = sum(1 for r in g5 if r["issues"])
    print(f"  {g5_issues}/{len(g5)} sampled records have analysis consistency issues")

    print("G6: Cluster handling (sample)...")
    g6 = run_g6(sample)
    write_csv(output_dir / "G6_cluster_handling.csv", g6)
    g6_cat_change = sum(1 for r in g6 if r.get("category_change_if_cluster_preserved"))
    print(f"  {len(g6)} cluster-mention cases in sample; {g6_cat_change} with potential category change")

    print("G7: Letter contradictions (sample)...")
    g7 = run_g7(sample)
    write_csv(output_dir / "G7_letter_contradictions.csv", g7)
    g7_irr = sum(1 for r in g7 if r["severity"] == "irresolvable")
    g7_dep = sum(1 for r in g7 if r["severity"] == "annotator_dependent")
    print(f"  {g7_irr} irresolvable; {g7_dep} annotator-dependent; {len(g7) - g7_irr - g7_dep} acceptable")

    print("G8: Encoding artefacts (all records)...")
    g8 = run_g8(records)
    write_csv(output_dir / "G8_encoding_artefacts.csv", g8)
    g8_art = sum(1 for r in g8 if r["has_encoding_artefacts"])
    g8_pro = sum(1 for r in g8 if r["pronoun_mismatch"])
    print(f"  {g8_art}/{len(g8)} records have encoding artefacts; {g8_pro} have pronoun mismatches")

    print("Building summary...")
    summary = build_summary(records, sample, g1, g2, g3, g4, g5, g6, g7, g8)
    write_json(output_dir / "summary.json", summary)

    # Manual review queue: highest-priority flags
    review_rows: list[dict[str, Any]] = []
    for r in g1:
        if r["is_mismatch"] and r["category_changes"]:
            review_rows.append({"check": "G1", "priority": "high", "document_id": r["document_id"], "detail": f"label='{r['gold_label']}' ref0='{r['reference_0']}' type={r['mismatch_type']}"})
    for r in g5:
        if "arithmetic_mismatch" in r.get("issues", "") or "seizure_free_in_analysis_but_label_is_rate" in r.get("issues", ""):
            review_rows.append({"check": "G5", "priority": "high", "document_id": r["document_id"], "detail": r["issues"][:100]})
    for r in g7:
        if r["severity"] == "irresolvable":
            review_rows.append({"check": "G7", "priority": "high", "document_id": r["document_id"], "detail": r["issues"][:100]})
    write_csv(output_dir / "manual_review_queue.csv", review_rows)

    print(f"\nAll outputs written to {output_dir}/")
    print(f"Summary: {output_dir / 'summary.json'}")
    print(f"Manual review queue: {len(review_rows)} high-priority items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
