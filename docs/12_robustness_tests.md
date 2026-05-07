# Robustness Tests

Milestone 6 added a perturbation harness for stress-testing S2, E2, and E3 on
modified clinic letters. Phase 7 extends the same harness into the recovery
robustness gate for comparing S2 with recovered candidates such as S4, S5, E4,
and E5.

## Scope

The robustness harness separates perturbations by expected label effect:

- `label_preserving`: the canonical ExECTv2 labels should stay the same.
- `label_changing`: the letter has been deliberately changed, so the original
  gold label is no longer a fair correctness target; these cases are reported
  for parseability, schema validity, and quote validity.
- `gan_frequency`: Gan 2026 seizure-frequency examples are used as focused
  seizure-frequency stress tests with their supplied expected frequency label.

The ExECTv2 label-preserving set currently covers:

- reordered sections,
- removed headings,
- bullet lists converted to prose,
- historical medication traps,
- planned medication traps,
- family-history seizure-frequency traps,
- negated investigation traps,
- historical seizure-free wording,
- vague seizure-frequency wording,
- mixed semiology and seizure-type wording.

The label-changing ExECTv2 set currently covers:

- a current seizure-free temporal contrast,
- a requested/pending MRI contrast.

Gan 2026 is used only for seizure-frequency robustness, not broad clinical
field scoring.

## Command

Generate a small perturbation corpus:

```bash
.venv/bin/python src/robustness.py generate \
  --split validation \
  --limit 5 \
  --include-gan \
  --gan-limit 5 \
  --output-dir runs/robustness
```

Run the selected systems over the generated corpus:

```bash
.venv/bin/python src/robustness.py run-systems \
  --provider stub \
  --systems S2 S4 \
  --output-dir runs/robustness
```

Evaluate robustness outputs:

```bash
.venv/bin/python src/robustness.py evaluate \
  --systems S2 S4 \
  --winning-system S4 \
  --clean-direct-run-dir runs/direct_baselines \
  --clean-recovery-run-dir runs/recovery/phase4_prompt_contract \
  --clean-comparison-table runs/recovery/validation_cycle_01/comparison_table.csv \
  --clean-event-run-dir runs/event_first \
  --output-dir runs/robustness
```

For real model runs, replace `--provider stub` with `--provider openai` and set
`--model` as required.

## Outputs

- `perturbation_manifest.json`: generated document IDs, source document IDs,
  perturbation type, label effect, and expected Gan seizure-frequency labels.
- `splits.json`: runner-compatible split file for the generated corpus.
- `robustness_document_scores.json`: per-document scores for label-preserving
  ExECTv2 perturbations.
- `label_preserving_degradation.csv`: field-by-field robust versus clean
  metrics by system and perturbation type.
- `label_changing_validity.json`: validity-only records for label-changing
  stress cases.
- `challenge_validity.json`: Phase 7 challenge-case bundle separating scored
  label-preserving traps from label-changing validity checks.
- `robustness_decision.md`: gate decision comparing the winning candidate with
  S2 on label-preserving degradation, with clean-validation gain available as a
  documented override.
- `gan_frequency_scores.json`: per-document Gan seizure-frequency scores.
- `gan_frequency_summary.csv`: Gan frequency accuracy by system and
  perturbation type.

Label-preserving degradation is computed against clean outputs for the original
source document IDs. If clean outputs are missing, robust metrics are still
reported and the clean/delta columns are left empty.
