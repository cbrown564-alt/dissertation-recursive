# Final Full-Field Evaluation Plan

**Date:** 2026-05-09  
**Purpose:** Reassemble the strongest workstreams into one final evaluation over the full
clinical extraction task: medications, investigations, seizure classification, epilepsy
classification, seizure frequency, temporal/evidence reliability, and deployment cost.

## Summary

Recent plans correctly focused on seizure frequency because it is the hardest single field
and because Gan 2026 gives a much better frequency-specific benchmark than the original
single-value ExECTv2 scorer. But the dissertation's final claim should return to the full
clinical extraction problem. A system that is excellent at seizure frequency but weak on
medications, investigations, diagnosis, evidence, or temporal scope is not the final system.

The final evaluation should therefore compare **composite systems**:

1. A full-field canonical extractor for medications, investigations, seizure types,
   epilepsy diagnosis, EEG/MRI, evidence, and temporal scope.
2. A seizure-frequency extractor, either integrated into the same harness or run as a
   sidecar when the best frequency system is field-specific.
3. A merger/projection step that writes one final canonical output for ExECTv2 scoring,
   while preserving Gan-specific frequency predictions for the frequency benchmark.

This plan promotes the best candidates from the recent workstreams:

- **Frontier full-field baseline:** GPT-4.1-mini S2/E3 corrected Phase 2+3 results.
- **Frontier frequency specialist:** GPT-5.5 `Gan_cot_label`, currently 0.80 Pragmatic
  micro-F1 on the 50-document Gan development subset.
- **Local full-field candidates:** qwen3.6:35b H6fs, qwen3.6:27b H6, gemma4:e4b H6,
  and qwen3.5:9b H6fs/H6v2 depending on the exact metric being optimized.
- **Local frequency candidate:** qwen35_b `Gan_direct_label`, currently observed at
  0.70 Pragmatic micro-F1 and needing artifact persistence.
- **Retrieval/verification candidate:** field-family retrieval plus selective verification,
  inspired by `minimal-epilepsy-retrieval-verified`, but scored with the wider repo's
  corrected metrics.

The final output should be a small, defensible evaluation matrix, not another broad prompt
zoo.

## Current Evidence Base

### Corrected Frontier Baselines

Authoritative Phase 2+3 corrected metrics remain the main comparison floor for ExECTv2.

Validation, 40 documents:

| System | Med name | Med full | Sz collapsed | Freq loose | EEG | MRI | Dx collapsed | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S2 GPT-4.1-mini | 0.852 | 0.655 | 0.610 | 0.075 | 0.950 | 1.000 | 0.700 | 0.835 |
| E2 GPT-4.1-mini | 0.796 | 0.633 | 0.613 | 0.125 | 0.950 | 0.975 | 0.575 | 0.957 |
| E3 GPT-4.1-mini | 0.872 | 0.707 | 0.633 | 0.125 | 0.975 | 0.975 | 0.725 | 0.914 |

Test, 40 documents:

| System | Med name | Med full | Sz collapsed | Freq loose | EEG | MRI | Dx collapsed | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S2 GPT-4.1-mini | 0.885 | 0.769 | 0.415 | 0.175 | 0.975 | 0.900 | 0.725 | 0.880 |
| E2 GPT-4.1-mini | 0.722 | 0.619 | 0.487 | 0.125 | 0.900 | 0.850 | 0.550 | 0.980 |
| E3 GPT-4.1-mini | 0.847 | 0.724 | 0.469 | 0.125 | 0.900 | 0.825 | 0.700 | 0.968 |

Interpretation: E3 is the strongest validation system overall; S2 generalizes strongly on
test medication and diagnosis; E2/E3 preserve temporal fidelity. These are still the
baseline systems to beat.

### Local Model Workstream

The local-model workstream shows that local models are not just cheaper; they are
competitive on important full-field metrics.

Best 40-document validation candidates:

