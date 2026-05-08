# Minimal Frequency Port Implementation Plan

**Date:** 2026-05-08  
**Purpose:** Port the focused seizure-frequency lessons from `minimal-epilepsy-extraction`
into the wider repo's Gan G2/G3 seizure-frequency workstream without losing the wider
repo's evaluation discipline.

## Summary

The minimal repo's strongest frequency result is `h013_production_multi_agent_llm` on
GPT-5.5: n=50, invalid-output rate 0.0, Gan-style Pragmatic micro-F1 0.68, Purist
micro-F1 0.64, exact label accuracy 0.34, and 15 percent monthly-rate tolerance accuracy
0.54. The useful lesson is not that the full h013 broader-field pipeline should be copied
wholesale. It is that seizure frequency performs better when it is isolated as a
full-letter task with a narrow output contract, evidence anchoring, deterministic label
normalization, and a fallback/error-review path.

The wider repo already has the right destination: `src/gan_frequency.py` implements Gan
gold audit, prediction, evaluation, and model x harness sweeps. This plan adds the missing
minimal-repo lessons to that workstream and defines the G2/G3 execution sequence.

## Current Starting Point

Already implemented in the wider repo:

- `src/gan_frequency.py audit` locks the Gan local synthetic subset distribution.
- `src/gan_frequency.py predict` runs single-condition frequency prediction.
- `src/gan_frequency.py sweep` runs model x harness comparisons.
- Existing harnesses: `Gan_direct_label`, `Gan_cot_label`, `Gan_evidence_label`,
  `Gan_two_pass`, `Gan_fs_hard`.
- Current primary metric: Gan Pragmatic micro-F1.
- Current target: Pragmatic micro-F1 >= 0.85, interpreted as a synthetic-subset
  comparison rather than a direct replication of Gan's real-letter test result.

Lessons to port from the minimal repo:

- Use a dedicated full-letter seizure-frequency call rather than embedding frequency inside
  a broad canonical schema.
- Preserve a strict JSON contract with one normalized label plus evidence.
- Treat evidence extraction and label normalization as separable roles when needed.
- Keep unknown/no-reference/seizure-free distinctions explicit.
- Log raw prompts/responses and parse failures for adjudication.
- Compare GPT-5.5 against local qwen-family models because the minimal repo's h013/h008
  contrast shows the closed/frontier and local/open conditions answer different questions.

## Implementation Work Packages

### WP1: Add Minimal-Inspired Harness IDs

**Files:** `src/gan_frequency.py`, tests under `tests/` if present or a new smoke test file.

Add three harnesses to `GAN_HARNESSES`:

- `Gan_h013_direct`: single full-letter call, h013-inspired. It should use the same narrow
  label-plus-evidence contract as the current direct harness, but with stronger language
  from the minimal contract: frequency is a separate role, use full-letter context, prefer
  current clinically relevant frequency, and do not infer a numeric rate from vague text.
- `Gan_h013_evidence_first`: two-stage h013-inspired pipeline. Pass 1 quotes candidate
  frequency evidence; pass 2 normalizes only from those quotes.
- `Gan_h008_guarded`: single full-letter guarded local-model harness. It should be short
  and JSON-only, with explicit guards for `unknown`, `no seizure frequency reference`,
  seizure-free statements, ranges, and cluster labels.

Acceptance:

- `python src/gan_frequency.py predict --stub-calls --limit 2 --harness Gan_h013_direct --evaluate`
  writes predictions, call report, and evaluation files.
- The same smoke command passes for `Gan_h013_evidence_first` and `Gan_h008_guarded`.
- Existing harnesses remain runnable.

### WP2: Align Label Parsing With the Minimal Parser

**Files:** `src/gan_frequency.py`; optionally shared helper in `src/normalization.py` later.

The wider parser currently uses `MULTIPLE_VALUE = 2.0`; the minimal parser uses
`MULTIPLE_VALUE = 3.0` and supports ranges with either `to` or `-`. Decide and document the
Gan-specific convention before running G2. The recommended approach is:

