# Data Intake

Milestone 2 turns the dataset plan into an executable intake contract.

## Artifacts

- `data/manifests/dataset_manifest.json`: primary and auxiliary dataset inventory.
- `data/splits/exectv2_splits.json`: fixed ExECTv2 development, validation, and test split.
- `src/intake.py`: manifest generation, deterministic splitting, preprocessing, gold-label loading, and quote-normalization checks.

## ExECTv2 Split

The fixed split is deterministic and independent of prompt or model results:

- method: `sha256(document_id, salt)` ordering,
- salt: `exectv2-fixed-splits-v1`,
- development: 120 letters,
- validation: 40 letters,
- test: 40 letters.

The development split is for prompt and pipeline iteration. The validation split is for choosing pipeline variants. The test split should be used once for the final main comparison.

## Preprocessing

The preprocessor:

- preserves original source text,
- normalizes only repeated spaces and line endings for the model-facing normalized text,
- creates sentence-like spans with stable IDs such as `s0001`,
- records `char_start` and `char_end` offsets against the original source text.

Line boundaries are treated as meaningful because the letters contain headings, medication lists, and short clinical fragments.

## Gold Loader

The gold loader parses BRAT standoff `.ann` files:

- textbound annotations such as `T1 Diagnosis 21 73 ...`,
- attributes such as `A12 DiagCategory T1 Epilepsy`,
- source slices from the corresponding `.txt` file,
- normalized quote-match flags.

Each loaded gold annotation includes the source offset slice and the annotation attributes needed by later field-specific scorers.

## Quote Normalization

ExECTv2 annotation text frequently serializes spaces as hyphens. The intake normalizer:

- converts common curly quotes and dash variants,
- treats hyphens as whitespace for annotation-span matching,
- collapses repeated whitespace,
- lowercases for comparison.

The loader records two checks:

- `normalized_match_by_offset`: annotation text matches the source slice at the recorded offsets after normalization.
- `normalized_match_in_document`: annotation text appears somewhere in the normalized source document.

Current corpus-wide quote audit:

- documents: 200,
- annotations: 2,092,
- offset mismatches: 278,
- document mismatches: 40.

These are logged rather than repaired automatically. Offset mismatches often reflect off-by-one spans; document mismatches include apparent spelling differences or annotation typos.

## Exit Check

```bash
python3 src/intake.py check-one EA0001 --max-mismatches 10
```

This command loads one letter, preprocesses it, assigns sentence IDs and offsets, loads gold labels, and reports quote-normalization mismatches.