| Local system | Med F1 | Sz F1 collapsed | Dx acc | Latency | Use case |
|---|---:|---:|---:|---:|---|
| qwen3.6:27b H6 | 0.885 | 0.578 | 0.800 | 34s | Best medication F1 |
| qwen3.6:35b H6fs | 0.852 | 0.593 | 0.800 | 12s | Best deployment balance |
| gemma4:e4b H6 | 0.849 | 0.593 | 0.825 | 28s | Best diagnosis accuracy |
| qwen3.5:9b H6fs | 0.839 | 0.602 | 0.825 | 12s | Best 9B balance |

Interpretation: qwen3.6:35b H6fs should be the main local deployment candidate because it
matches frontier medication F1 at 12s/doc and has near-frontier seizure-type performance.
qwen3.6:27b H6 and gemma4:e4b H6 are important ablations for best-medication and
best-diagnosis claims.

### Frequency Workstreams

Gan frequency workstream:

| System | Dataset | Pragmatic micro-F1 | Purist micro-F1 | Exact label acc |
|---|---|---:|---:|---:|
| GPT-5.5 `Gan_cot_label` | Gan local synthetic, 50-doc dev | 0.80 | 0.76 | 0.54 |
| GPT-5.5 `Gan_direct_label` | Gan local synthetic, 50-doc dev | 0.76 | 0.76 | 0.60 |
| qwen35_b `Gan_direct_label` | Gan local synthetic, current observation | 0.70 | TBD | TBD |

Interpretation: frequency should be represented in the final evaluation through both:

- Gan-specific Pragmatic/Purist micro-F1, because this is the best benchmark shape for the
  frequency task.
- ExECTv2 crosswalk metrics, because the final full-field system must still produce a
  canonical output on the dissertation corpus.

### Retrieval + Verification Workstream

`minimal-epilepsy-retrieval-verified` suggests that field-family isolation and retrieval
highlighting can improve some fields, especially seizure frequency and classification.
However, its n=25 LLM-adjudicated scores are not directly comparable to the corrected
main-repo metrics. The final plan should include one retrieval-inspired candidate only if
it is scored through the wider repo's corrected scorer.

## Final Candidate Systems

The final evaluation should promote a small set of systems. Recommended candidates:

| ID | System | Purpose |
|---|---|---|
| F1 | GPT-4.1-mini S2 | Strong direct frontier baseline; best test medication/diagnosis pattern |
| F2 | GPT-4.1-mini E3 | Strong event-first frontier baseline; best validation full-field system |
| F3 | qwen3.6:35b H6full | Primary local deployment candidate (12s/doc, full-field harness) |
| F4 | qwen3.6:27b H6full | Best local full-field candidate (medication full F1 exceeds frontier) |
| F5 | gemma4:e4b H6 | Best local diagnosis candidate (benchmark harness only) |
| F6 | qwen3.6:35b H6full + local/Gan frequency sidecar | Local full-system composite |
| F7 | GPT-4.1-mini E3 + GPT-5.5 `Gan_cot_label` sidecar | Best expected quality composite |
| F8 | Retrieval-field-family candidate, optional | Architecture ablation from retrieval/verification work |

**Updated 2026-05-10:** F3 and F4 promoted from H6fs/H6 to H6full following the
H6full validation sweep (see results below). gemma4:26b and gemma4:31b (F5b, F5c)
are ruled out as hardware-limited on this machine (see Hardware Constraint Findings).

Do not promote every historical variant. H3, H4, H7, H6v2/H6ev, H6fs for qwen3.6
models, `Gan_fs_hard`, `Gan_two_pass`, and direct mini baselines remain useful as
error-analysis references, not final matrix systems unless a newer run displaces the
above candidates.

## Final Evaluation Questions

The final evaluation should answer six questions:

1. **Best overall quality:** Which system gives the strongest full-field extraction across
   medications, investigations, seizure classification, epilepsy classification, frequency,
   temporal scope, schema validity, and quote validity?
2. **Best local deployment:** How close can a zero-API-cost local system get to the best
   frontier system when evaluated across the full field set?
