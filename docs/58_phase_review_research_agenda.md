# Phase Review Research Agenda

**Date:** 2026-05-13  
**Status:** Working planning note; implementation started  
**Purpose:** Capture post-synthesis concerns and convert them into a sharper research agenda for the next experimental pass.

**Implementation tracker:** The first implementation slice is documented in
[`docs/59_final_clarification_implementation.md`](59_final_clarification_implementation.md).
Implemented support now covers sanitized prompt variants, prompt artefact
auditing, projection delta reporting, temporality challenge-set construction,
and a machine-readable final clarification matrix skeleton.

---

## 1. Core Reframing

The current phase reports are useful, but the synthesis risks becoming too tidy. The next stage should stop asking only "which harness won?" and instead ask:

> Which extraction task benefits from which intervention, under which model, with which scorer assumptions?

Medication name extraction, medication tuple parsing, seizure-type abstention, diagnosis granularity, and frequency normalization are different tasks. They should not be collapsed into a single architecture story too early.

The dissertation's strongest next move is a controlled final clarification study that separates:

- raw model capability from deterministic projection and normalization;
- benchmark compliance from clinical usefulness;
- extraction failure from scorer or gold-standard mismatch;
- simple fields from reasoning-intensive fields;
- evidence validity from evidence support.

---

## 2. Immediate Concerns From Phase Review

### 2.1 Decomposed vs single-pass remains under-answered

The existing results do not yet cleanly answer whether decomposed harnesses are better than single-pass extraction. S2, E3, H6, H7, D3, and MA_v1 differ across too many axes at once:

- prompt wording;
- output schema;
- evidence requirements;
- number of calls;
- model;
- projection path;
- scoring assumptions;
- development vs validation sample size.

The result is suggestive rather than definitive. A clean factorial comparison is needed.

### 2.2 Prompt artefacts need sanitizing and testing

Some prompts expose internal implementation language to the model, including `pipeline_id`, "benchmark", "Pass 1 of 2", and "nearest allowed benchmark label". These may be harmless for schema compliance but could bias model behaviour toward scorer-shaped answers rather than clinically natural extraction.

Required action:

- create sanitized clinician-facing variants of the final prompts; **implemented
  for maintained H6-family prompt builders via `prompt_style="clinician"` in
  `src/core/prompts.py`;**
- A/B test internal-labelled prompts against sanitized prompts;
- report whether prompt artefacts materially affect extraction quality, temporality, abstention, evidence, or latency.

Implemented support:

- `scripts/audit_prompt_artifacts.py` audits tracked internal prompt artefacts.
- `src/local_models.py` now accepts `--prompt-style internal|clinician` for
  supported H6-family local-model runs.
- `runs/prompt_artifact_audit/prompt_artifacts.json` contains an initial
  EA0001 audit: internal prompts expose harness identity and benchmark language;
  clinician variants expose zero tracked artefacts under the current rules.

### 2.3 Projection and normalization are experimental actors

`projected_canonical()` is not neutral glue. It maps relaxed outputs into canonical form, canonicalizes seizure labels, force-sets projected medications and seizure fields to current, and can drop fields without evidence.

This is useful engineering, but results should be described as model + projection policy where relevant.

Required action:

- report raw-output metrics where possible;
- report projected-output metrics separately; **projection delta reporting
  implemented as an audit surface;**
- document which claims depend on deterministic post-processing; **initial
  retrospective projection-delta report generated;**
- add ablations for projection policy choices that may bias results.

Implemented support:

- `src/core/projection_diagnostics.py` compares parsed raw model payloads with
  `canonical_projection.json` outputs.
- `scripts/build_projection_delta_report.py` builds row-level and summary
  projection delta reports for existing run directories.
- `src/core/raw_output_scoring.py` and
  `scripts/build_raw_output_score_report.py` now provide direct raw-payload
  metrics for fields that can be scored before canonical projection.
