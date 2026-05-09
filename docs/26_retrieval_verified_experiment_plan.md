# Retrieval + Verification Experiment Plan

**Date:** 2026-05-09  
**Purpose:** Use `minimal-epilepsy-retrieval-verified` as a source of new experiments
for the wider repo, while preserving the wider repo's stronger evaluation discipline,
local-model workstream, and Gan seizure-frequency progress.

## Summary

`minimal-epilepsy-retrieval-verified` is useful because it isolates a different
architectural claim from the main dissertation repo: field-family retrieval plus
small, focused extractor calls can outperform broad canonical extraction on some
hard fields, and an additional verification pass can improve supported classification
signals even when it is too expensive for default deployment.

Its canonical n=25 GPT-5.5 results are:

| System | SF | Med | Inv | Seizure class | Epilepsy class | Calls/letter | Cost/letter | Latency/letter |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GPT-5.5 retrieval | 68.0 | 100.0 | 98.4 | 98.7 | 66.7 | 5 | $0.061 | 38.4s |
| GPT-5.5 verified | 45.8 | 100.0 | 98.4 | 99.0 | 84.2 | 6 | $0.100 | 74.1s |

The wider repo has now moved beyond the older "frequency is unsolved" state. The Gan
workstream has prompt-only frequency systems with much stronger pragmatic scores:
G2 `gpt_5_5` + `Gan_cot_label` reaches Pragmatic micro-F1 0.80, and the current local
qwen35_b `Gan_direct_label` observation is Pragmatic micro-F1 0.70. That changes the role
of the retrieval capsule: it should not replace the Gan workstream, but it should provide
the next experimental layer for deciding when retrieval, field-family specialization, and
verification are worth their extra calls.

## Current Starting Point

Already implemented in the wider repo:

- `src/gan_frequency.py` supports `Gan_direct_label`, `Gan_cot_label`,
  `Gan_evidence_label`, `Gan_two_pass`, `Gan_fs_hard`, `Gan_h013_direct`,
  `Gan_h013_evidence_first`, `Gan_h008_guarded`, and `Gan_g3_qwen`.
- `src/gan_frequency.py` now records the parser contract and evidence quality metrics
  for new evaluations.
- G2 and G3 Gan artifacts exist under `runs/gan_frequency/`.
- G2 best checked-in result: `gpt_5_5` + `Gan_cot_label`, Pragmatic micro-F1 0.80,
  Purist micro-F1 0.76, exact label accuracy 0.54 on 50 Gan documents.
- G3 hard-case few-shot did not beat the G2 carry-forward winner.
- Local-model workstream recommends qwen3.6:35b/H6fs for wider extraction, and the
  current qwen35_b `Gan_direct_label` observation gives a local frequency baseline of
  Pragmatic micro-F1 0.70.

Already implemented in the retrieval capsule:

- `retrieval_field_extractors`: one call per core field family after candidate-span
  selection, followed by deterministic aggregation.
- `clines_epilepsy_verified`: chunked field-family extraction, deterministic checks,
  aggregation, then provider-backed verification as an audit artifact.
- Replay files for deterministic reproduction of the leading GPT-5.5 runs.
- Compact field-level, budget, and complexity tables for cross-architecture comparison.

Important caveat:

The capsule's scores are not directly comparable to the main repo's corrected validation
and test metrics. The capsule uses n=25 and LLM-as-judge/auto-adjudicated field-family
accuracy; the main repo uses larger validation/test splits, deterministic corrected
scorers where possible, and explicit quote/schema/temporal reliability metrics. The plan
below therefore uses the capsule to generate hypotheses and experiments, not to declare
a new winner by table-matching.

## Lessons To Port

1. **Field-family isolation beats broad extraction for some fields.** The retrieval
   harness wins on seizure frequency and maintains near-ceiling medication,
   investigation, and seizure-classification scores.

2. **Retrieval should be a recall aid, not a hard context bottleneck.** The capsule's
   retrieval harness includes both retrieved context and the full letter. The experiment
   to port is "highlighted full-letter extraction", not "throw away most of the letter".

3. **Verification is most useful for classification and support claims.** The verified
   harness loses seizure-frequency accuracy but improves epilepsy classification. That
   suggests using verification selectively, especially for epilepsy type/syndrome and
   supported classification claims.

4. **Complexity accounting belongs in the primary comparison.** Calls/letter, tokens,
   latency, modules invoked, intermediate artifacts, and verifier passes are part of the
   result, not metadata to add later.

5. **Replayable provider streams are worth copying.** The retrieval capsule's replay
   mode makes regression checks and dissertation reproducibility much cleaner than live
   provider-only artifacts.

## Work Packages

### WP1: Persist The Current qwen35_b Gan Baseline

**Files:** `runs/gan_frequency/`, `docs/21_seizure_frequency_workstream.md`.

