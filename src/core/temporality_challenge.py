"""Build temporality-focused challenge slices from ExECT-style letters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChallengePattern:
    category: str
    pattern: re.Pattern[str]


TEMPORALITY_PATTERNS = [
    ChallengePattern("planned_medication", re.compile(r"\b(?:to start|start(?:ing)?|commence|commencing|suggest(?:ed)? that (?:he|she|they) starts?)\b.{0,80}\b(?:levetiracetam|lamotrigine|carbamazepine|valproate|lacosamide|topiramate|zonisamide|clobazam|brivaracetam|perampanel)\b", re.IGNORECASE)),
    ChallengePattern("previous_medication", re.compile(r"\b(?:previously|formerly|in the past|prior(?:ly)?|used to be)\b.{0,80}\b(?:on|taking|treated with)?\s*(?:levetiracetam|lamotrigine|carbamazepine|valproate|lacosamide|topiramate|zonisamide|clobazam|brivaracetam|perampanel)\b", re.IGNORECASE)),
    ChallengePattern("taper_or_stop", re.compile(r"\b(?:reduce|reducing|taper|tapering|wean|weaning|withdraw|withdrawing|stop|stopping|discontinue|discontinuing)\b.{0,80}\b(?:levetiracetam|lamotrigine|carbamazepine|valproate|lacosamide|topiramate|zonisamide|clobazam|brivaracetam|perampanel|medication|dose)\b", re.IGNORECASE)),
    ChallengePattern("dose_escalation", re.compile(r"\b(?:increase|increasing|escalate|escalating|titrate|titrating|target dose|up to)\b.{0,80}\b(?:levetiracetam|lamotrigine|carbamazepine|valproate|lacosamide|topiramate|zonisamide|clobazam|brivaracetam|perampanel|mg|dose)\b", re.IGNORECASE)),
    ChallengePattern("prn_medication", re.compile(r"\b(?:PRN|as required|when required|rescue medication|rescue therapy)\b", re.IGNORECASE)),
    ChallengePattern("split_dose", re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml)\b.{0,60}\b(?:morning|am)\b.{0,80}\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml)\b.{0,60}\b(?:night|evening|pm|nocte)\b", re.IGNORECASE)),
    ChallengePattern("seizure_free_historical_type", re.compile(r"\b(?:previously|formerly|in the past|history of|had)\b.{0,100}\b(?:focal|tonic clonic|absence|myoclonic|generalized|generalised)\b.{0,140}\b(?:seizure free|seizure-free|no further|no seizures|free of seizures)\b|\b(?:seizure free|seizure-free|no further|no seizures|free of seizures)\b.{0,140}\b(?:previously|formerly|in the past|history of|had)\b.{0,100}\b(?:focal|tonic clonic|absence|myoclonic|generalized|generalised)\b", re.IGNORECASE)),
]


def snippet(text: str, start: int, end: int, window: int = 140) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    return re.sub(r"\s+", " ", text[left:right]).strip()


def temporality_matches(document_id: str, text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for challenge in TEMPORALITY_PATTERNS:
        for match in challenge.pattern.finditer(text):
            key = (challenge.category, match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "document_id": document_id,
                    "category": challenge.category,
                    "char_start": match.start(),
                    "char_end": match.end(),
                    "matched_text": re.sub(r"\s+", " ", match.group(0)).strip(),
                    "snippet": snippet(text, match.start(), match.end()),
                }
            )
    return sorted(rows, key=lambda row: (row["document_id"], row["category"], row["char_start"]))


def summarize_temporality_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    categories = sorted({row["category"] for row in rows})
    documents = sorted({row["document_id"] for row in rows})
    return {
        "documents_with_matches": len(documents),
        "match_count": len(rows),
        "categories": {
            category: {
                "matches": sum(1 for row in rows if row["category"] == category),
                "documents": len({row["document_id"] for row in rows if row["category"] == category}),
            }
            for category in categories
        },
    }