- Keep the current Gan evaluator unchanged for comparability with existing audit artifacts.
- Add an explicit `parser_contract` field to `gan_frequency_evaluation.json` containing:
  `multiple_value`, `unknown_x`, supported label forms, and category thresholds.
- Add parser unit cases for:
  - `3 to 4 per month`
  - `3-4 per month`
  - `2 cluster per month, 6 per cluster`
  - `seizure free for 12 month`
  - `seizure free for multiple month`
  - `unknown`
  - `no seizure frequency reference`

Acceptance:

- Parser contract appears in all new Gan evaluation JSON.
- Unit or smoke tests verify the above labels map to expected Pragmatic/Purist classes.

### WP3: Add Evidence Quality Audit

**Files:** `src/gan_frequency.py`.

Current Gan evaluation scores labels but does not score quote validity. Add a lightweight
evidence audit using the source text in each `GanExample`.

For each row in `call_report.csv`, compute:

- `quote_present`: quote is non-empty.
- `quote_exact_in_text`: normalized quote is a substring of the source letter.
- `quote_overlap_4gram`: quote has at least one 4-token overlap with the source letter.
- `evidence_valid`: exact or overlap.

Then aggregate into `gan_frequency_evaluation.json`:

- `quote_presence_rate`
- `quote_exact_rate`
- `quote_overlap_or_exact_rate`

Acceptance:

- G2 comparison table includes quote/evidence rates.
- Promotion decisions include both label performance and evidence quality.
- Evidence metrics do not block label-only baselines, but any dissertation-facing
  evidence-grounded claim must report them.

### WP4: Make G2 a Minimal-vs-Wider Sweep

**Files:** `docs/21_seizure_frequency_workstream.md` after implementation, run artifacts.

Run G2 as a direct comparison between existing wider-repo harnesses and minimal-inspired
harnesses.

Models:

- `gpt_4_1_mini_baseline`: cost-effective wider-repo baseline.
- `gpt_5_5`: minimal repo's strongest h013 model.
- `qwen_35b_local`: recommended local deployment model from the local-model workstream.
- Optional if available: `qwen_4b_local` or the exact `qwen3.5:4b` model used by h008,
  as a small local comparison.

Harnesses:

- Existing: `Gan_direct_label`, `Gan_evidence_label`, `Gan_two_pass`, `Gan_fs_hard`.
- New: `Gan_h013_direct`, `Gan_h013_evidence_first`, `Gan_h008_guarded`.

Command shape:

```bash
python src/gan_frequency.py sweep \
  --models gpt_4_1_mini_baseline gpt_5_5 qwen_35b_local \
  --harnesses Gan_direct_label Gan_evidence_label Gan_two_pass Gan_fs_hard Gan_h013_direct Gan_h013_evidence_first Gan_h008_guarded \
  --limit 150 \
  --output-dir runs/gan_frequency/stage_g2_minimal_port
```

Acceptance:

- `runs/gan_frequency/stage_g2_minimal_port/comparison_table.csv` ranks all conditions.
- `promotion_decision.md` names the best condition and whether it passes the 0.75
  Pragmatic micro-F1 promotion gate.
- The comparison table includes cost/doc, calls/doc, parse success, evidence quality,
  exact label accuracy, Purist micro-F1, and Pragmatic micro-F1.

### WP5: G3 Hard-Case Development From G2 Errors

**Files:** `src/gan_frequency.py`; new artifacts under `runs/gan_frequency/stage_g3_minimal_port/`.

After G2, generate error buckets from `gan_frequency_predictions_scored.csv` and
`call_report.csv`:

- gold `NS` predicted `UNK` or `frequent`
- gold `UNK` predicted numeric or `NS`
- infrequent/frequent threshold flips
- cluster labels collapsed to plain rates
- ranges normalized to a single value incorrectly
- no-reference confused with unknown
- quote missing or unsupported

