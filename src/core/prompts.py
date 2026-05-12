"""Prompt contracts for maintained benchmark extraction harnesses."""

from __future__ import annotations

from typing import Any

from .labels import benchmark_label_block


def h6_few_shot_examples() -> str:
    """Synthetic few-shot examples for current seizure-status edge cases."""
    return "\n".join(
        [
            "## Examples",
            "",
            "Example 1 -- patient has ongoing seizures but type is not specified in the letter:",
            'Letter excerpt: "She continues to have approximately two episodes per month. We plan to review her medication at the next visit."',
            'Output: {"medication_names":["lamotrigine"],"seizure_types":["unknown seizure type"],"epilepsy_diagnosis_type":"epilepsy"}',
            "",
            "Example 2 -- patient is currently seizure-free:",
            'Letter excerpt: "He has been completely seizure-free for the past ten months since starting levetiracetam."',
            'Output: {"medication_names":["levetiracetam"],"seizure_types":["seizure free"],"epilepsy_diagnosis_type":"juvenile myoclonic epilepsy"}',
            "",
            "Example 3 -- letter mentions past seizure type but patient is now seizure-free:",
            'Letter excerpt: "Previously had tonic clonic seizures, but has had no further events since sodium valproate was introduced two years ago."',
            'Output: {"medication_names":["sodium valproate"],"seizure_types":["seizure free"],"epilepsy_diagnosis_type":"generalized epilepsy"}',
        ]
    )


def h6full_examples() -> str:
    """Few-shot examples using structured medications and investigation fields."""
    return "\n".join(
        [
            "## Examples",
            "",
            "Example 1 -- named current seizure type, frequency stated, EEG done:",
            'Letter excerpt: "She continues to have focal impaired awareness seizures approximately twice a month. '
            'EEG showed left temporal spikes. Lamotrigine 100mg twice daily."',
            '{"medications":[{"name":"lamotrigine","dose":"100","unit":"mg","frequency":"twice daily"}],'
            '"seizure_types":["focal seizure"],"epilepsy_diagnosis_type":"focal epilepsy",'
            '"current_seizure_frequency":"2 per month","investigations":{"eeg":"abnormal","mri":null}}',
            "",
            "Example 2 -- seizures ongoing but type not specified in letter:",
            'Letter excerpt: "She continues to have approximately two episodes per month. EEG showed generalised discharges. Lamotrigine 100mg twice daily."',
            '{"medications":[{"name":"lamotrigine","dose":"100","unit":"mg","frequency":"twice daily"}],'
            '"seizure_types":["unknown seizure type"],"epilepsy_diagnosis_type":"epilepsy",'
            '"current_seizure_frequency":"2 per month","investigations":{"eeg":"abnormal","mri":null}}',
            "",
            "Example 3 -- currently seizure-free, no investigations mentioned:",
            'Letter excerpt: "He has been completely seizure-free for the past ten months since starting levetiracetam 1000mg twice daily."',
            '{"medications":[{"name":"levetiracetam","dose":"1000","unit":"mg","frequency":"twice daily"}],'
            '"seizure_types":["seizure free"],"epilepsy_diagnosis_type":"juvenile myoclonic epilepsy",'
            '"current_seizure_frequency":null,"investigations":{"eeg":null,"mri":null}}',
            "",
            "Example 4 -- letter mentions past seizure type but patient is now seizure-free:",
            'Letter excerpt: "Previously had tonic clonic seizures, but has had no further events since sodium valproate was introduced two years ago. MRI was normal."',
            '{"medications":[{"name":"sodium valproate","dose":null,"unit":null,"frequency":null}],'
            '"seizure_types":["seizure free"],"epilepsy_diagnosis_type":"generalized epilepsy",'
            '"current_seizure_frequency":null,"investigations":{"eeg":null,"mri":"normal"}}',
        ]
    )


def build_h6_prompt(document: dict[str, Any], harness_id: str) -> str:
    return "\n\n".join(
        [
            "Extract only benchmark fields from this epilepsy clinic letter.",
            "Return JSON only with this shape:",
            '{"medication_names":[],"seizure_types":[],"epilepsy_diagnosis_type":null}',
            "Medication names should include current anti-seizure medications only. Use generic drug names where possible.",
            "Seizure types must use only the allowed labels. Do not include aura, warning, symptom, medication side effect, investigation finding, or differential diagnosis labels as seizure types.",
            "Epilepsy diagnosis/type must use one allowed label or null. Do not invent a diagnosis if the letter does not support one.",
            benchmark_label_block(),
            f"## Harness\n{harness_id}",
            "## Source Letter",
            document["text"],
        ]
    )


def build_h6fs_prompt(document: dict[str, Any], harness_id: str) -> str:
    return "\n\n".join(
        [
            "Extract only benchmark fields from this epilepsy clinic letter.",
            "Return JSON only with this shape:",
            '{"medication_names":[],"seizure_types":[],"epilepsy_diagnosis_type":null}',
            "Medication names should include current anti-seizure medications only. Use generic drug names where possible.",
            "Seizure types must use only the allowed labels. Do not include aura, warning, symptom, medication side effect, investigation finding, or differential diagnosis labels as seizure types.",
            "Epilepsy diagnosis/type must use one allowed label or null. Do not invent a diagnosis if the letter does not support one.",
            benchmark_label_block(),
            h6_few_shot_examples(),
            f"## Harness\n{harness_id}",
            "## Source Letter",
            document["text"],
        ]
    )


def build_h6full_prompt(document: dict[str, Any], harness_id: str) -> str:
    schema = (
        '{"medications":[{"name":"...","dose":"...","unit":"...","frequency":"..."}],'
        '"seizure_types":[],"epilepsy_diagnosis_type":null,'
        '"current_seizure_frequency":null,'
        '"investigations":{"eeg":null,"mri":null}}'
    )
    return "\n\n".join(
        [
            "Extract clinical fields from this epilepsy clinic letter.",
            f"Return JSON only with this shape:\n{schema}",
            (
                "medications: list current anti-seizure medications only. "
                "Each entry must have a name. Include dose (number only), unit (mg/mcg/g/ml), "
                "and frequency (once daily / twice daily / three times daily / nocte / as required) "
                "if stated; use null for any component not mentioned. "
                "Use generic drug names where possible."
            ),
            (
                "Seizure types must use only the allowed labels. "
                "Include only the patient's CURRENT seizure types as documented in this letter - "
                "do not include historical seizure types that are no longer occurring. "
                "If the patient has seizures but the specific type is not described or is unclear in the letter, "
                "use 'unknown seizure type'. "
                "Do not include aura, warning, symptom, medication side effect, "
                "investigation finding, or differential diagnosis labels as seizure types."
            ),
            "Epilepsy diagnosis/type must use one allowed label or null. Do not invent a diagnosis if the letter does not support one.",
            (
                'current_seizure_frequency: copy the frequency expression from the letter as a short string '
                '(e.g. "2 per month", "daily", "every 6 weeks") or null if not stated or patient is seizure-free.'
            ),
            (
                'investigations.eeg: normalized result - use "normal", "abnormal", or null. '
                "Do not copy the raw EEG description; classify it as normal or abnormal. "
                "Same for investigations.mri."
            ),
            benchmark_label_block(),
            h6full_examples(),
            f"## Harness\n{harness_id}",
            "## Source Letter",
            document["text"],
        ]
    )