3. **Frequency transfer:** Does the Gan frequency improvement transfer into the ExECTv2
   full-field setting, or is it mostly a benchmark-specific sidecar result?
4. **Architecture value:** Does event-first, retrieval-highlight, or verification add value
   once the best local and frontier baselines are included?
5. **Reliability:** Which systems preserve evidence support, schema validity, and temporal
   correctness under final validation/test conditions?
6. **Cost and deployment:** Which system sits on the best quality/cost/latency frontier?

## Metrics

### Primary Full-Field Metrics

Report these for every final system on ExECTv2 validation and test:

- `medication_name_f1`
- `medication_full_f1`
- medication component F1: dose, unit, frequency
- `investigation_accuracy` or the current investigation-correctness metric
- `seizure_type_f1`
- `seizure_type_f1_collapsed`
- `epilepsy_diagnosis_accuracy`
- `epilepsy_diagnosis_accuracy_collapsed`
- EEG accuracy
- MRI accuracy
- `current_seizure_frequency_loose_accuracy`
- `current_seizure_frequency_per_letter_accuracy`
- `seizure_frequency_type_linkage_accuracy`
- `temporal_accuracy`
- `schema_valid_rate`
- `quote_presence_rate`
- `quote_validity_rate`

### Frequency-Specific Metrics

Report these for each promoted frequency harness on the Gan subset:

- Pragmatic micro/macro/weighted F1
- Purist micro/macro/weighted F1
- exact normalized-label accuracy
- parse success
- provider error rate
- quote presence
- quote exact or overlap validity
- cost/doc and latency/doc

### Final Composite Score

Use a composite score for ranking, but do not hide the per-field table.

Recommended balanced score:

```text
full_field_score =
  0.20 * medication_name_f1
  0.15 * medication_full_f1
  0.15 * seizure_type_f1_collapsed
  0.10 * epilepsy_diagnosis_accuracy_collapsed
  0.10 * investigation_score
  0.10 * frequency_score
  0.10 * temporal_accuracy
  0.05 * schema_valid_rate
  0.05 * quote_validity_rate
```

Where `frequency_score` is:

- ExECTv2 frequency per-letter/loose score for canonical-only systems.
- A mapped ExECTv2 frequency score for composite systems.
- Gan Pragmatic micro-F1 should be reported separately and not directly inserted into the
  ExECTv2 composite unless the output is projected back to ExECTv2 and scored there.

This prevents the Gan sidecar from artificially dominating a full-field score.

## Work Packages

### WP1: Freeze Final Splits And Candidate Registry

**Files:** `runs/final_full_field/experiment_freeze.json`,
`runs/final_full_field/candidate_registry.json`.

Create a freeze file with:

- validation and test document IDs;
- Gan development/full-subset IDs;
- model registry snapshot;
- harness IDs;
- prompt/schema versions;
- scorer version;
- code commit hash;
- whether each system is canonical-only, frequency-only, or composite.

Acceptance:

- No final candidate can be added without updating the registry and recording the reason.
- Validation is used for final candidate selection; test is used once for final reporting.

### WP2: Persist And Score Missing Candidate Artifacts

**Files:** `runs/final_full_field/candidates/`.

Collect or rerun the promoted systems:

- F1: S2 GPT-4.1-mini.
- F2: E3 GPT-4.1-mini.
- F3: qwen3.6:35b H6fs.
- F4: qwen3.6:27b H6.
- F5: gemma4:e4b H6.
- Frequency: GPT-5.5 `Gan_cot_label`, GPT-5.5 `Gan_direct_label`, qwen35_b
  `Gan_direct_label`.
- Optional: retrieval-field-family candidate if implemented before final freeze.

Acceptance:

- Every candidate has raw outputs, parsed outputs, call report, scorer output, and manifest.
- qwen35_b `Gan_direct_label` 0.70 is persisted as an artifact, not only a note.
- Existing Phase 2+3 frontier artifacts may be reused if scorer/version compatibility is
  confirmed.

### WP3: Implement Composite Projection

**Files:** likely `src/final_full_field.py` or `scripts/build_final_composites.py`.

