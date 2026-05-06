# Evaluation Harness

Milestone 5 adds a reproducible scorer for canonical outputs from S2, E2, and
E3. Milestone 7 also reuses the same scorer for S3 YAML-to-JSON artifacts in
the controlled format comparison.

## Scope

The first executable harness scores existing run artifacts against ExECTv2 gold
labels. It reports field correctness, quote presence, quote validity,
evidence-overlap support, temporal support heuristics, and cost/latency fields
when they are present in metadata.

Gold labels are loaded from:

- `MarkupPrescriptions.csv` for current medication name/dose/unit/frequency,
- `MarkupSeizureFrequency.csv` for seizure-frequency value and seizure-type
  linkage,
- `MarkupInvestigations.csv` for EEG/MRI normal or abnormal results,
- `MarkupDiagnosis.csv` for affirmed epilepsy diagnosis/type,
- BRAT `.ann` spans for evidence-overlap checks.

The scorer keeps these layers separate. Quote validity only checks whether an
evidence quote appears in the source letter; semantic support is approximated
by overlap with a relevant gold span; field correctness is scored from
normalized field values.

## Command

```bash
.venv/bin/python src/evaluate.py run \
  --split validation \
  --systems S2 E2 E3 \
  --direct-run-dir runs/direct_baselines \
  --event-run-dir runs/event_first \
  --output-dir runs/evaluation
```

For a quick mechanical check against stub outputs:

```bash
.venv/bin/python src/evaluate.py run \
  --split development \
  --limit 2 \
  --systems E2 E3 \
  --event-run-dir runs/milestone_4_stub_check_venv_2 \
  --output-dir runs/milestone_5_stub_eval
```

## Outputs

- `evaluation_summary.json`: aggregate metrics by system.
- `document_scores.json`: per-document field, evidence, temporal, and
  cost/latency scores.
- `comparison_table.csv`: compact S2 versus E2/E3 table for reporting.

The harness scores missing outputs as unavailable rather than silently
dropping expected validation documents. `S3` is accepted as a direct-run system
for secondary format analyses; it is not part of the primary S2 versus E2/E3
comparison unless explicitly requested.
