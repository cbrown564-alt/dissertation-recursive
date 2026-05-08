from __future__ import annotations

import re
from dataclasses import dataclass

from .labels import parse_label
from .schema import EvidenceSpan, Prediction

FREQUENCY_TERMS = re.compile(
    r"\b(seizure|seizures|event|events|episode|episodes|absence|absences|cluster|clusters|fit|fits|"
    r"spell|spells|jerk|jerks|spasm|spasms|attack|attacks|tonic-clonic|convulsion|convulsions|frequency|"
    r"seizure-free|seizure free|remission|recurrence|recurrences|seizure freedom)\b",
    re.IGNORECASE,
)

NUMBER_WORDS = {
    "one": "1",
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
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "single": "1",
    "a": "1",
    "an": "1",
    "several": "multiple",
    "multiple": "multiple",
}

MONTH_INDEX = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _clean_evidence(text: str) -> str:
    return " ".join(text.strip().strip("-:;,.").split())


def _num(text: str) -> str:
    return NUMBER_WORDS.get(text.lower(), text)


def _count_text(text: str) -> str:
    parts = [part.strip() for part in re.split(r"\s+(?:to|or)\s+|-", text) if part.strip()]
    return " to ".join(_num(part) for part in parts)


def _count_value(text: str) -> float | None:
    value = _count_text(text)
    if value == "multiple":
        return None
    parts = [part.strip() for part in value.split(" to ") if part.strip()]
    try:
        values = [float(part) for part in parts]
    except ValueError:
        return None
    return sum(values) / len(values)


