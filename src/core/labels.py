"""Shared benchmark label contracts used by prompt builders and scorers."""

from __future__ import annotations

BENCHMARK_SEIZURE_LABELS = [
    "focal seizure",
    "secondary generalized seizures",
    "generalized tonic clonic seizure",
    "generalized absence seizure",
    "generalized myoclonic seizure",
    "generalized seizures",
    "convulsive seizure",
    "cluster of seizures",
    "seizure free",
    "unknown seizure type",
]

BENCHMARK_EPILEPSY_LABELS = [
    "epilepsy",
    "focal epilepsy",
    "generalized epilepsy",
    "juvenile myoclonic epilepsy",
    "status epilepticus",
]


def benchmark_label_block() -> str:
    return "\n".join(
        [
            "Allowed seizure_type labels:",
            *[f"- {label}" for label in BENCHMARK_SEIZURE_LABELS],
            "",
            "Allowed epilepsy_diagnosis_type labels:",
            *[f"- {label}" for label in BENCHMARK_EPILEPSY_LABELS],
        ]
    )