Before launching new retrieval experiments, save the qwen35_b `Gan_direct_label` result
as a first-class artifact.

Expected artifact shape:

```text
runs/gan_frequency/stage_g3_qwen35_direct/
  call_report.csv
  gan_frequency_evaluation.json
  gan_frequency_predictions_scored.csv
  predictions.json
  claim_note.md
```

Acceptance:

- `claim_note.md` states the observed Pragmatic micro-F1 0.70, Purist micro-F1,
  exact label accuracy, parse success, provider error rate, evidence quality, document
  count, model registry id, and command used.
- `docs/21_seizure_frequency_workstream.md` distinguishes checked-in artifacts from
  ad hoc local observations.
- Future plans compare against the persisted qwen35_b baseline, not a remembered result.

### WP2: Add Retrieval-Highlighted Gan Harnesses

**Files:** `src/gan_frequency.py`, tests under `tests/`, artifacts under
`runs/gan_frequency/stage_g4_retrieval/`.

Add two Gan harnesses inspired by `retrieval_field_extractors`:

- `Gan_retrieval_highlight`: retrieve candidate seizure-frequency spans with a small
  keyword/regex selector, then pass both retrieved spans and full letter to a single
  strict label-plus-quote call.
- `Gan_retrieval_only_ablation`: pass only retrieved spans, with full-letter fallback
  if no spans are found. This is an ablation, not the expected production winner.

Acceptance:

- Stub predict works for both harnesses:

```bash
python src/gan_frequency.py predict \
  --stub-calls \
  --limit 2 \
  --harness Gan_retrieval_highlight \
  --evaluate \
  --output-dir runs/gan_frequency/stage_g4_retrieval/stub_highlight
```

- Real smoke works on 10 documents for qwen35_b and the current GPT-5.5/Gan winner.
- Evaluation includes Pragmatic/Purist micro-F1, exact label accuracy, parse success,
  provider error rate, calls/doc, cost/doc, latency/doc, and evidence quality.
- Retrieval artifacts include selected spans, offsets when available, fallback status,
  and sparse-context warnings.

### WP3: Add Field-Family Retrieval Harness For Canonical ExECTv2 Fields

**Files:** likely `src/model_expansion.py`, `src/event_first.py`, or a new focused module
depending on current ownership; results under `runs/retrieval_verified/`.

Port the capsule's field-family idea into the main canonical evaluation:

- One extractor call for seizure frequency.
- One extractor call for medications.
- One extractor call for investigations.
- One extractor call for seizure classification.
- One extractor call for epilepsy classification.
- Deterministic aggregation into the canonical schema.

The key implementation detail is the same as the capsule: each call receives retrieved
field-family context plus the full letter. This should be tested against a retrieval-only
ablation, but the production candidate should preserve full-letter context.

Acceptance:

- Run on the 40-document validation split with the corrected scorer.
- Report the same core table as Phase 3: medication name/full/component F1, seizure type
  strict/collapsed, current seizure frequency metrics, EEG/MRI, epilepsy diagnosis strict
  and collapsed, temporal accuracy, schema validity, quote validity.
- Add a complexity table with calls/doc, tokens/doc, latency/doc, cost/doc, modules
  invoked, and intermediate artifacts.
- Compare against S2, E2, E3 corrected validation/test numbers, not against the capsule's
  n=25 table alone.

### WP4: Selective Verification, Not Blanket Verification

**Files:** new or existing verification module, `src/evaluate.py` only if metrics are
missing, artifacts under `runs/retrieval_verified/verification_ablation/`.

The capsule's verified harness improves epilepsy classification but hurts seizure
frequency and doubles latency. Port it as selective verification:

- `Verify_classification_only`: verify epilepsy type/syndrome and seizure classification.
- `Verify_evidence_only`: verify quote support without changing field values.
- `Verify_repair_ablation`: allow the verifier to propose corrected values, but keep
  those values separate from the original extraction for scoring.

Acceptance:

- Verification artifacts are stored separately from canonical predictions.
- Tables report original score, verified-support score, and repair-applied score.
- No dissertation claim says "verification improves extraction" unless the repair-applied
  condition is explicitly scored and wins.
- If verification is audit-only, the claim is limited to support/reliability.

### WP5: Replay Provider Streams For New Runs

**Files:** `src/model_providers.py` or a small replay provider wrapper; run artifacts.

Copy the capsule's replay discipline into the wider repo for selected expensive runs.

Acceptance:

- Each promoted condition can be replayed without external API calls.
- Replay captures raw response text, parsed payload, usage, latency, provider/model id,
  prompt id, schema id, and code version.
- A smoke test verifies that replayed predictions exactly match the original scored
  predictions for at least one Gan condition and one canonical retrieval condition.