- Initial retrospective run on `runs/final_full_field/validation/calls`
  compared 104 documents and found 24 dropped fields, 352 force-current
  assignments, 5 seizure-label changed documents, and 22 investigation-label
  changed documents.

### 2.4 Temporality remains a core clinical failure mode

Planned vs current medication, historical seizure type vs current seizure-free status, prior ASM exposure, medication tapering, and future dose escalation are still not cleanly solved.

This should become a named evaluation slice rather than a miscellaneous limitation.

Examples to target:

- "to start levetiracetam";
- "suggest that he starts";
- "previously on carbamazepine";
- "reduce and stop";
- "increase to target dose";
- "seizure free, previously had focal impaired awareness seizures".

Implemented support:

- `src/core/temporality_challenge.py` defines temporality trigger patterns for
  planned medication, previous medication, taper/stop, dose escalation, PRN,
  split-dose schedules, and seizure-free with historical seizure type.
- `scripts/build_temporality_challenge_set.py` builds a reusable CSV/JSON/MD
  challenge slice from ExECTv2 splits.
- Initial validation-split run found 53 temporality matches across 28 documents:
  22 dose-escalation, 14 planned-medication, 4 previous-medication, 3 split-dose,
  and 10 taper/stop matches.

### 2.5 Unknown seizure type is an abstention problem

`unknown seizure type` is not just another label. It is an abstention decision. Current F1 scoring hides whether the model was:

- reasonably over-specific;
- unsupported and overconfident;
- correctly abstaining;
- incorrectly abstaining;
- following clinical context but violating annotation convention.

The next evaluation should score abstention explicitly.

### 2.6 Evidence validity is not evidence support

Quote validity proves that a quote exists in the letter. It does not prove that the quote supports the extracted claim.

Future evidence scoring should distinguish:

- quote exists;
- quote supports the claim;
- quote is merely co-located with the claim;
- quote contradicts the claim;
- quote is ambiguous.

This matters especially for current/planned medication and historical/current seizure type errors.

Implemented support:

- `src/core/evidence_support.py` defines rule-assisted per-claim evidence
  support categories separate from quote validity: supported, co-located,
  contradicts gold, ambiguous, invalid quote, and no quote.
- `src/core/scoring.py` now includes an `evidence_support` block in each
  document score and aggregate `evidence_support_rate` /
  `evidence_support_decidable_rate` fields in summary rows.
- The current implementation is intentionally conservative: support requires a
  valid quote, overlap with relevant gold evidence, and field correctness under
  the existing scorer. Ambiguous cases remain visible when the gold annotations
  do not provide an adjudicable evidence span.

---

## 3. Proposed Final Harness Clarification Study

### 3.1 Aim

Run a controlled 40-document minimum study that clarifies which architecture actually helps which field.

### 3.2 Candidate models

Use a small, stable set:

- GPT-5.5 for reasoning-intensive fields, especially frequency;
- GPT-5.4-mini;
- GPT-4.1-mini;
- Gemini 3 Flash, rerun now that quota issues are fixed;
- qwen3.6:27b;
- qwen3.6:35b;
- gemma4:e4b as a contrasting local family.

### 3.3 Candidate harnesses

Compare architecture families under stable scoring:

- single-pass canonical with evidence;
- single-pass benchmark-only;
- single-pass benchmark-only plus evidence fields;
- extract-then-normalize;
- candidate-plus-verifier;
- retrieval-highlight;
- evidence-later resolver;
- local evidence-in-prompt vs deterministic evidence resolver;
- clinical-guideline prompt variants.

### 3.4 Required controls

For each condition, record:

- raw model output score; **implemented for directly mappable raw payload
  fields;**
- projected canonical score;
- quote validity;
- evidence support score; **implemented as a rule-assisted scoring layer
  separate from quote validity;**
- schema validity;
- parse success;
- latency;
- input/output tokens;
- deterministic post-processing applied; **projection delta reporting now records
  field drops/additions, label changes, evidence/quote counts, and force-current
  assignments;**
