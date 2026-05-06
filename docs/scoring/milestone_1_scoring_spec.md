# Milestone 1 Scoring Specification

This document pins down the first executable scoring contract. It is intentionally small: enough to validate a manually written extraction and score the evidence and field layers without committing to every final benchmark detail.

## Scope

Primary quantitative scoring is limited to ExECTv2-native fields:

- current anti-seizure medication name, dose, unit, and frequency,
- current seizure frequency,
- seizure type,
- EEG result,
- MRI result,
- epilepsy diagnosis/type.

Medication statuses beyond current and investigation statuses beyond completed-result evidence are extension outputs unless manually adjudicated.

## Evidence Layers

Each present field is scored across five layers:

- `quote_presence`: the field has at least one non-empty evidence quote.
- `quote_validity`: each quoted string appears in the source letter after normalization.
- `semantic_support`: the quote supports the extracted value.
- `temporal_support`: the quote supports the extracted temporality or status.
- `field_correctness`: the normalized extracted value matches the gold or manual expectation.

The first two layers are executable in the Milestone 1 script. The remaining three layers are represented by explicit examples and by manually supplied field expectations.

## Quote Normalization

For Milestone 1 validation, quote matching normalizes:

- repeated whitespace to a single space,
- leading and trailing whitespace,
- Unicode curly quotes to straight quotes,
- common dash variants to `-`.

This is deliberately conservative. ExECTv2 `.ann` span text sometimes uses hyphenated placeholders for spaces, but model evidence should quote the source letter text rather than the `.ann` serialization.

## Examples

### Correct Evidence And Field

Source quote:

```text
Current antiepileptic medication: lamotrigine 75 mg twice a day
```

Extraction:

```json
{
  "name": "lamotrigine",
  "dose": "75",
  "dose_unit": "mg",
  "frequency": "twice a day",
  "status": "current",
  "temporality": "current"
}
```

Scoring:

- `quote_presence`: pass.
- `quote_validity`: pass.
- `semantic_support`: pass, because the quote states the medication and dose.
- `temporal_support`: pass, because the section says `Current`.
- `field_correctness`: pass if the gold medication is lamotrigine 75 mg with current dosing.

### Valid Quote But Bad Temporal Support

Source quote:

```text
I suggest that he increases the lamotrigine slowly by 25 mg every fortnight
```

Extraction:

```json
{
  "name": "lamotrigine",
  "dose": "100 mg",
  "status": "current",
  "temporality": "current"
}
```

Scoring:

- `quote_presence`: pass.
- `quote_validity`: pass.
- `semantic_support`: partial or fail, depending on the asserted target dose.
- `temporal_support`: fail for current status, because the quote describes a planned increase.
- `field_correctness`: fail for current dose unless the resulting current dose is explicitly stated elsewhere.

### Absent Field

If the source letter does not state EEG result:

```json
{
  "status": "not_stated",
  "result": "not_stated",
  "missingness": "not_stated",
  "temporality": "uncertain",
  "evidence": null
}
```

Scoring:

- `quote_presence`: not applicable.
- `quote_validity`: not applicable.
- `semantic_support`: not applicable.
- `temporal_support`: not applicable.
- `field_correctness`: pass if the gold labels do not include an EEG result.

## Exit Criterion

Milestone 1 is complete when this command succeeds:

```bash
python3 src/validate_extraction.py \
  examples/sample_canonical_extraction.json \
  --source "data/ExECT 2 (2025)/Gold1-200_corrected_spelling/EA0001.txt" \
  --expectations examples/sample_scoring_expectations.json
```
