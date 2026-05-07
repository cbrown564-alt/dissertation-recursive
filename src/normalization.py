#!/usr/bin/env python3
"""Canonical normalizers for recovery-phase scoring and diagnostics."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


NULL_STRINGS = {"", "null", "none", "nan", "n/a", "na", "not stated", "unknown"}

NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "once": "1",
    "two": "2",
    "twice": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "a": "1",
    "an": "1",
}

ASM_SYNONYMS = {
    "acetazolamide": "acetazolamide",
    "brivaracetam": "brivaracetam",
    "carbamazepine": "carbamazepine",
    "tegretol": "carbamazepine",
    "clobazam": "clobazam",
    "frisium": "clobazam",
    "clonazepam": "clonazepam",
    "rufinamide": "rufinamide",
    "inovelon": "rufinamide",
    "ethosuximide": "ethosuximide",
    "epilim": "sodium valproate",
    "valproate": "sodium valproate",
    "sodium valproate": "sodium valproate",
    "valproic acid": "sodium valproate",
    "keppra": "levetiracetam",
    "levetiracetam": "levetiracetam",
    "lamictal": "lamotrigine",
    "lamotrigine": "lamotrigine",
    "lacosamide": "lacosamide",
    "vimpat": "lacosamide",
    "oxcarbazepine": "oxcarbazepine",
    "trileptal": "oxcarbazepine",
    "perampanel": "perampanel",
    "fycompa": "perampanel",
    "phenobarbital": "phenobarbital",
    "phenobarbitone": "phenobarbital",
    "phenytoin": "phenytoin",
    "pregabalin": "pregabalin",
    "lyrica": "pregabalin",
    "tiagabine": "tiagabine",
    "gabitril": "tiagabine",
    "topamax": "topiramate",
    "topiramate": "topiramate",
    "vigabatrin": "vigabatrin",
    "sabril": "vigabatrin",
    "zonisamide": "zonisamide",
    "zonegran": "zonisamide",
}

SEIZURE_TYPE_SYNONYMS = {
    "absence": "generalized absence seizure",
    "absence seizure": "generalized absence seizure",
    "absences": "generalized absence seizure",
    "atonic seizure": "generalized atonic seizure",
    "complex partial": "focal impaired awareness seizure",
    "complex partial seizure": "focal impaired awareness seizure",
    "focal aware": "focal aware seizure",
    "focal aware seizure": "focal aware seizure",
    "focal impaired awareness": "focal impaired awareness seizure",
    "focal impaired awareness seizure": "focal impaired awareness seizure",
    "focal seizure": "focal seizure",
    "focal seizures": "focal seizure",
    "focal to bilateral tonic clonic": "focal to bilateral tonic clonic seizure",
    "focal to bilateral tonic clonic seizure": "focal to bilateral tonic clonic seizure",
    "generalised tonic clonic": "generalized tonic clonic seizure",
    "generalised tonic clonic seizure": "generalized tonic clonic seizure",
    "generalized tonic clonic": "generalized tonic clonic seizure",
    "generalized tonic clonic seizure": "generalized tonic clonic seizure",
    "gtc": "generalized tonic clonic seizure",
    "myoclonic": "generalized myoclonic seizure",
    "myoclonic seizure": "generalized myoclonic seizure",
    "partial seizure": "focal seizure",
    "tonic clonic": "generalized tonic clonic seizure",
    "tonic clonic seizure": "generalized tonic clonic seizure",
}

DIAGNOSIS_SYNONYMS = {
    "epilepsy": "epilepsy",
    "focal epilepsy": "focal epilepsy",
    "generalised epilepsy": "generalized epilepsy",
    "generalized epilepsy": "generalized epilepsy",
    "idiopathic generalized epilepsy": "generalized epilepsy",
    "jme": "juvenile myoclonic epilepsy",
    "juvenile myoclonic epilepsy": "juvenile myoclonic epilepsy",
    "temporal lobe epilepsy": "focal epilepsy",
}


def normalize_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if text in NULL_STRINGS:
        return ""
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"[^a-z0-9./]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return "" if text in NULL_STRINGS else text


def _strip_formulation(text: str) -> str:
    return re.sub(r"\b(tablets?|tabs?|capsules?|caps?|liquid|solution|syrup|modified release|mr|xr|cr)\b", " ", text)


def canonical_medication_name(value: Any) -> str:
    text = _strip_formulation(normalize_value(value))
    text = re.sub(r"\b\d+(?:\.\d+)?\s*(?:mg|g|mcg|microgram|ml)s?\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text in ASM_SYNONYMS:
        return ASM_SYNONYMS[text]
    for synonym, canonical in sorted(ASM_SYNONYMS.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(synonym)}\b", text):
            return canonical
    return text


def normalize_unit(value: Any) -> str:
    normalized = normalize_value(value)
    mapping = {
        "g": "g",
        "gram": "g",
        "grams": "g",
        "mcg": "mcg",
        "microgram": "mcg",
        "micrograms": "mcg",
        "mg": "mg",
        "milligram": "mg",
        "milligrams": "mg",
        "mgs": "mg",
        "ml": "ml",
        "millilitre": "ml",
        "millilitres": "ml",
        "milliliter": "ml",
        "milliliters": "ml",
    }
    return mapping.get(normalized, normalized)


def normalize_dose(value: Any) -> str:
    text = normalize_value(value)
    if not text:
        return ""
    text = re.sub(r"(?<=\d)(?:mg|g|mcg|micrograms?|ml|milligrams?|grams?)\b", "", text)
    text = re.sub(r"\b(?:mg|g|mcg|micrograms?|ml|milligrams?|grams?)\b", "", text)
    text = text.replace(" ", "")
    return text


def normalize_medication_frequency(value: Any) -> str:
    normalized = normalize_value(value)
    mapping = {
        "1": "once daily",
        "once a day": "once daily",
        "once daily": "once daily",
        "od": "once daily",
        "o d": "once daily",
        "daily": "once daily",
        "nocte": "nightly",
        "night": "nightly",
        "nightly": "nightly",
        "on": "nightly",
        "2": "twice daily",
        "bd": "twice daily",
        "b d": "twice daily",
        "bid": "twice daily",
        "twice a day": "twice daily",
        "twice daily": "twice daily",
        "3": "three times daily",
        "tds": "three times daily",
        "t d s": "three times daily",
        "tid": "three times daily",
        "three times a day": "three times daily",
        "three times daily": "three times daily",
        "4": "four times daily",
        "qds": "four times daily",
        "q d s": "four times daily",
        "qid": "four times daily",
        "four times a day": "four times daily",
        "four times daily": "four times daily",
        "as required": "as required",
        "prn": "as required",
    }
    return mapping.get(normalized, normalized)


def normalize_frequency(value: Any) -> str:
    return normalize_medication_frequency(value)


def singular_unit(value: Any) -> str:
    normalized = normalize_value(value)
    if normalized.endswith("s"):
        normalized = normalized[:-1]
    return normalized


def canonical_seizure_type(value: Any) -> str:
    text = normalize_value(value).replace("generalised", "generalized")
    text = re.sub(r"\bfits?\b", "seizure", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text in SEIZURE_TYPE_SYNONYMS:
        return SEIZURE_TYPE_SYNONYMS[text]
    if "focal" in text and "bilateral" in text and "tonic clonic" in text:
        return "focal to bilateral tonic clonic seizure"
    if "complex partial" in text or ("focal" in text and "impaired awareness" in text):
        return "focal impaired awareness seizure"
    if "focal" in text or "partial" in text:
        return "focal seizure"
    if "tonic clonic" in text or "gtc" in text:
        return "generalized tonic clonic seizure"
    if "absence" in text:
        return "generalized absence seizure"
    if "myoclonic" in text:
        return "generalized myoclonic seizure"
    if text in {"seizure", "seizures"}:
        return "unknown seizure type"
    return text


def canonical_diagnosis(value: Any) -> str:
    text = normalize_value(value).replace("generalised", "generalized")
    if text in DIAGNOSIS_SYNONYMS:
        return DIAGNOSIS_SYNONYMS[text]
    if "temporal lobe" in text or "focal" in text or "partial" in text:
        return "focal epilepsy"
    if "generalized" in text or "idiopathic general" in text:
        return "generalized epilepsy"
    if "epilepsy" in text:
        return "epilepsy"
    return text


def canonical_investigation_result(value: Any) -> str:
    text = normalize_value(value)
    if not text:
        return ""
    if any(term in text for term in ["no abnormality", "no abnormalities", "unremarkable", "within normal", "nad"]):
        return "normal"
    if any(term in text for term in ["abnormal", "epileptiform", "slowing", "lesion", "sclerosis"]):
        return "abnormal"
    if "normal" in text:
        return "normal"
    if any(term in text for term in ["pending", "awaited", "requested", "planned"]):
        return "uncertain"
    return text


def normalize_temporality(value: Any, evidence_text: Any = None) -> str:
    text = " ".join(part for part in [normalize_value(value), normalize_value(evidence_text)] if part)
    if not text:
        return ""
    if any(term in text for term in ["previous", "previously", "historical", "history of", "used to", "stopped", "withdrawn"]):
        return "historical"
    if any(term in text for term in ["will start", "plan", "planned", "to commence", "increase to", "reduce to"]):
        return "planned"
    if any(term in text for term in ["current", "currently", "now", "ongoing", "continues", "taking"]):
        return "current"
    return normalize_value(value) or "uncertain"


def normalize_missingness(value: Any, evidence_text: Any = None) -> str:
    text = " ".join(part for part in [normalize_value(value), normalize_value(evidence_text)] if part)
    if not text:
        return "not_stated"
    if any(term in text for term in ["unclear", "uncertain", "possible", "probable", "?", "query"]):
        return "uncertain"
    if any(term in text for term in ["conflicting", "inconsistent"]):
        return "conflicting"
    return "present"


def _number_token(token: str) -> str:
    return NUMBER_WORDS.get(token, token)


def _range_value(first: str, second: str | None) -> str:
    first = _number_token(first)
    second = _number_token(second) if second else None
    return f"{first}-{second}" if second else first


def parse_frequency_expression(value: Any) -> dict[str, str]:
    normalized = normalize_value(value)
    normalized = normalized.replace("seizure free", "seizure-free")
    if not normalized:
        return {"count": "", "period_count": "", "period_unit": "", "class": ""}
    if any(term in normalized for term in ["seizure-free", "seizurefree", "none since", "no seizures", "free of seizures"]):
        return {"count": "0", "period_count": "", "period_unit": "", "class": "seizure_free"}
    if any(term in normalized for term in ["every few months", "few monthly", "few months"]):
        return {"count": "1", "period_count": "3", "period_unit": "month", "class": "approximate_rate"}

    single_rates = {
        "daily": ("1", "day"),
        "every day": ("1", "day"),
        "once daily": ("1", "day"),
        "weekly": ("1", "week"),
        "every week": ("1", "week"),
        "once weekly": ("1", "week"),
        "fortnightly": ("2", "week"),
        "monthly": ("1", "month"),
        "every month": ("1", "month"),
        "once monthly": ("1", "month"),
        "yearly": ("1", "year"),
        "annually": ("1", "year"),
        "every year": ("1", "year"),
        "once yearly": ("1", "year"),
    }
    if normalized in single_rates:
        period_count, period_unit = single_rates[normalized]
        return {"count": "1", "period_count": period_count, "period_unit": period_unit, "class": "rate"}

    every = re.search(
        r"\bevery\s+((?:\d+(?:\.\d+)?)|one|two|three|four|five|six|few|couple)\s+(day|week|month|year)s?\b",
        normalized,
    )
    if every:
        period_count = "3" if every.group(1) == "few" else "2" if every.group(1) == "couple" else _number_token(every.group(1))
        return {"count": "1", "period_count": period_count, "period_unit": every.group(2), "class": "approximate_rate" if every.group(1) in {"few", "couple"} else "rate"}

    per = re.search(
        r"\b((?:\d+(?:\.\d+)?)|one|two|three|four|five|six|seven|eight|nine|ten|a|an)"
        r"(?:\s*(?:to|or|-)\s*((?:\d+(?:\.\d+)?)|one|two|three|four|five|six|seven|eight|nine|ten))?"
        r"\s+(?:seizures?\s+)?(?:per|a|each|every)\s+"
        r"(?:(\d+(?:\.\d+)?)\s+)?(day|week|month|year)s?\b",
        normalized,
    )
    if per:
        return {
            "count": _range_value(per.group(1), per.group(2)),
            "period_count": per.group(3) or "1",
            "period_unit": per.group(4),
            "class": "rate",
        }

    in_period = re.search(
        r"\b((?:\d+(?:\.\d+)?)|one|two|three|four|five|six|seven|eight|nine|ten)"
        r"(?:\s*(?:to|or|-)\s*((?:\d+(?:\.\d+)?)|one|two|three|four|five|six|seven|eight|nine|ten))?"
        r"\s+(?:seizures?\s+)?(?:in|over|during|last)\s+"
        r"(?:(\d+(?:\.\d+)?)\s+)?(day|week|month|year)s?\b",
        normalized,
    )
    if in_period:
        return {
            "count": _range_value(in_period.group(1), in_period.group(2)),
            "period_count": in_period.group(3) or "1",
            "period_unit": in_period.group(4),
            "class": "rate",
        }

    bare = re.fullmatch(r"\d+(?:\.\d+)?", normalized)
    if bare:
        return {"count": normalized, "period_count": "", "period_unit": "", "class": "count_only"}

    return {"count": "", "period_count": "", "period_unit": "", "class": "unparsed"}


def frequency_parts_match(predicted: dict[str, str], gold: dict[str, str]) -> bool:
    return bool(
        predicted.get("count")
        and predicted.get("count") == gold.get("count")
        and predicted.get("period_count") == gold.get("period_count")
        and predicted.get("period_unit") == gold.get("period_unit")
    )


def normalize_medication(item: dict[str, Any]) -> dict[str, str]:
    return {
        "name": canonical_medication_name(item.get("name") or item.get("medication_name")),
        "dose": normalize_dose(item.get("dose")),
        "dose_unit": normalize_unit(item.get("dose_unit")),
        "frequency": normalize_medication_frequency(item.get("frequency")),
        "temporality": normalize_temporality(item.get("temporality"), _evidence_quote(item)),
        "missingness": normalize_missingness(item.get("missingness"), _evidence_quote(item)),
    }


def _evidence_quote(item: dict[str, Any]) -> str:
    evidence = item.get("evidence")
    if isinstance(evidence, dict):
        return str(evidence.get("quote") or "")
    if isinstance(evidence, list):
        return " ".join(str(entry.get("quote") or "") for entry in evidence if isinstance(entry, dict))
    return ""


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    function_name = case["function"]
    input_value = case.get("input")
    functions = {
        "canonical_medication_name": canonical_medication_name,
        "normalize_dose": normalize_dose,
        "normalize_unit": normalize_unit,
        "normalize_medication_frequency": normalize_medication_frequency,
        "canonical_seizure_type": canonical_seizure_type,
        "canonical_diagnosis": canonical_diagnosis,
        "canonical_investigation_result": canonical_investigation_result,
        "normalize_temporality": normalize_temporality,
        "normalize_missingness": normalize_missingness,
        "parse_frequency_expression": parse_frequency_expression,
        "normalize_medication": normalize_medication,
    }
    actual = functions[function_name](input_value)
    expected = case.get("expected")
    return {
        "id": case.get("id"),
        "function": function_name,
        "passed": actual == expected,
        "input": input_value,
        "expected": expected,
        "actual": actual,
    }


def command_check(args: argparse.Namespace) -> int:
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    results = [_run_case(case) for case in cases["cases"]]
    report = {
        "case_count": len(results),
        "passed_count": sum(1 for result in results if result["passed"]),
        "failed_count": sum(1 for result in results if not result["passed"]),
        "results": results,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['passed_count']}/{report['case_count']} normalization cases passed")
    print(f"wrote {args.output}")
    return 0 if report["failed_count"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="Run normalization fixture cases.")
    check.add_argument("--cases", default="examples/normalization_cases.json")
    check.add_argument("--output", default="runs/recovery/normalization_unit_report.json")
    check.set_defaults(func=command_check)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
