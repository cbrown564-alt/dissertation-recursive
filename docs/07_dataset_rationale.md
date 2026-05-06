# Dataset Rationale

This project evaluates whether event-first, evidence-grounded extraction improves structured information extraction from epilepsy clinic letters. The primary evaluation therefore needs source text, gold labels, and evidence spans that are reproducible and aligned with the target fields.

## Primary Dataset: ExECTv2 Synthetic Corpus

Location: `data/ExECT 2 (2025)/`

Use: primary benchmark for quantitative evaluation.

The ExECTv2 data is the main evaluation dataset because it provides 200 public synthetic epilepsy clinic letters with span-level gold annotations and annotation guidance. Its native labels cover the core fields needed for the dissertation:

- current anti-seizure medication name, dose, dose unit, and dosing frequency,
- seizure frequency with counts, ranges, temporal units, and seizure-free statements,
- seizure type and epilepsy diagnosis/type,
- EEG and MRI result where stated,
- supporting clinical history and timing entities useful for event extraction and error analysis.

Primary scoring should remain limited to ExECTv2-native labels. This keeps the main direct-versus-event-first comparison reproducible and avoids treating unsupported extension labels as gold standard.

## Auxiliary Dataset: Gan 2026 Synthetic Seizure-Frequency Data

Location: `data/Gan (2026)/`

Use: seizure-frequency development, stress testing, and robustness analysis.

The Gan dataset contains 1,500 synthetic clinic letters focused on seizure-frequency extraction. It is valuable because it has richer and longer frequency narratives, normalized frequency labels, rationales, and evidence strings. It includes explicit rates, ranges, cluster patterns, seizure-free intervals, unknown frequency, and no-reference cases.

This dataset should not be used as the primary benchmark for the full dissertation field set because it is narrower than ExECTv2. Its main role is to strengthen seizure-frequency normalization, robustness tests, and error analysis.

## Extension And Challenge Sets

Some clinically useful distinctions are not natively captured by ExECTv2, including:

- previous, stopped, declined, planned, increased, or reduced medication status,
- requested, pending, unavailable, or planned EEG/MRI status.

These may be evaluated only in manually adjudicated challenge sets or perturbation experiments. They should be reported separately from the primary ExECTv2-native accuracy results.

## Practical Implications

The primary claim should be:

> On ExECTv2-native fields, event-first evidence-grounded extraction improves or does not improve reliability compared with direct evidence-grounded extraction.

The extension claim, if evaluated, should be weaker:

> On manually adjudicated challenge cases, event-first extraction may help with broader temporal and status distinctions not covered by ExECTv2.