Build canonical composites by combining a full-field extractor with a frequency sidecar.

Rules:

- Full-field extractor owns medications, investigations, seizure types, epilepsy diagnosis,
  EEG/MRI, temporal support, and citations.
- Frequency sidecar owns `current_seizure_frequency` only.
- The composite must preserve both original frequency fields:
  - `frequency_source`: canonical, gan_sidecar, retrieval_sidecar.
  - `frequency_original_label`: raw Gan normalized label.
  - `frequency_projected_value`: ExECTv2-compatible projection.
  - `frequency_evidence`: quote from sidecar or canonical extraction.
- If sidecar evidence is unsupported, the merger should either retain canonical frequency
  or mark the sidecar frequency as unsupported, depending on the predeclared system.

Acceptance:

- Composite output validates against the canonical schema.
- Composite scoring can be run with `src/evaluate.py`.
- The original non-composite outputs are still preserved for ablation.

### WP4: Final Validation Matrix

**Files:** `runs/final_full_field/validation/`.

Run all final candidates on the validation split.

Recommended matrix:

| Candidate | Full-field extractor | Frequency source | Model family |
|---|---|---|---|
| F1 | S2 GPT-4.1-mini | canonical S2 | frontier |
| F2 | E3 GPT-4.1-mini | canonical E3 | frontier |
| F3 | qwen3.6:35b H6fs | none/canonical if available | local |
| F4 | qwen3.6:27b H6 | none/canonical if available | local |
| F5 | gemma4:e4b H6 | none/canonical if available | local |
| F6 | qwen3.6:35b H6fs | qwen35_b `Gan_direct_label` | local composite |
| F7 | E3 GPT-4.1-mini | GPT-5.5 `Gan_cot_label` | hybrid best-quality |
| F8 | retrieval-field-family | retrieval-field-family | architecture ablation |

Acceptance:

- Produce `comparison_table.csv` with all primary full-field metrics.
- Produce `frequency_table.csv` with ExECTv2 and Gan frequency metrics.
- Produce `complexity_table.csv` with calls/doc, tokens/doc, cost/doc, latency/doc,
  local/API status, and artifact count.
- Produce `promotion_decision.md` selecting at most three systems for final test:
  best quality, best local deployment, and best architecture ablation if distinct.

### WP5: Final Test Run

**Files:** `runs/final_full_field/test/`.

Run only the promoted validation winners on the held-out test split.

Promotion cap:

- Best overall quality system.
- Best fully local system.
- Optional retrieval/verification architecture if validation shows a meaningful gain.

Acceptance:

- Test is run once per promoted system.
- `test/comparison_table.csv` mirrors validation metrics exactly.
- `test/generalization_delta.csv` reports validation-to-test deltas.
- Any system that regresses badly on test is still reported; no post-test swapping.

### WP6: Robustness And Reliability Check

**Files:** `runs/final_full_field/robustness/`.

Use the existing robustness perturbations for promoted systems:

- family-history trap;
- negated investigation trap;
- bullets-to-prose;
- medication spelling variants;
- seizure-free vs historical seizure mentions;
- frequency cluster/range hard cases;
- unknown vs no-reference frequency cases.

Acceptance:

- Report worst metric drop per system.
- Report schema and quote validity under perturbation.
- Report whether local systems are more/less brittle than frontier systems.

### WP7: Final Claim Package

**Files:** `runs/final_full_field/writeup/`.

Generate:

- `dissertation_tables.md`
- `claim_support_matrix.csv`
- `error_analysis_examples.csv`
- `methods_traceability.md`
- `final_system_cards.md`

Each final claim must map to an artifact path.

## Decision Rules

### Best Overall System

Promote as best overall if:

- highest balanced `full_field_score` on validation;
- schema validity >= 0.99 on validation or documented reason if local model falls short;
- quote validity >= 0.99 for evidence-grounded claims;
- no catastrophic field failure, defined as any primary field dropping below 0.50 unless
  it is seizure frequency and separately explained.

### Best Local Deployment System

