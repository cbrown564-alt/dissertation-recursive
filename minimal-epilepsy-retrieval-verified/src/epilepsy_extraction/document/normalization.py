from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_letter(text: str) -> str:
    return normalize_whitespace(text)