Add a new helper command if useful:

```bash
python src/gan_frequency.py errors \
  --condition-dir runs/gan_frequency/stage_g2_minimal_port/<best_condition> \
  --output-dir runs/gan_frequency/stage_g3_minimal_port/error_audit
```

Then create one or two G3 prompt variants, not a wide prompt zoo:

- `Gan_h013_hardcases`: h013 direct plus only the top five observed hard-case examples.
- `Gan_h013_evidence_hardcases`: evidence-first plus the same hard-case normalization rules.

Acceptance:

- Error audit identifies top confusion pairs and at least five representative rows.
- G3 variants are justified by observed G2 failures, not speculative prompt additions.
- G3 comparison table shows whether each variant improved Pragmatic micro-F1 without
  worsening evidence validity or parse success.

### WP6: Promotion to G4 Full-Subset Run

Promote one condition to the full 1,500-example local Gan subset when:

- Pragmatic micro-F1 >= 0.75 on G2/G3 development subset.
- Parse success >= 0.99.
- Provider error rate <= 0.01.
- If making an evidence-grounded claim: quote overlap-or-exact rate >= 0.95.
- Cost and latency are acceptable for 1,500 examples.

Command shape:

```bash
python src/gan_frequency.py predict \
  --model <promoted_model> \
  --harness <promoted_harness> \
  --output-dir runs/gan_frequency/stage_g4_minimal_port/<condition> \
  --evaluate
```

Acceptance:

- `stage_g4_minimal_port/<condition>/gan_frequency_evaluation.json` is complete.
- `comparison_vs_minimal_h013.md` reports:
  - minimal h013 n=50 Pragmatic/Purist/exact/tolerance results;
  - G2/G3 development result;
  - G4 full-subset result;
  - caveats about synthetic subset versus Gan real-letter target.

## Result Interpretation Rules

Use these rules when writing the dissertation-facing result:

- If G4 Pragmatic micro-F1 >= 0.85: claim the system reaches the Gan-style synthetic
  benchmark target, with the caveat that Gan's published 0.847/0.858 result was on an
  independent real-letter test set.
- If G4 Pragmatic micro-F1 is 0.75-0.84: claim substantial benchmark alignment but not parity
  with Gan's fine-tuned real-letter result.
- If G4 Pragmatic micro-F1 < 0.75: claim that prompt-only frequency extraction remains
  insufficient, and use the error audit to argue for fine-tuning, stronger normalization,
  or a better evidence-first pipeline.
- Do not compare ExECTv2 `current_seizure_frequency_loose_accuracy` directly to Gan
  Pragmatic micro-F1. Use ExECTv2 only as a crosswalk after the Gan result is locked.

## Risks

| Risk | Mitigation |
|---|---|
| Minimal h013 gains do not transfer from n=50 to 150/1500 | Keep h013 as a baseline comparison, not a promised ceiling. |
| GPT-5.5 improves label score but is not cost-effective | Report cost/doc and compare against GPT-4.1-mini and qwen local conditions. |
| Local models fail strict JSON schema | Keep `Gan_h008_guarded` short and use existing Ollama JSON-mode fallback. |
| Evidence-first improves auditability but hurts label F1 | Promote based on the intended claim: label-only benchmark vs evidence-grounded reliability. |
| Parser convention changes alter historical scores | Freeze parser contract in evaluation JSON before real G2 runs. |

## Immediate Next Steps

1. Patch `src/gan_frequency.py` with the three minimal-inspired harnesses.
2. Add parser contract output and evidence-quality audit.
3. Run stub smoke tests for every Gan harness.
4. Run a tiny real smoke, 5 documents x 2 models x 2 harnesses, to catch provider issues.
5. Run G2 minimal-port sweep on 150 documents.
6. Generate G2 error audit and implement only the top one or two G3 variants.
7. Promote one condition to G4 full-subset evaluation.