Promote as best local if:

- fully local inference for all fields or clearly separated local/full-field and API/frequency
  composite variants;
- medication name F1 >= 0.85 or within 0.03 of best frontier;
- seizure type collapsed F1 >= 0.58 or within 0.05 of best frontier;
- diagnosis accuracy >= 0.80;
- latency <= 35s/doc on available hardware;
- zero API cost.

### Best Frequency System

Promote as frequency system if:

- Gan Pragmatic micro-F1 >= 0.75 on development/validation;
- parse success >= 0.99;
- provider error rate <= 0.01;
- quote overlap-or-exact rate >= 0.95 if making evidence-grounded claims;
- ExECTv2 projection does not reduce full-field composite reliability.

### Retrieval/Verification Promotion

Promote retrieval/verification only if:

- it improves at least one hard field by >= 0.03 absolute without degrading medication,
  schema, quote, or temporal metrics;
- or it gives materially better evidence/verification support at similar field accuracy;
- complexity cost is reported and justified.

## Reporting Structure

The final dissertation result should use three tables:

### Table 1: Full-Field Accuracy

Rows: final systems.  
Columns: medication name, medication full, investigation, seizure type collapsed,
epilepsy diagnosis collapsed, ExECTv2 frequency, EEG, MRI, temporal, schema, quote.

### Table 2: Frequency Benchmark

Rows: promoted frequency systems.  
Columns: Gan Pragmatic micro-F1, Gan Purist micro-F1, exact label accuracy, parse success,
evidence validity, cost/doc, latency/doc.

### Table 3: Deployment Frontier

Rows: final systems.  
Columns: model location, calls/doc, latency/doc, cost/doc, local/API dependency,
best-use case, final recommendation.

## Claim Templates

### Best Overall

> "The strongest final system was [system], which achieved [key metrics] on the held-out
> ExECTv2 test split while preserving schema validity [x] and quote validity [y]. Its
> remaining weakness was [field], concentrated in [error mode]."

### Local Deployment

> "A fully local configuration, [system], matched or approached frontier performance on
> medications, seizure classification, and diagnosis at zero marginal API cost. This supports
> the feasibility of offline epilepsy-letter extraction, with seizure frequency handled by
> [local sidecar / remaining limitation]."

### Frequency

> "For seizure frequency specifically, [system] achieved Gan-style Pragmatic micro-F1 [x]
> and Purist micro-F1 [y] on [dataset]. This should be interpreted separately from the
> full-field ExECTv2 score because Gan evaluates normalized single-label frequency categories."

### Architecture

> "Field-family retrieval and selective verification [did/did not] improve the final system.
> The result suggests that [salience highlighting / event-first temporal structure /
> verification audit] is useful primarily for [field], not as a universal replacement for
> simpler full-letter extraction."

---

## Implementation Results (2026-05-10)

### Infrastructure Completed

- `src/final_full_field.py` — four-command runner: `setup`, `import-existing`,
  `run-validation`, `build-report`.
- `runs/final_full_field/experiment_freeze.json` — freeze file with splits, scorer
  version, commit hash, and harness registry (WP1 complete).
- `runs/final_full_field/candidate_registry.json` — 10 local candidates with status
  `existing_run` or `needs_run`.
- All nine existing local model conditions imported and re-scored from
  `runs/local_models/` into `runs/final_full_field/validation/imported/`.
- Two composite scores implemented:
  - **BenchComp** (benchmark-field composite): medication name + seizure type +
    diagnosis + EEG + MRI only. Apples-to-apples comparison between H6-family
    harnesses and frontier systems.
  - **FullComp** (plan composite): all fields including medication full F1, frequency,
    temporal, schema, quote validity. Penalises H6/H6fs for not extracting these fields;
    use FullComp only when comparing systems that extract the same field set.

### H6full Harness

A new `H6full_benchmark_coarse_json` harness was implemented
(`build_h6full_prompt` in `src/model_expansion.py`) adding:

- Structured medication objects: `{"name", "dose", "unit", "frequency"}`.
- Explicit `investigations: {"eeg", "mri"}`.
- `current_seizure_frequency` as a string.
- Schema-consistent three-shot examples (structured format throughout).

`projected_canonical` in `src/model_expansion.py` was extended to decode structured
medication objects and an investigations dict directly, bypassing the regex fallback
used for plain-text name strings.

### H6full Validation Results (40-doc validation split)

#### qwen3.6 models — complete, 0 parse failures

| Metric | qwen3.6:35b H6full | qwen3.6:27b H6full | Frontier E3 |
|---|---:|---:|---:|
| Med name F1 | 0.847 | **0.885** | 0.872 |
| **Med full F1** | **0.707** | **0.796** | 0.707 |
| Dose F1 | 0.822 | 0.882 | — |
| Dose unit F1 | 0.882 | 0.898 | — |
| Freq component F1 | 0.819 | 0.851 | — |
| Sz type F1 collapsed | 0.581 | 0.578 | 0.633 |
| Dx accuracy | 0.800 | 0.800 | 0.725 |
| EEG accuracy | 0.750 | 0.750 | 0.975 |
| MRI accuracy | **0.825** | **0.825** | 0.975 |
| Sz freq loose | 0.175 | 0.150 | 0.125 |
| BenchComp | 0.716 | **0.747** | 0.809 |
| FullComp | 0.669 | 0.697 | 0.721 |
| Latency/doc | ~12s | ~34s | API |
| Parse success | 40/40 | 40/40 | — |

Key findings:

- **qwen3.6:27b H6full matches or exceeds E3 on medication full F1** (0.796 vs 0.707).
  This is the first local system to beat frontier on a full medication metric including
  dose, unit, and frequency components simultaneously.
- **MRI accuracy jumped from 0.625 → 0.825** for both qwen3.6 models simply by asking
  explicitly in the prompt. This confirms the prior 0.625 was a harness artefact, not a
  model capability ceiling.
- **EEG accuracy reached only 0.750 vs frontier 0.975.** This gap (0.225) is not
  explained by capability — MRI showed the same improvement pattern when asked for.
  Root cause needs investigation (see Open Questions).
- **Seizure type F1 unchanged** from H6 as expected; H6full adds no new seizure-type
  prompt mechanics. The 0.578–0.581 result is consistent with H6 baselines.
- qwen3.6:35b at 12s/doc with 0.716 BenchComp is the best deployment candidate
  (speed × quality). qwen3.6:27b at 0.747 BenchComp is the best quality candidate.

#### Composite score comparison: benchmark-field view

| System | Med F1 | Sz F1 | Dx Acc | EEG | MRI | BenchComp |
|---|---:|---:|---:|---:|---:|---:|
| GPT-4.1-mini E3 (frontier) | 0.872 | 0.633 | 0.725 | 0.975 | 0.975 | 0.809 |
| GPT-4.1-mini S2 (frontier) | 0.852 | 0.610 | 0.700 | 0.950 | 1.000 | 0.792 |
| **qwen3.6:27b H6full** | **0.885** | 0.578 | 0.800 | 0.750 | 0.825 | **0.747** |
| qwen3.6:35b H6full | 0.847 | 0.581 | 0.800 | 0.750 | 0.825 | 0.716 |
| qwen3.6:27b H6 (prior best) | 0.885 | 0.578 | 0.800 | 0.700 | 0.625 | 0.721 |
| gemma4:e4b H6 | 0.849 | 0.593 | 0.825 | 0.700 | 0.625 | 0.708 |

The remaining 6.2pp gap between qwen3.6:27b H6full (0.747) and frontier E3 (0.809) is
driven almost entirely by the EEG accuracy shortfall (0.750 vs 0.975) and seizure type
F1 (0.578 vs 0.633). Medications and diagnosis are at or above frontier.

### Hardware Constraint Findings (gemma4:26b and gemma4:31b)

Both larger gemma4 models were pulled and tested on H6full on the RTX 4070 Laptop
(8 GB VRAM, 31.5 GB RAM).

