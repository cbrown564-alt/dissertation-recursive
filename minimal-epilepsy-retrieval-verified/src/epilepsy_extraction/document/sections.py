from __future__ import annotations

import re
from dataclasses import dataclass


_HEADER_RE = re.compile(
    r"^(?P<header>"
    r"(?:Present|Current)?\s*Seizure\s*(?:Frequency|History)|"
    r"Current\s*Medications?|"
    r"Medications?\s*(?:and\s*Doses?)?|"
    r"Investigations?|"
    r"Assessment|"
    r"Background(?:\s*History)?|"
    r"History(?:\s*of\s*Presenting\s*Complaint)?|"
    r"Examination|"
    r"Plan|"
    r"Summary|"
    r"(?:Past\s*)?Medical\s*History|"
    r"Family\s*History|"
    r"Social\s*History"
    r")[\s:]*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class LetterSection:
    name: str
    text: str
    start: int
    end: int


def detect_sections(letter: str) -> list[LetterSection]:
    """Return sections detected in a clinic letter.

    Falls back to a single 'body' section if no headers are found.
    """
    headers = list(_HEADER_RE.finditer(letter))
    if not headers:
        return [LetterSection(name="body", text=letter.strip(), start=0, end=len(letter))]

    sections: list[LetterSection] = []

    preamble_end = headers[0].start()
    if preamble_end > 0:
        preamble = letter[:preamble_end].strip()
        if preamble:
            sections.append(LetterSection(name="preamble", text=preamble, start=0, end=preamble_end))

    for i, match in enumerate(headers):
        name = match.group("header").strip().lower()
        section_start = match.end()
        section_end = headers[i + 1].start() if i + 1 < len(headers) else len(letter)
        text = letter[section_start:section_end].strip()
        sections.append(LetterSection(name=name, text=text, start=section_start, end=section_end))

    return sections


def letter_to_sections_dict(letter: str) -> dict[str, str]:
    return {s.name: s.text for s in detect_sections(letter)}