### WP6: Retrieval Capsule Cross-Scoring

**Files:** adapter script under `scripts/` or `src/`, artifacts under
`runs/retrieval_verified/capsule_cross_score/`.

Build a small adapter that maps capsule run records into the wider repo's scoring format
where possible. The goal is not perfect comparability; it is to identify which headline
gains survive under local deterministic scoring.

Acceptance:

- For the n=25 capsule row set, produce a cross-score table with:
  - Gan-style seizure-frequency label metrics where labels are compatible.
  - Main-repo corrected medication and seizure-type metrics where schema mapping is clean.
  - Evidence support/quote validity where quotes are present.
  - A "not comparable" column for fields that cannot be fairly mapped.
- The report explicitly separates LLM-as-judge field-family accuracy from deterministic
  corrected scoring.

### WP7: Stage G4/G5 Decision Sequence

Use the current Gan result hierarchy as the spine:

1. Persist qwen35_b `Gan_direct_label` at Pragmatic micro-F1 0.70.
2. Run `Gan_retrieval_highlight` and `Gan_retrieval_only_ablation` on the same 50-doc
   subset used by G2/G3.
3. Compare against:
   - `gpt_5_5` + `Gan_cot_label`: 0.80 Pragmatic.
   - `gpt_5_5` + `Gan_direct_label`: 0.76 Pragmatic.
   - qwen35_b + `Gan_direct_label`: 0.70 Pragmatic.
4. Promote only if one of these is true:
   - Retrieval raises qwen35_b by at least +0.05 without hurting parse/evidence quality.
   - Retrieval raises the GPT-5.5 winner above 0.85 Pragmatic.
   - Retrieval gives similar label score with materially better quote/evidence support.
5. If no retrieval condition wins, keep retrieval as a negative/ablation result and move
   effort to scaling the current qwen/GPT label harnesses.

Command shape:

```bash
python src/gan_frequency.py sweep \
  --models qwen_35b_local gpt_5_5 \
  --harnesses Gan_direct_label Gan_cot_label Gan_retrieval_highlight Gan_retrieval_only_ablation \
  --limit 50 \
  --output-dir runs/gan_frequency/stage_g4_retrieval
```

Then:

```bash
python src/gan_frequency.py errors \
  --condition-dir runs/gan_frequency/stage_g4_retrieval/<best_condition> \
  --output-dir runs/gan_frequency/stage_g4_retrieval/error_audit
```

## Result Interpretation Rules

- If retrieval-highlight improves qwen35_b from 0.70 to >=0.75 Pragmatic micro-F1, claim
  that retrieval guidance makes local open-weight deployment competitive with the earlier
  frontier prompt-only threshold.
- If retrieval-highlight improves GPT-5.5 from 0.80 to >=0.85, claim prompt-only plus
  field-specific retrieval reaches the Gan-style target on the local synthetic subset.
- If retrieval-only underperforms retrieval-highlight, use that as evidence that retrieved
  spans are useful as salience cues but not sufficient context.
- If verification improves epilepsy classification but not frequency, treat it as a
  classification-support tool, not a frequency solution.
- Do not compare the capsule's n=25 LLM-adjudicated percentages directly to corrected
  validation/test F1. Use cross-scoring or clearly label the comparison as architectural.

## Risks

| Risk | Mitigation |
|---|---|
| Retrieval drops recall by omitting decisive context | Make retrieval-highlight the primary condition and retrieval-only an ablation. |
| qwen35_b result is not reproducible | Persist the exact run artifacts before building on it. |
| Verification artifacts are mistaken for corrected predictions | Store audit-only and repair-applied outputs separately and score both explicitly. |
| New harnesses duplicate already-implemented h013 prompts | Restrict this plan to retrieval-highlight, retrieval-only ablation, canonical field-family extraction, selective verification, and replay. |
| LLM-as-judge capsule scores inflate apparent gains | Cross-score capsule outputs with deterministic local metrics before making dissertation claims. |
| Extra calls make the method too slow | Complexity tables are promotion gates, not supporting detail. |

## Immediate Next Steps

1. Save the current qwen35_b `Gan_direct_label` result as `stage_g3_qwen35_direct`.
2. Add `Gan_retrieval_highlight` and `Gan_retrieval_only_ablation` to `src/gan_frequency.py`.
3. Add stub and parser/evidence smoke tests for both new harnesses.
4. Run a 10-doc real smoke on qwen35_b and GPT-5.5.
5. Run the 50-doc Stage G4 retrieval sweep.
6. Generate error audit for the best retrieval condition and the current qwen35_b baseline.
7. Decide whether retrieval earns promotion to a 150/1500-doc Gan run.
8. In parallel, design the canonical ExECTv2 field-family retrieval harness and selective
   verification ablation for the 40-doc validation split.