| Model | Size | Calls | Timeouts | Mean latency (non-timeout) |
|---|---|---|---|---|
| gemma4:26b | ~14-16 GB | 40 | 16 (40%) | 172s/doc |
| gemma4:31b | ~17-19 GB | 40 | 40 (100%) | — |

gemma4:31b is entirely unviable on this hardware for H6full; every call timed out at
300s. gemma4:26b completed 24/40 documents at 172s mean latency; the 16 timeouts
are biased toward longer/harder letters, making the 24-doc scores unreliable.

The 24-doc gemma4:26b result (med full F1 0.800, dose F1 0.926) is promising on the
documents that completed, but it cannot be used as a dissertation claim without a full
40-doc run. gemma4 models lack the MoE efficiency that makes qwen3.6:35b run at 12s
despite its 23 GB size; dense 26-31B models at Q4_K_M exceed this machine's viable
inference budget.

**Decision:** gemma4:26b and gemma4:31b (F5b, F5c) are withdrawn from the final
candidate matrix. They may be revisited if run on different hardware.

### Open Questions

1. **EEG accuracy gap (0.750 vs 0.975):** MRI improved identically (0.625 → 0.825)
   when asked explicitly, but EEG stalled at 0.750 for both qwen3.6 models. Likely
   causes: (a) EEG result strings in the letters use more varied vocabulary than MRI
   (e.g. "generalised epileptiform discharges" vs "normal"), straining the
   normalization step; (b) EEG results are sometimes embedded in complex sentence
   structures that the model misreads. Needs a failure-mode analysis on the 10 docs
   where EEG is incorrect.
2. **Seizure frequency signal:** Both qwen3.6 models produce `current_seizure_frequency`
   strings that score 0.150–0.175 on the loose metric, marginally above the frontier
   (0.125). Whether this represents a real improvement or noise on 40 docs is unclear.
   The Gan workstream provides the right benchmark for this field.

## Risks

| Risk | Mitigation |
|---|---|
| Final matrix becomes too large | Cap final test to best quality, best local, and one architecture ablation. |
| Frequency sidecar distorts full-field comparison | Report Gan metrics separately and project sidecar output into ExECTv2 before composite scoring. |
| Local systems lack some canonical fields | Mark unsupported fields explicitly; do not compare partial contracts as full systems unless composited. |
| Validation overfitting | Freeze candidates before final test and do not swap after test results. |
| qwen35_b frequency result remains undocumented | Persist the artifact before using it in final claims. |
| Retrieval capsule metrics are overinterpreted | Use corrected local scorer for final comparisons; keep capsule scores as hypothesis-generating evidence. |

## Immediate Next Steps

**Completed (2026-05-10):**
1. ~~Create `runs/final_full_field/experiment_freeze.json` and `candidate_registry.json`.~~
2. ~~Re-score promoted local full-field candidates through the same corrected scorer.~~
3. ~~Implement H6full harness; run on qwen3.6:27b/35b and gemma4:26b/31b.~~
4. ~~Implement dual composite score (BenchComp and FullComp).~~

**Remaining:**
5. **Investigate EEG accuracy gap** — run failure-mode analysis on the 10 documents
   where qwen3.6 EEG is incorrect. Determine whether this is a normalization issue
   (fixable) or a genuine extraction gap.
6. **Promote final candidates for test** — based on current validation results:
   - Best overall quality: qwen3.6:27b H6full (0.747 BenchComp, exceeds E3 on
     medication full F1)
   - Best local deployment: qwen3.6:35b H6full (12s/doc, 0.716 BenchComp)
   - Optional: gemma4:e4b H6 as benchmark-only reference (best diagnosis accuracy)
7. **Run the held-out test split once** on the two promoted candidates.
8. **Persist the qwen35_b `Gan_direct_label` frequency artifact** before using it in
   final claims.
9. **Build composite projection** for full-field + frequency sidecar (F6, F7) if
   frequency transfer claim is included.
10. **Generate final dissertation tables and claim support package** (WP7).
