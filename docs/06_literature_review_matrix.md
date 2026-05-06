# Literature Review Matrix

The literature review should support implementation decisions, not only provide background. Each paper should be logged against the practical question it answers.

## Review Strands

1. Epilepsy information extraction from clinic letters and electronic health records.
2. Clinical NLP for temporality, negation, uncertainty, and assertion status.
3. LLM-based clinical information extraction and structured output reliability.
4. Evidence-grounded, citation-grounded, or span-supported extraction.
5. Open/local versus closed/frontier models in clinical or privacy-sensitive settings.

## Evidence To Extract From Each Paper

- Citation.
- Dataset type and size.
- Clinical domain.
- Target fields.
- Method.
- Output representation.
- Temporality handling.
- Negation and uncertainty handling.
- Evidence span or citation handling.
- Evaluation metrics.
- Reported limitations.
- Relevance to this dissertation.

## Decision Questions

### Field Definitions

What fields did prior epilepsy NLP systems extract, and how do those definitions map onto current medication, previous medication, seizure type, seizure frequency, investigations, and diagnosis/type?

### Temporal Correctness

How have clinical NLP systems represented current, historical, planned, negated, family-history, hypothetical, and uncertain statements?

### Evidence Support

What should count as an evidence-supported extraction? Is exact quote matching enough, or should evidence support be judged semantically?

### Seizure Frequency

How should seizure frequency be normalized when letters use phrases such as "seizure-free", "weekly", "two in the last year", or "previously monthly but none since medication change"?

### Medication Status

How should current, previous, stopped, planned, increased, reduced, and declined medications be represented?

### Investigation Status

How should requested, pending, completed, normal, abnormal, and unavailable EEG/MRI results be scored?

### Structured Output Format

What evidence exists that JSON, YAML, XML, constrained decoding, or repair loops affect parseability and accuracy in clinical or extraction tasks?

### Model Family Comparison

What comparisons are clinically meaningful without turning the dissertation into a broad model leaderboard?

## Suggested Literature Table

| Citation | Domain | Data | Fields | Method | Temporality | Evidence spans | Metrics | Relevance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TBD | Epilepsy letters | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## Minimum Literature Review Output

Before implementation begins, the review should produce:

- Field-definition notes.
- Temporal-label justification.
- Evidence-support scoring criteria.
- Normalization examples for seizure frequency, medications, EEG/MRI, and diagnosis/type.
- A short rationale for the bounded model and format comparisons.