- cost;
- failure category counts.

### 3.5 Minimum reporting slices

Report aggregate metrics, but also named hard slices:

- planned medication; **challenge-set trigger implemented;**
- previous medication; **challenge-set trigger implemented;**
- split-dose prescription; **challenge-set trigger implemented;**
- PRN/as-required medication;
- seizure-free with historical seizure type; **challenge-set trigger implemented;**
- unknown seizure type;
- fine-grained vs collapsed seizure type;
- diagnosis granularity;
- multiple seizure-frequency mentions;
- conflicting or ambiguous gold labels.

Matrix support:

- `configs/final_clarification_matrix.yaml` now names model groups, harness
  groups, prompt styles, projection policies, evaluation slices, and required
  outputs, including raw-output score rows and summaries.
- `scripts/describe_final_clarification_matrix.py` summarizes the matrix. The
  current full-factorial skeleton contains 168 conditions.
- A pragmatic 40-document down-selection is now encoded as `selected_run_plan`:
  19 selected conditions, 760 document-runs, 1080 estimated model calls, and an
  estimated API spend of USD 8.5768 before local runtime costs.
- `scripts/run_final_clarification_conditions.py` materializes and optionally
  runs selected conditions from the plan. FC19 has been launched successfully on
  the 40-document validation split: all 40 GPT-4.1-mini H6fs clinician-prompt
  calls succeeded and parsed.

---

## 4. Field-Specific Research Questions

### 4.1 Medication name extraction

Medication name extraction appears comparatively easy. The key questions are:

- Is remaining error mostly normalization, spelling, or true extraction failure?
- Do local models already reach the practical ceiling?
- Does evidence requirement harm or help name extraction?
- Are brand/generic and misspelling normalizations reasonable, or do they obscure model differences?

### 4.2 Medication full tuple

Medication tuple extraction remains partly unsolved because dose, unit, frequency, PRN status, split-dose schedules, and planned/current status interact.

Questions:

- Should split-dose prescriptions be represented as one structured object with dose schedule, rather than duplicated tuples?
- Should PRN be a frequency, a modifier, or both?
- Does asking for richer medication subfields improve temporal classification by forcing cleaner separation?
- How much of medication_full_f1 loss is clinically meaningful vs schema mismatch?

### 4.3 Seizure type

The current "normalization problem, not model problem" claim is probably too blunt.

Questions:

- When models disagree with `unknown seizure type`, are they overconfident or clinically reasonable?
- Should evaluation separately score fine-grained ILAE labels and collapsed Fang-style categories?
- What taxonomy did Fang use, exactly, and how comparable is it to ExECTv2?
- Does requiring evidence reduce over-specific seizure-type inference?
- Do structured subfields for semiology, seizure status, and seizure type improve performance?

### 4.4 Diagnosis

Diagnosis granularity is currently too blunt.

Questions:

- Should diagnosis be scored at multiple levels: epilepsy present, broad type, syndrome, aetiology, localization?
- How should ExECTv2 CUIPhrase mappings be used rather than collapsed away?
- When a model outputs a more specific diagnosis, is that clinically useful even if benchmark-noncompliant?

### 4.5 Seizure frequency

Frequency normalization is the best example of a reasoning-intensive structured extraction task.

Questions:

- Why does GPT-5.5 outperform smaller models here?
- Is the gap due to arithmetic, temporality, contradiction handling, cluster interpretation, or abstention?
- Is the Gan pragmatic 4-class taxonomy clinically useful enough?
- Would an intermediate class structure be more meaningful than the current purist/pragmatic split?
- Can retrieval-highlight transfer to ExECTv2 frequency, medication, and seizure-type tasks?

---

## 5. Cross-Cutting Evaluation Metrics

F1 remains necessary, but the next stage should add explicit error metrics.

Recommended error categories:

- unsupported extraction;
- missed stated fact;
- temporal misclassification;
- planned-as-current;
- historical-as-current;
- current-as-historical;
- medication tuple component error;
- split-dose representation mismatch;
- PRN representation mismatch;
- label granularity mismatch;
- normalization mismatch;
- abstention error;
- unsupported inference;
- contradiction not flagged;
- evidence quote invalid;
- evidence quote valid but non-supporting;
- gold ambiguity or suspected gold error.

These should be counted per model and harness so that architectural trade-offs are visible.

---

## 6. Clinical Use-Case Profiles

The project has optimized heavily for existing benchmark metrics. That is appropriate for dissertation validity, but deployment use cases need different outputs.

Potential profiles:

- **Billing / registry profile:** concise structured codes and normalized labels.
- **Clinical review profile:** structured fields plus prose caveats and evidence.
- **Research cohorting profile:** high recall, explicit uncertainty, granular labels, adjudication flags.
- **Trial safety profile:** conservative extraction, contradiction detection, stronger evidence support.
- **Offline hospital deployment profile:** local model, minimal infrastructure, deterministic evidence resolver.

Future experiments should ask which harness works best for each profile, rather than assuming one universal best output.

---

## 7. Clinical Guidelines as a Prompt Variable

Clinical guidelines should become a modular experimental component, not just prose in prompts.

Candidate modules:

- ILAE seizure classification guidance;
- medication temporality rules;
- current vs planned ASM rules;
- seizure-free and historical seizure-type rules;
- frequency normalization rules;
- uncertainty and abstention rules.

Experiment variants:

- no guideline;
- compact guideline;
- detailed guideline;
- retrieved guideline snippet;
- guideline plus examples;
- guideline plus evidence-support requirement.

This could support a transparent future app design where clinicians can see and potentially swap the guideline basis for an extraction task.

---

## 8. Benchmark Reconciliation Work Needed

The dissertation should not treat Fang, ExECTv2, and Gan as a simple ladder of benchmark targets. They measure different things.

Create a reconciliation table covering:

- task definition;
- unit of prediction;
- label taxonomy;
- temporal policy;
- evidence expectation;
- gold source;
- scoring rule;
- published target;
- comparability limits;
- valid claim type.

Specific actions:

- inspect Fang taxonomy and scoring in more detail;
- inspect ExECTv2 schema fully, including lower/upper seizure counts and BRAT CUIPhrase mappings;
- decide which ExECTv2 fields are usable as-is, usable with revised scoring, or unsuitable for final claims;
- avoid describing collapsed labels as a replacement for fine-grained ILAE evaluation.

---

## 9. Near-Term Next Steps

1. Sanitize the final prompts and document all internal artefacts currently exposed to models. **Implemented infrastructure; A/B model runs pending.**
2. Build a temporality challenge set from ExECTv2 letters. **Implemented initial validation slice.**
3. Add raw vs projected scoring reports for promoted relaxed harnesses. **Projection delta reporting implemented; direct raw-output metrics still pending where feasible.**
4. Define evidence support scoring separately from quote validity. **Implemented
   as rule-assisted per-claim support classification; manual adjudication or
   model-assisted semantic judging remains future work.**
5. Design the 40-document final clarification matrix. **Initial machine-readable matrix skeleton, costed down-selection, launcher, and first low-cost condition implemented.**
6. Rerun Gemini 3 Flash under fixed quota conditions.
7. Revisit qwen3.6:27b and qwen3.6:35b on 40-doc controlled harness comparisons.
8. Test local evidence-in-prompt vs deterministic evidence resolver.
9. Add retrieval-highlight experiments for ExECTv2 medication and seizure type.
10. Write the benchmark reconciliation table before making any stronger external benchmark claims.

---

## 10. Working Conclusion

The strongest dissertation argument is not that one model or one harness wins. It is that clinical information extraction performance depends on the interaction between task type, model capability, prompt architecture, normalization policy, evidence design, and benchmark validity.

The next experimental phase should make that interaction explicit.
