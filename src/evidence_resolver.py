#!/usr/bin/env python3
"""Option C Hybrid Evidence Resolver — two-pass evidence grounding for local models.

Pass 2a (deterministic):
    Fuzzy / synonym-aware substring search against the source letter using the
    existing normalization tables (ASM_SYNONYMS, SEIZURE_TYPE_SYNONYMS,
    DIAGNOSIS_SYNONYMS).  Most values resolve here with zero LLM tokens.

Pass 2b (LLM fallback):
    For values with no deterministic match, a lightweight local model locates
    the shortest contiguous supporting sentence.  The prompt is strictly
    read-only: "find evidence, do not change values."

The resolver is additive: it mutates *only* the ``evidence`` arrays of a
canonical extraction produced by Pass 1 (e.g. H6fs).  It never changes
extracted values, missingness, or temporality.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from intake import normalize_quote, split_sentences
from normalization import (
    ASM_SYNONYMS,
    DIAGNOSIS_SYNONYMS,
    SEIZURE_TYPE_SYNONYMS,
    canonical_medication_name,
    canonical_seizure_type,
    canonical_diagnosis,
)
from validate_extraction import check_quote_validity, normalize_text


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResolvableValue:
    """A single value extracted by Pass 1 that needs evidence grounding."""

    path: str  # e.g. "fields.current_anti_seizure_medications[0].name"
    category: str  # medication | seizure_type | diagnosis | frequency | investigation
    value: str
    context: dict[str, Any] = field(default_factory=dict)  # e.g. dose, freq for meds


@dataclass
class ResolutionResult:
    """Outcome of the hybrid resolver for one document."""

    quote: str | None = None
    grounded_by: str = "none"  # exact | normalized | synonym | fallback | ungrounded
    confidence: str = "high"  # high | medium | low


@dataclass
class ResolverStats:
    """Aggregate statistics across a single document."""

    total_values: int = 0
    deterministic_hits: int = 0
    fallback_hits: int = 0
    ungrounded: int = 0
    fallback_tokens_in: int = 0
    fallback_tokens_out: int = 0
    latency_ms: float = 0.0

    @property
    def fallback_rate(self) -> float:
        return self.fallback_hits / self.total_values if self.total_values else 0.0

    @property
    def ungrounded_rate(self) -> float:
        return self.ungrounded / self.total_values if self.total_values else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_values": self.total_values,
            "deterministic_hits": self.deterministic_hits,
            "fallback_hits": self.fallback_hits,
            "ungrounded": self.ungrounded,
            "fallback_rate": round(self.fallback_rate, 4),
            "ungrounded_rate": round(self.ungrounded_rate, 4),
            "fallback_tokens_in": self.fallback_tokens_in,
            "fallback_tokens_out": self.fallback_tokens_out,
            "latency_ms": round(self.latency_ms, 2),
        }


# ---------------------------------------------------------------------------
# 1. Collect values from a canonical extraction
# ---------------------------------------------------------------------------

CATEGORY_MAP: dict[str, str] = {
    "current_anti_seizure_medications": "medication",
    "previous_anti_seizure_medications": "medication",
    "seizure_types": "seizure_type",
    "epilepsy_diagnosis": "diagnosis",
    "current_seizure_frequency": "frequency",
    "eeg": "investigation",
    "mri": "investigation",
}


def _collect_from_field(
    fields: dict[str, Any], key: str
) -> list[ResolvableValue]:
    """Yield resolvable values for a single top-level field."""
    category = CATEGORY_MAP.get(key, "unknown")
    value = fields.get(key)
    if value is None:
        return []

    results: list[ResolvableValue] = []

    if category == "medication":
        if not isinstance(value, list):
            return []
        for idx, med in enumerate(value):
            if not isinstance(med, dict):
                continue
            if med.get("missingness") != "present":
                continue
            name = med.get("name")
            if name:
                results.append(
                    ResolvableValue(
                        path=f"fields.{key}[{idx}].name",
                        category="medication",
                        value=str(name),
                        context={
                            "dose": med.get("dose"),
                            "dose_unit": med.get("dose_unit"),
                            "frequency": med.get("frequency"),
                            "status": med.get("status"),
                        },
                    )
                )

    elif category == "seizure_type":
        if not isinstance(value, list):
            return []
        for idx, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            if item.get("missingness") != "present":
                continue
            val = item.get("value")
            if val:
                results.append(
                    ResolvableValue(
                        path=f"fields.{key}[{idx}].value",
                        category="seizure_type",
                        value=str(val),
                    )
                )

    elif category == "diagnosis":
        if isinstance(value, dict) and value.get("missingness") == "present":
            val = value.get("value")
            if val:
                results.append(
                    ResolvableValue(
                        path=f"fields.{key}.value",
                        category="diagnosis",
                        value=str(val),
                    )
                )

    elif category == "frequency":
        if isinstance(value, dict) and value.get("missingness") == "present":
            val = value.get("value")
            if val:
                results.append(
                    ResolvableValue(
                        path=f"fields.{key}.value",
                        category="frequency",
                        value=str(val),
                    )
                )

    elif category == "investigation":
        if isinstance(value, dict) and value.get("missingness") == "present":
            for sub_key in ("status", "result"):
                sub_val = value.get(sub_key)
                if sub_val and str(sub_val).lower() not in {"not_stated", "", "null", "none"}:
                    results.append(
                        ResolvableValue(
                            path=f"fields.{key}.{sub_key}",
                            category="investigation",
                            value=str(sub_val),
                            context={"investigation_type": key.upper()},
                        )
                    )

    return results


def collect_resolvable_values(canonical: dict[str, Any]) -> list[ResolvableValue]:
    """Walk a canonical extraction and return every present value needing evidence."""
    fields = canonical.get("fields")
    if not isinstance(fields, dict):
        return []
    results: list[ResolvableValue] = []
    for key in CATEGORY_MAP:
        results.extend(_collect_from_field(fields, key))
    return results


# ---------------------------------------------------------------------------
# 2. Deterministic matching (Pass 2a)
# ---------------------------------------------------------------------------

def _source_sentences(source_text: str) -> list[tuple[str, int, int]]:
    """Return list of (normalized_sentence, char_start, char_end)."""
    spans = split_sentences(source_text)
    return [
        (normalize_quote(span.text), span.char_start, span.char_end)
        for span in spans
    ]


def _find_exact_quote(source_text: str, value: str) -> str | None:
    """Return the original-cased quote if ``value`` is an exact substring."""
    idx = source_text.lower().find(value.lower())
    if idx >= 0:
        return source_text[idx : idx + len(value)]
    return None


def _find_normalized_quote(source_text: str, value: str) -> str | None:
    """Match after normalizing both sides (smart quotes, dashes, whitespace).

    Uses a regex built from the normalized value that tolerates variable
    whitespace and common punctuation variants in the original text.
    """
    norm_value = normalize_text(value).lower()
    tokens = norm_value.split()
    if not tokens:
        return None

    # Build pattern: allow \s* between tokens, and tolerate dash/quote variants
    pattern = r"\s*".join(re.escape(tok) for tok in tokens)
    pattern = pattern.replace(r"\-", r"[\-\u2013\u2014]")
    pattern = pattern.replace(r"\'", r"['\u2018\u2019]")
    pattern = pattern.replace(r'\"', r'["\u201c\u201d]')

    match = re.search(pattern, source_text, re.IGNORECASE)
    if match:
        return match.group(0)
    return None


def _find_synonym_quote(
    source_text: str,
    value: str,
    synonym_map: dict[str, str],
    canonicalizer: Callable[[Any], str],
) -> str | None:
    """Search source for any synonym that maps to the same canonical form."""
    target_canonical = canonicalizer(value)
    if not target_canonical:
        return None

    # Build a reverse map: canonical → set of synonyms
    reverse: dict[str, set[str]] = {}
    for syn, can in synonym_map.items():
        reverse.setdefault(can, set()).add(syn)

    candidates = reverse.get(target_canonical, set())
    # Also include the canonical form itself
    candidates.add(target_canonical)

    for candidate in sorted(candidates, key=len, reverse=True):
        # Require word boundary for short candidates to avoid false positives
        pattern = re.escape(candidate)
        if len(candidate) <= 4:
            pattern = r"\b" + pattern + r"\b"
        for match in re.finditer(pattern, source_text, re.IGNORECASE):
            return match.group(0)

    return None


def _find_medication_quote(source_text: str, value: str) -> str | None:
    """Try exact, normalized, then synonym-aware matching for medications."""
    quote = _find_exact_quote(source_text, value)
    if quote:
        return quote
    quote = _find_normalized_quote(source_text, value)
    if quote:
        return quote
    return _find_synonym_quote(
        source_text, value, ASM_SYNONYMS, canonical_medication_name
    )


def _find_seizure_type_quote(source_text: str, value: str) -> str | None:
    quote = _find_exact_quote(source_text, value)
    if quote:
        return quote
    quote = _find_normalized_quote(source_text, value)
    if quote:
        return quote
    quote = _find_synonym_quote(
        source_text, value, SEIZURE_TYPE_SYNONYMS, canonical_seizure_type
    )
    if quote:
        return quote
    return _find_seizure_type_pattern_quote(source_text, value)


def _find_diagnosis_quote(source_text: str, value: str) -> str | None:
    quote = _find_exact_quote(source_text, value)
    if quote:
        return quote
    quote = _find_normalized_quote(source_text, value)
    if quote:
        return quote
    return _find_synonym_quote(
        source_text, value, DIAGNOSIS_SYNONYMS, canonical_diagnosis
    )


def _find_investigation_quote(source_text: str, value: str) -> str | None:
    """Investigations are often short (normal/abnormal/pending); be conservative."""
    quote = _find_exact_quote(source_text, value)
    if quote:
        return quote
    # For result values like "normal", look for "EEG was normal" style patterns
    norm_val = normalize_text(value).lower()
    if norm_val in {"normal", "abnormal"}:
        for pattern in (
            rf"\bEEG\s+was\s+{re.escape(value)}\b",
            rf"\bMRI\s+was\s+{re.escape(value)}\b",
            rf"\bscan\s+was\s+{re.escape(value)}\b",
            rf"\bshowed\s+{re.escape(value)}\s+findings?\b",
        ):
            match = re.search(pattern, source_text, re.IGNORECASE)
            if match:
                return match.group(0)
    return _find_normalized_quote(source_text, value)


def _find_frequency_quote(source_text: str, value: str) -> str | None:
    """Frequencies often contain numbers; try exact then normalized."""
    quote = _find_exact_quote(source_text, value)
    if quote:
        return quote
    return _find_normalized_quote(source_text, value)


# Clinical description patterns that map to canonical seizure types.
# These reduce LLM fallback by catching common phrasing the H6 model abstracts.
SEIZURE_TYPE_PATTERNS: list[tuple[str, str]] = [
    # Generalized tonic-clonic
    (r"generalised?\s+tonic[\s\-]clonic\s+(?:seizure|fit)s?", "generalized tonic clonic seizure"),
    (r"gtc\s+(?:seizure|fit)s?", "generalized tonic clonic seizure"),
    (r"tonic[\s\-]clonic\s+(?:seizure|fit)s?", "generalized tonic clonic seizure"),
    # Focal impaired awareness
    (r"complex\s+partial\s+(?:seizure|fit)s?", "focal impaired awareness seizure"),
    (r"focal\s+(?:seizure|fit)s?\s+with\s+impaired\s+awareness", "focal impaired awareness seizure"),
    (r"focal\s+(?:seizure|fit)s?\s+with\s+loss\s+of\s+awareness", "focal impaired awareness seizure"),
    (r"focal\s+onset\s+(?:\w+\s+)*?(?:seizure|fit)s?\s+with\s+impaired\s+awareness", "focal impaired awareness seizure"),
    # Focal aware
    (r"focal\s+aware\s+(?:seizure|fit)s?", "focal aware seizure"),
    (r"simple\s+partial\s+(?:seizure|fit)s?", "focal aware seizure"),
    # Focal to bilateral
    (r"focal\s+to\s+bilateral\s+tonic[\s\-]clonic\s+(?:seizure|fit)s?", "focal to bilateral tonic clonic seizure"),
    # Absence
    (r"absence\s+(?:seizure|fit)s?", "generalized absence seizure"),
    (r"typical\s+absence\s+(?:seizure|fit)s?", "generalized absence seizure"),
    # Myoclonic
    (r"myoclonic\s+(?:seizure|fit)s?", "generalized myoclonic seizure"),
    # Atonic
    (r"atonic\s+(?:seizure|fit)s?", "generalized atonic seizure"),
    # Focal onset (catches "focal onset convulsive seizure", "focal onset seizure", etc.)
    (r"focal\s+onset\s+(?:\w+\s+)*?(?:seizure|fit)s?", "focal seizure"),
    # Generic focal
    (r"focal\s+(?:seizure|fit)s?", "focal seizure"),
    (r"partial\s+(?:seizure|fit)s?", "focal seizure"),
    # Generic generalized
    (r"generalised?\s+(?:seizure|fit)s?", "generalized seizures"),
]


def _find_seizure_type_pattern_quote(source_text: str, value: str) -> str | None:
    """Match clinical descriptions that the model abstracted into canonical labels."""
    target_canonical = canonical_seizure_type(value)
    if not target_canonical:
        return None
    for pattern, mapped_canonical in SEIZURE_TYPE_PATTERNS:
        if canonical_seizure_type(mapped_canonical) != target_canonical:
            continue
        match = re.search(pattern, source_text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


# Context markers that disqualify a quote from being patient-specific evidence.
# These catch family-history traps, negated statements, and other irrelevant contexts.
INVALID_CONTEXT_MARKERS: list[tuple[str, ...]] = [
    ("family", "history"),
    ("brother", "had"),
    ("brother", "has"),
    ("mother", "had"),
    ("mother", "has"),
    ("father", "had"),
    ("father", "has"),
    ("sister", "had"),
    ("sister", "has"),
    ("no", "report", "of"),
    ("not", "available"),
]


def _quote_context_valid(quote: str) -> bool:
    """Return False if the quote contains invalid context markers."""
    lowered = quote.lower()
    for markers in INVALID_CONTEXT_MARKERS:
        if all(marker in lowered for marker in markers):
            return False
    return True


def _expand_to_sentence(source_text: str, quote: str) -> str:
    """Expand a substring to its containing sentence-like span."""
    if not quote:
        return quote
    idx = source_text.find(quote)
    if idx < 0:
        return quote
    # Simple sentence boundary heuristics
    start = idx
    while start > 0 and source_text[start - 1] not in {".\n", "!", "?", "\n"}:
        start -= 1
    end = idx + len(quote)
    while end < len(source_text) and source_text[end] not in {".\n", "!", "?", "\n"}:
        end += 1
    # Trim whitespace
    while start < end and source_text[start] in " \t":
        start += 1
    while end > start and source_text[end - 1] in " \t":
        end -= 1
    return source_text[start:end]


def deterministic_resolve(
    source_text: str, value: ResolvableValue, expand_sentence: bool = True
) -> ResolutionResult | None:
    """Attempt to locate a verbatim quote for *value* without an LLM call.

    Returns ``None`` when no deterministic match is found.
    """
    category = value.category
    raw_value = value.value

    finder: Callable[[str, str], str | None]
    if category == "medication":
        finder = _find_medication_quote
    elif category == "seizure_type":
        finder = _find_seizure_type_quote
    elif category == "diagnosis":
        finder = _find_diagnosis_quote
    elif category == "investigation":
        finder = _find_investigation_quote
    elif category == "frequency":
        finder = _find_frequency_quote
    else:
        finder = _find_exact_quote

    quote = finder(source_text, raw_value)
    if not quote:
        return None

    # Determine which matcher succeeded for telemetry
    if quote.lower() == raw_value.lower():
        grounded_by = "exact"
    elif normalize_text(quote).lower() == normalize_text(raw_value).lower():
        grounded_by = "normalized"
    else:
        grounded_by = "synonym"

    if expand_sentence:
        quote = _expand_to_sentence(source_text, quote)

    # Reject quotes from invalid contexts (family history, negated statements, etc.)
    if not _quote_context_valid(quote):
        return None

    # Limit length to avoid truncation issues on local models
    if len(quote) > 300:
        quote = quote[:300].rsplit(" ", 1)[0]

    return ResolutionResult(quote=quote, grounded_by=grounded_by, confidence="high")


# ---------------------------------------------------------------------------
# 3. LLM fallback (Pass 2b)
# ---------------------------------------------------------------------------

DEFAULT_FALLBACK_PROMPT_PATH = Path("prompts/recovery/evidence_resolver_fallback.md")


def load_fallback_prompt_template(path: Path | None = None) -> str:
    path = path or DEFAULT_FALLBACK_PROMPT_PATH
    if path.exists():
        return path.read_text(encoding="utf-8")
    # Minimal inline fallback if file is missing
    return (
        "You are an evidence locator.  Your job is to find the shortest "
        "contiguous verbatim substring from the source letter that supports "
        "each extracted value.  Do NOT change, normalise, or interpret the "
        "values.  Return strict JSON only.\n\n"
        "Source letter:\n---\n{source_text}\n---\n\n"
        "Values to ground:\n{values_json}\n\n"
        "Return JSON: {\"groundings\": [{\"path\": \"...\", \"quote\": \"...\"}]}"
    )


def build_fallback_prompt(
    source_text: str,
    unresolved: list[ResolvableValue],
    template: str | None = None,
) -> str:
    """Construct the Pass-2b fallback prompt."""
    if template is None:
        template = load_fallback_prompt_template()
    values_json = json.dumps(
        [
            {
                "path": v.path,
                "category": v.category,
                "value": v.value,
                **({"context": v.context} if v.context else {}),
            }
            for v in unresolved
        ],
        indent=2,
        ensure_ascii=False,
    )
    return template.replace("{source_text}", source_text).replace(
        "{values_json}", values_json
    )


def parse_fallback_response(text: str) -> dict[str, str]:
    """Extract {path: quote} mapping from LLM JSON response."""
    # Strip markdown fences
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {}

    results: dict[str, str] = {}
    groundings = data.get("groundings") or data.get("decisions") or []
    if isinstance(groundings, dict):
        groundings = [groundings]
    for item in groundings:
        if not isinstance(item, dict):
            continue
        path = item.get("path") or item.get("field_path")
        quote = item.get("quote") or item.get("evidence", {}).get("quote")
        if path and quote and isinstance(quote, str):
            results[path] = quote.strip()
    return results


# ---------------------------------------------------------------------------
# 4. Hybrid orchestration
# ---------------------------------------------------------------------------

ModelCall = Callable[[str], dict[str, Any]]
"""Signature: prompt_text -> {"text": str, "tokens_in": int, "tokens_out": int, "latency_ms": float}"""


def resolve_evidence_hybrid(
    canonical: dict[str, Any],
    source_text: str,
    model_call: ModelCall | None = None,
    fallback_prompt_template: str | None = None,
    expand_sentence: bool = True,
) -> tuple[dict[str, Any], ResolverStats]:
    """Run the full Option-C resolver on a single canonical extraction.

    Parameters
    ----------
    canonical:
        Pass-1 canonical extraction (e.g. from H6fs).  Will **not** be mutated;
        a deep copy is returned.
    source_text:
        Original clinic letter text.
    model_call:
        Optional callable for Pass-2b fallback.  If ``None``, unresolved values
        remain ungrounded.
    fallback_prompt_template:
        Optional override for the Pass-2b prompt template.
    expand_sentence:
        If True, deterministic matches are expanded to their containing sentence.

    Returns
    -------
    (resolved_canonical, stats)
    """
    import time

    started = time.perf_counter()
    out = copy.deepcopy(canonical)
    values = collect_resolvable_values(out)
    stats = ResolverStats(total_values=len(values))

    unresolved: list[ResolvableValue] = []
    path_to_result: dict[str, ResolutionResult] = {}

    # ---- Pass 2a: deterministic -----------------------------------------
    for value in values:
        result = deterministic_resolve(source_text, value, expand_sentence=expand_sentence)
        if result:
            path_to_result[value.path] = result
            stats.deterministic_hits += 1
        else:
            unresolved.append(value)

    # ---- Pass 2b: LLM fallback ------------------------------------------
    if unresolved and model_call is not None:
        prompt = build_fallback_prompt(
            source_text, unresolved, template=fallback_prompt_template
        )
        response = model_call(prompt)
        raw_text = response.get("text", "")
        stats.fallback_tokens_in = int(response.get("tokens_in", 0))
        stats.fallback_tokens_out = int(response.get("tokens_out", 0))

        fallback_quotes = parse_fallback_response(raw_text)
        for value in unresolved:
            quote = fallback_quotes.get(value.path)
            if quote and normalize_text(quote) in normalize_text(source_text):
                path_to_result[value.path] = ResolutionResult(
                    quote=quote, grounded_by="fallback", confidence="medium"
                )
                stats.fallback_hits += 1
            else:
                stats.ungrounded += 1
    else:
        stats.ungrounded += len(unresolved)

    # ---- Populate canonical output --------------------------------------
    for value in values:
        result = path_to_result.get(value.path)
        if result and result.quote:
            _inject_evidence(out, value.path, result.quote)

    stats.latency_ms = (time.perf_counter() - started) * 1000
    return out, stats


# ---------------------------------------------------------------------------
# 5. Canonical mutation helpers
# ---------------------------------------------------------------------------

def _inject_evidence(canonical: dict[str, Any], path: str, quote: str) -> None:
    """Insert an evidence object into the canonical structure at *path*."""
    # Expected paths:
    #   fields.current_anti_seizure_medications[0].name
    #   fields.seizure_types[0].value
    #   fields.epilepsy_diagnosis.value
    #   fields.current_seizure_frequency.value
    #   fields.eeg.status
    #   fields.mri.result
    #
    # We actually want to attach evidence to the *parent object* (the field
    # record), not to the leaf scalar.  So we mutate the parent dict's
    # ``evidence`` list.
    parts = path.split(".")
    if len(parts) < 3 or parts[0] != "fields":
        return

    # Reconstruct parent path
    leaf = parts[-1]
    parent_parts = parts[1:-1]  # e.g. ["current_anti_seizure_medications[0]"]

    parent = canonical["fields"]
    for part in parent_parts:
        match = re.fullmatch(r"(.+?)\[(\d+)\]", part)
        if match:
            key, idx = match.group(1), int(match.group(2))
            parent = parent[key][idx]
        else:
            parent = parent[part]

    if not isinstance(parent, dict):
        return

    evidence_obj = {"quote": quote, "sentence_id": None, "char_start": None, "char_end": None}

    if leaf in ("name", "value", "status", "result"):
        # Ensure evidence list exists
        if parent.get("evidence") is None:
            parent["evidence"] = []
        if isinstance(parent["evidence"], list):
            # Avoid duplicate quotes
            existing_quotes = {
                normalize_text(e.get("quote", "")) for e in parent["evidence"] if isinstance(e, dict)
            }
            if normalize_text(quote) not in existing_quotes:
                parent["evidence"].append(evidence_obj)


# ---------------------------------------------------------------------------
# 6. CLI
# ---------------------------------------------------------------------------

def _jsonify(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extraction", type=Path, help="Pass-1 canonical extraction JSON")
    parser.add_argument("--source", type=Path, required=True, help="Source clinic letter .txt")
    parser.add_argument("--output", type=Path, help="Write resolved canonical JSON to path")
    parser.add_argument("--stats", type=Path, help="Write resolver stats JSON to path")
    parser.add_argument(
        "--no-expand-sentence",
        action="store_true",
        help="Keep deterministic matches as short substrings rather than expanding to sentence.",
    )
    args = parser.parse_args()

    canonical = json.loads(args.extraction.read_text(encoding="utf-8"))
    source_text = args.source.read_text(encoding="utf-8")

    resolved, stats = resolve_evidence_hybrid(
        canonical,
        source_text,
        model_call=None,  # Stub mode: deterministic only
        expand_sentence=not args.no_expand_sentence,
    )

    # Validate quote validity
    quote_total, quote_failures = check_quote_validity(resolved, source_text)
    validity_rate = (
        (quote_total - len(quote_failures)) / quote_total if quote_total else 1.0
    )

    print(f"total_values: {stats.total_values}")
    print(f"deterministic_hits: {stats.deterministic_hits}")
    print(f"fallback_hits: {stats.fallback_hits}")
    print(f"ungrounded: {stats.ungrounded}")
    print(f"fallback_rate: {stats.fallback_rate:.4f}")
    print(f"ungrounded_rate: {stats.ungrounded_rate:.4f}")
    print(f"quote_count: {quote_total}")
    print(f"quote_validity_rate: {validity_rate:.4f}")
    if quote_failures:
        print(f"invalid_quote_paths: {quote_failures}")

    if args.output:
        args.output.write_text(_jsonify(resolved) + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    if args.stats:
        report = stats.to_dict()
        report["quote_count"] = quote_total
        report["quote_validity_rate"] = round(validity_rate, 4)
        report["invalid_quote_paths"] = quote_failures
        args.stats.write_text(_jsonify(report) + "\n", encoding="utf-8")
        print(f"wrote {args.stats}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