def _count_label(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def _singular_unit(unit: str) -> str:
    return unit.lower().rstrip("s")


@dataclass(frozen=True)
class SectionTimeline:
    candidates: list[EvidenceSpan]
    sections: dict[str, str]


class SectionTimelineAgent:
    """Segments a letter and keeps seizure-relevant evidence candidates."""

    def run(self, letter: str) -> SectionTimeline:
        sections: dict[str, list[str]] = {}
        current = "body"
        for raw_line in letter.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.endswith(":") and len(line) <= 60:
                current = line[:-1].strip().lower()
                sections.setdefault(current, [])
            else:
                sections.setdefault(current, []).append(line)

        sentence_candidates: list[EvidenceSpan] = []
        sentence_pattern = re.compile(r"[^.!?\n]+(?:[.!?]|\n|$)")
        for match in sentence_pattern.finditer(letter):
            sentence = _clean_evidence(match.group(0))
            if sentence and FREQUENCY_TERMS.search(sentence):
                sentence_candidates.append(EvidenceSpan(sentence, match.start(), match.end()))

        window_candidates: list[EvidenceSpan] = []
        for left, right in zip(sentence_candidates, sentence_candidates[1:]):
            if left.end is not None and right.start is not None and right.start - left.end <= 5:
                window_candidates.append(
                    EvidenceSpan(
                        _clean_evidence(f"{left.text} {right.text}"),
                        left.start,
                        right.end,
                        source="letter_window",
                    )
                )

        candidates = window_candidates + sentence_candidates

        for heading, lines in sections.items():
            if "seizure frequency" in heading:
                text = _clean_evidence(" ".join(lines[:2]))
                if text:
                    candidates.insert(0, EvidenceSpan(text, source=f"section:{heading}"))

        compact_sections = {key: " ".join(value) for key, value in sections.items()}
        return SectionTimeline(candidates=candidates, sections=compact_sections)


class FieldExtractorAgent:
    """A deterministic extractor used as the offline baseline agent."""

    def run(self, timeline: SectionTimeline) -> list[Prediction]:
        predictions: list[Prediction] = []
        for candidate in timeline.candidates:
            text = candidate.text
            extracted = self._extract_from_text(text)
            if extracted:
                label, reason = extracted
                parsed = parse_label(label)
                predictions.append(
                    Prediction(
                        label=label,
                        evidence=[candidate],
                        confidence=0.62,
                        analysis=reason,
                        parsed_monthly_rate=parsed.monthly_rate,
                        pragmatic_class=parsed.pragmatic_class,
                        purist_class=parsed.purist_class,
                    )
                )
        return predictions

    def _extract_from_text(self, text: str) -> tuple[str, str] | None:
        lower = (
            text.lower()
            .replace("≤", "")
            .replace("≥", "")
            .replace("≈", "")
            .replace("approximately", "")
            .replace("around", "")
        )
        count = (
            r"(?:\d+(?:\.\d+)?|one|two|twice|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|several|multiple)"
        )
        ranged_count = rf"{count}(?:\s+(?:to|or|-)\s+{count})?"
        unit = r"(?:day|days|week|weeks|month|months|year|years)"
        event_noun = (
            r"(?:drop attacks?|tonic[-‑– ]clonic seizures?|seizures?|events?|episodes?|absences?|"
            r"fits?|spells?|jerks?|spasms?|convulsions?|attacks?)"
        )
        modifiers = r"(?:[a-z]+(?:[-‑–][a-z]+)?\s+){0,8}?"

        dated = self._extract_dated_count_list(lower, count, event_noun)
        if dated:
            return dated

        no_ref = [
            "unable to quantify",
            "cannot quantify",
            "unclear frequency",
            "frequency is unclear",
            "unknown frequency",
        ]
        if any(phrase in lower for phrase in no_ref):
            return "unknown", "The candidate explicitly states that frequency cannot be quantified."

        seizure_free = re.search(
            rf"seizure[- ]free\s+for\s+(?P<value>{count}(?:\s+(?:to|-)\s+{count})?)\s+(?P<unit>{unit})",
            lower,
        )
        if seizure_free and "before" not in lower and "then" not in lower:
            value = _num(seizure_free.group("value"))
            return (
                f"seizure free for {value} {_singular_unit(seizure_free.group('unit'))}",
                "The candidate contains an explicit seizure-free duration.",
            )

        no_seizures_for = re.search(
            rf"(?:no|not\s+(?:had|experienced|having|reporting|reported|witnessed))\s+"
            rf"(?:any\s+)?"
            rf"(?:further\s+|reported\s+|witnessed\s+|recorded\s+|new\s+|recent\s+|"
            rf"additional\s+|definite\s+|documented\s+|clear\s+|identifiable\s+){{0,2}}"
            rf"(?:seizures?|events?|episodes?|fits?|spells?|convulsions?|recurrences?)\s+"
            rf"(?:reported\s+|recorded\s+|noted\s+|documented\s+|observed\s+)?"
            rf"(?:for|in|over|across)\s+(?:over\s+|at\s+least\s+|the\s+past\s+|the\s+last\s+)?"
            rf"(?P<value>{ranged_count})\s+(?P<unit>{unit})",
            lower,
        )
        if no_seizures_for and "otherwise" not in lower and "between" not in lower:
            value = _count_text(no_seizures_for.group("value"))
            return (
                f"seizure free for {value} {_singular_unit(no_seizures_for.group('unit'))}",
                "The candidate reports an absence of seizures over a stated interval.",
            )

        if re.search(
            r"seizure[- ]free\s+for\s+(?:a\s+|an\s+)?"
            r"(?:long|prolonged|sustained|extended|significant|considerable|substantial|"
            r"ongoing|extensive)"
            r"(?:[- ]term)?\s+"
            r"(?:duration|period|time|while|stretch|spell|interval|run)\b",
            lower,
        ):
            return (
                "seizure free for multiple month",
                "The candidate reports a qualitatively long seizure-free period.",
            )

        seizure_free_units = re.search(
            r"seizure[- ]free\s+for\s+"
            r"(?:a\s+|an\s+|several\s+|many\s+|multiple\s+|some\s+|numerous\s+|"
            r"countless\s+|ongoing\s+|sustained\s+|over\s+|more\s+than\s+)*"
            r"(?P<unit>months?|years?|weeks?)\b",
            lower,
        )
        if seizure_free_units:
            return (
                f"seizure free for multiple {_singular_unit(seizure_free_units.group('unit'))}",
                "The candidate reports a seizure-free interval of multiple units.",
            )

        if re.search(
            r"seizure[- ]free\s+"
            r"(?:off\s+asms?\s+|interval\s+|status\s+|episodes?\s+)?"
            r"since\b",
            lower,
        ):
            return (
                "seizure free for multiple month",
                "The candidate reports seizure freedom since a specified point in time.",
            )

        if re.search(
            r"seizure[- ]free\s+"
            r"(?:by\s+(?:patient|self|clinician|carer|caregiver)\s+report|"
            r"on\s+review|at\s+(?:today(?:'s|s)?|this)\s+(?:visit|review|appointment)|"
            r"at\s+present|at\s+this\s+time|currently|today)\b",
            lower,
        ) or re.search(
            r"\b(?:currently|remains?|is|continues\s+to\s+be)\s+seizure[- ]free\b",
            lower,
        ):
            return (
                "seizure free for multiple month",
                "The candidate reports present-tense seizure freedom.",
            )

        if re.search(
            r"(?:sustained|ongoing|maintained|achieved|durable|stable|long[- ]term)\s+"
            r"seizures?\s+freedom\b|"
            r"seizures?\s+freedom\s+(?:achieved|sustained|maintained|noted|is\s+sustained)",
            lower,
        ):
            return (
                "seizure free for multiple month",
                "The candidate reports sustained seizure freedom.",
            )

        if re.search(
            r"\b(?:in|currently\s+in|achieved|achieving|maintaining|enjoys?|sustained|ongoing)\s+"
            r"(?:a\s+)?(?:long[- ]term\s+|sustained\s+|ongoing\s+|durable\s+|stable\s+|complete\s+)?"
            r"remission\b",
            lower,
        ):
            return (
                "seizure free for multiple month",
                "The candidate reports ongoing remission.",
            )

        if re.search(
            r"(?:seizures?|events?|episodes?|attacks?|seizure\s+occurrences?)\s+"
            r"have\s+not\s+(?:been\s+)?(?:happening|occurring|occurred|recurred|recurring)",
            lower,
        ):
            return (
                "seizure free for multiple month",
                "The candidate states that seizure activity has ceased.",
            )

        absence = re.search(
            r"\b(?:no|denies|denying|without(?:\s+any)?|absence\s+of|"
            r"there\s+(?:have|has)\s+been\s+no|with\s+no|"
            r"have\s+had\s+no|has\s+had\s+no|reports?\s+no|reporting\s+no|"
            r"have\s+not\s+(?:had|been\s+having)|has\s+not\s+(?:had|been\s+having))"
            r"\s+(?:(?:further|witnessed|reported|definite|new|additional|recurrent|clear|"
            r"significant|identifiable|breakthrough|recent|documented|observed)\s+){0,3}"
            r"(?:seizures?|events?|episodes?|fits?|spells?|convulsions?|recurrences?|"
            r"breakthroughs?|attacks?|seizure\s+occurrences?)\b",
            lower,
        )
        if (
            absence
            and "otherwise" not in lower
            and "between" not in lower
            and "at the wheel" not in lower
            and "prior to" not in lower
            and "previously" not in lower
            and "for context" not in lower
        ):
            return (
                "seizure free for multiple month",
                "The candidate describes an absence of recent seizure activity.",
            )

        cluster = re.search(
            rf"cluster\s+(?:days?\s+)?(?P<clusters>{ranged_count})\s+(?:this|per|a|each|every|last)\s+"
            rf"(?P<period>{unit}).{{0,80}}?(?P<count>{count})\s+(?:seizures?|events?|episodes?|fits?)\s+"
            rf"(?:in|per|during|within)\s+(?:24\s*h|cluster|day)",
            lower,
        )
        if cluster:
            clusters = _count_text(cluster.group("clusters"))
            per_cluster = _count_text(cluster.group("count"))
            unit_text = _singular_unit(cluster.group("period"))
            return (
                f"{clusters} cluster per {unit_text}, {per_cluster} per cluster",
                "The candidate describes cluster frequency and within-cluster seizure count.",
            )

        combined_window = re.search(
            rf"(?P<count1>{ranged_count})\s+{modifiers}{event_noun}\s+(?:and|,)\s+"
            rf"(?P<count2>{ranged_count})\s+{modifiers}{event_noun}.{{0,80}}?"
            rf"(?:over|in|during|across|since)\s+(?:the\s+)?(?:last|past|previous)?\s*"
            rf"(?P<period>{count})\s+(?P<unit>{unit})",
            lower,
        )
        if combined_window:
            first = _count_value(combined_window.group("count1"))
            second = _count_value(combined_window.group("count2"))
            if first is not None and second is not None:
                total = first + second
                return (
                    f"{_count_label(total)} per {_num(combined_window.group('period'))} "
                    f"{_singular_unit(combined_window.group('unit'))}",
                    "The candidate sums multiple event counts over a shared retrospective window.",
                )

        over_window = re.search(
            rf"(?P<count>{ranged_count})\s+{modifiers}{event_noun}\s+"
            rf"(?:over|in|during|across)\s+(?:the\s+)?(?:last|past|previous)?\s*"
            rf"(?:(?P<period>{count})\s+)?(?P<unit>{unit})",
            lower,
        )
        if over_window:
            seizure_count = _count_text(over_window.group("count"))
            period = _num(over_window.group("period") or "1")
            if period == "1":
                return (
                    f"{seizure_count} per {_singular_unit(over_window.group('unit'))}",
                    "The candidate gives a count over a defined retrospective window.",
                )
            return (
                f"{seizure_count} per {period} {_singular_unit(over_window.group('unit'))}",
                "The candidate gives a count over a defined retrospective window.",
            )

        window_first = re.search(
            rf"(?:over|in|during|across)\s+(?:the\s+)?(?:last|past|previous)?\s*"
            rf"(?P<period>{count})\s+(?P<unit>{unit}).{{0,80}}?\b(?:were|was|had|reports?|recorded)\s+"
            rf"(?P<count>{ranged_count})\s+{modifiers}{event_noun}",
            lower,
        )
        if window_first:
            seizure_count = _count_text(window_first.group("count"))
            period = _num(window_first.group("period"))
            return (
                f"{seizure_count} per {period} {_singular_unit(window_first.group('unit'))}",
                "The candidate gives a count over a defined retrospective window.",
            )

        interval = re.search(
            rf"(?:inter-seizure interval|clusters?\s+every|seizures?\s+every|events?\s+every)\s+"
            rf"(?P<period>{count})\s+(?P<unit>{unit})",
            lower,
        )
        if interval:
            period = _num(interval.group("period"))
            return (
                f"1 per {period} {_singular_unit(interval.group('unit'))}",
                "The candidate gives an event interval, normalised as one event per interval.",
            )

        direct = re.search(
            rf"(?P<count>{ranged_count})\s+"
            rf"(?:times\s+)?{modifiers}(?:{event_noun})?\s*"
            rf"(?:per|a|each|every)\s+"
            rf"(?P<period>{count}\s+)?(?P<unit>{unit})",
            lower,
        )
        if direct:
            count_text = _count_text(direct.group("count"))
            period_text = (direct.group("period") or "1 ").strip()
            period_text = _num(period_text)
            if period_text == "1":
                return (
                    f"{count_text} per {_singular_unit(direct.group('unit'))}",
                    "The candidate contains a direct frequency expression.",
                )
            return (
                f"{count_text} per {period_text} {_singular_unit(direct.group('unit'))}",
                "The candidate contains a direct frequency expression.",
            )

        present = re.search(r"present seizure frequency\s*:?\s*(?P<phrase>.+)", lower)
        if present:
            phrase = present.group("phrase")
            return self._extract_from_text(phrase)

        return None

    def _extract_dated_count_list(
        self, lower: str, count: str, event_noun: str
    ) -> tuple[str, str] | None:
        if "for context" in lower and "before" in lower:
            return None

        month = "|".join(MONTH_INDEX)
        dated_count = rf"(?:{count}|single|a|an|0)"
        modifiers = r"(?:[a-z]+(?:[-‑–][a-z]+)?\s+){0,8}?"
        entries: list[tuple[int | None, float]] = []

        for match in re.finditer(
            rf"\bin\s+(?P<month>{month})\b[^.;,]{{0,100}}?"
            rf"(?P<count>{dated_count})\s+{modifiers}{event_noun}",
            lower,
        ):
            value = _count_value(match.group("count"))
            if value is not None:
                entries.append((MONTH_INDEX[match.group("month")], value))

        for match in re.finditer(
            rf"(?P<count>{dated_count})\s+{modifiers}{event_noun}[^.;,]{{0,80}}?"
            rf"(?:so far\s+)?in\s+(?P<month>{month})\b",
            lower,
        ):
            value = _count_value(match.group("count"))
            if value is not None:
                entries.append((MONTH_INDEX[match.group("month")], value))

        for match in re.finditer(
            rf"(?P<count>{dated_count})\s+in\s+(?P<month>{month})\b", lower
        ):
            value = _count_value(match.group("count"))
            if value is not None:
                entries.append((MONTH_INDEX[match.group("month")], value))

        for match in re.finditer(
            rf"this\s+month[^.;,]{{0,60}}?(?P<count>{dated_count})\s+{modifiers}{event_noun}",
            lower,
        ):
            value = _count_value(match.group("count"))
            if value is not None:
                entries.append((None, value))

        if len(entries) < 2:
            return None

        total = sum(value for _, value in entries)
        months = [month_index for month_index, _ in entries if month_index is not None]
        if months:
            period = max(months) - min(months) + 1
            if any(month_index is None for month_index, _ in entries):
                period = max(period, len(set(months)) + 1)
        else:
            period = len(entries)

        return (
            f"{_count_label(total)} per {period} month",
            "The candidate gives dated event counts that can be summed over a calendar window.",
        )


class VerificationAgent:
    """Checks support and resolves ambiguous or unsupported extraction candidates."""

    def run(self, predictions: list[Prediction], timeline: SectionTimeline) -> Prediction:
        if not predictions:
            label = "no seizure frequency reference"
            parsed = parse_label(label)
            return Prediction(
                label=label,
                evidence=[],
                confidence=0.25,
                analysis="No seizure-frequency candidate with a parseable value was found.",
                parsed_monthly_rate=parsed.monthly_rate,
                pragmatic_class=parsed.pragmatic_class,
                purist_class=parsed.purist_class,
                warnings=["no_supported_candidate"],
            )

        scored = sorted(predictions, key=self._score, reverse=True)
        best = scored[0]
        evidence_text = best.evidence[0].text.lower() if best.evidence else ""
        confidence = best.confidence
        warnings = list(best.warnings)
        if "present seizure frequency" in evidence_text:
            confidence += 0.18
        if any(word in evidence_text for word in ["over", "per", "seizure free", "cluster"]):
            confidence += 0.1
        if len(scored) > 1 and scored[1].label != best.label:
            warnings.append("competing_candidate")
            confidence -= 0.08

        return Prediction(
            label=best.label,
            evidence=best.evidence,
            confidence=max(0.0, min(confidence, 0.95)),
            analysis=best.analysis,
            parsed_monthly_rate=best.parsed_monthly_rate,
            pragmatic_class=best.pragmatic_class,
            purist_class=best.purist_class,
            warnings=warnings,
            metadata={"candidate_count": len(predictions)},
        )

    def _score(self, prediction: Prediction) -> tuple[float, int]:
        evidence = prediction.evidence[0].text.lower() if prediction.evidence else ""
        priority = 0
        if "present seizure frequency" in evidence:
            priority += 4
        if "over" in evidence or "per" in evidence:
            priority += 2
        month_mentions = sum(1 for month in MONTH_INDEX if re.search(rf"\b{month}\b", evidence))
        if month_mentions >= 2:
            priority += 3
        if "cluster" in evidence:
            priority += 1
        if prediction.label.startswith("seizure free for multiple"):
            priority -= 3
        return (prediction.confidence, priority)


class MultiAgentPipeline:
    def __init__(self) -> None:
        self.timeline_agent = SectionTimelineAgent()
        self.extractor_agent = FieldExtractorAgent()
        self.verification_agent = VerificationAgent()

    def predict(self, letter: str) -> Prediction:
        timeline = self.timeline_agent.run(letter)
        candidates = self.extractor_agent.run(timeline)
        prediction = self.verification_agent.run(candidates, timeline)
        return prediction


class SinglePassBaseline:
    """Simpler baseline: scan the whole letter and return the first parseable pattern."""

    def __init__(self) -> None:
        self.extractor = FieldExtractorAgent()

    def predict(self, letter: str) -> Prediction:
        timeline = SectionTimeline(candidates=[EvidenceSpan(_clean_evidence(letter[:3000]))], sections={})
        predictions = self.extractor.run(timeline)
        if predictions:
            return predictions[0]
        parsed = parse_label("no seizure frequency reference")
        return Prediction(
            label="no seizure frequency reference",
            evidence=[],
            confidence=0.2,
            analysis="Single-pass baseline found no parseable expression.",
            parsed_monthly_rate=parsed.monthly_rate,
            pragmatic_class=parsed.pragmatic_class,
            purist_class=parsed.purist_class,
            warnings=["no_supported_candidate"],
        )
