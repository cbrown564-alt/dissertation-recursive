# Multi-Agent Extraction Pipeline Plan

**Date:** 2026-05-11  
**Status:** Planned  
**Harness ID:** MA_v1  
**Doc supersedes:** nothing — this is a new experimental thread  
**Related:** doc 34 (full experiment record §3.5–3.6, D3 finding), doc 27 (final full-field
evaluation plan, Option A / architecture ablation)

---

## Motivation

The supervisor's original project brief described a training-free multi-agent system with
four explicit roles: (a) Section/Timeline Agent, (b) per-field-family Field Extractor Agents,
(c) Verification Agent, (d) Aggregator Agent. The project has independently discovered and
tested components matching roles (b)–(d) in stages D and E: H2 for per-field extraction,
D3 for verification (best single dev result: quality 0.846, highest of any condition tested),
and E3 for aggregation. None of these were framed as a multi-agent system, and they were
never assembled into one pipeline.

Role (a) — the Section/Timeline Agent — has never been built. It is the missing component.
Its absence explains the largest remaining failure mode: the `family_history_trap`
perturbation causes S2 to drop −0.400 on seizure type because the model reads family seizure
history as current patient findings. An explicit segmentation pass would isolate those spans
before field extraction begins.

This plan builds the full four-stage MA_v1 pipeline, runs it on two cost-efficient models
(GPT-5.4-mini and qwen3.6:35b), and compares it against the existing single-prompt and
event-first baselines. GPT-5.5 is promoted conditionally based on validation results.

---

## Research Questions

1. Does a four-stage multi-agent pipeline improve full-field extraction quality (BenchComp,
   FullComp) relative to single-prompt S2 and event-first E3?
2. Does explicit section segmentation reduce the seizure type errors caused by family-history
   context bleeding? (Primary hypothesis for Role a.)
3. Does parallel per-field extraction with section-specific context improve over monolithic
   full-letter extraction?
4. Does a full verification pass (Role c) combined with explicit evidence spans produce higher
   quote_validity and lower hallucination rate than D3's simpler keep/drop design?
5. What is the cost and latency overhead per document for MA_v1 vs S2/E3, and does quality
   justify it?
6. Does the pipeline exhibit the same model-specific harness sensitivity observed elsewhere
   (H6fs helping qwen, hurting gemma), or does the structured decomposition make quality
   more model-agnostic?

---

## Pipeline Architecture: MA_v1

### Stage 1 — Section/Timeline Agent (one call per document)

**Input:** raw letter text.  
**Task:** Segment the letter into named clinical sections and build a temporal event index.  
**Output JSON:**

```json
{
  "sections": [
    {"label": "Presenting Complaint", "is_current": true, "excerpt_start": "..."},
    {"label": "Past Medical / Seizure History", "is_current": false, "excerpt_start": "..."},
    {"label": "Family History", "is_current": false, "is_family": true, "excerpt_start": "..."},
    {"label": "Current Medications", "is_current": true, "excerpt_start": "..."},
    {"label": "Investigations", "is_current": false, "excerpt_start": "..."},
    {"label": "Assessment and Plan", "is_current": true, "excerpt_start": "..."}
  ],
  "current_seizure_mentions": ["<verbatim quote>", "..."],
  "historical_seizure_mentions": ["<verbatim quote>", "..."],
  "family_history_seizure_mentions": ["<verbatim quote>", "..."]
}
```

**Why it matters:** The three seizure mention lists are passed as explicit context to Stage 2.
The field extractor for seizure types receives only `current_seizure_mentions`; historical and
family mentions are withheld. This is the direct structural fix for `family_history_trap`.

**Failure mode:** The letter may not have explicit section headings. The prompt must handle
flowing prose letters by inferring section boundaries from clinical content, not headers.
If section segmentation is incomplete, Stage 2 falls back to full-letter context.

---

### Stage 2 — Parallel Field Extractor Agents (three or four calls per document)

Each call receives: (i) full letter text, (ii) the segmentation output from Stage 1, and
(iii) the relevant section excerpts highlighted in the prompt. Calls can be issued concurrently.

**Call 2a — Medications:**  
Extract all CURRENT medications as `[{name, dose, unit, frequency}]`.  
Receives: full letter + Current Medications section excerpt.  
Uses: H6full-style medication prompt with structured output.  
Constraint: do not extract historical or discontinued medications unless explicitly labelled
as current.

**Call 2b — Seizure Types and Frequency:**  
Extract CURRENT seizure types and current seizure frequency.  
Receives: full letter + `current_seizure_mentions` list from Stage 1 (family and historical
lists withheld).  
Uses: H6v2-style seizure prompt (CURRENT-only constraint, `unknown seizure type` guidance,
Gan-normalized frequency format).

**Call 2c — Investigations:**  
Extract EEG result and MRI result.  
Receives: full letter + Investigations section excerpt.  
Uses: H6full-style investigation prompt with the fixed normalization instruction ("use
normal/abnormal directly, do not copy raw description text").

**Call 2d — Epilepsy Diagnosis (optional separate call):**  
Extract epilepsy diagnosis type and syndrome.  
Receives: full letter (diagnosis integrates all sections).  
This call may be merged into 2b if model capacity allows — keep separate if seizure + diagnosis
output length risks truncation.

---

### Stage 3 — Verification Agent (one call per document)

**Input:** all Stage 2 field extractions + full letter text.  
**Task:** For each extracted item, verify (a) evidence support (is there a verbatim quote?),
(b) temporal scope (is this current?), (c) internal consistency (do extracted fields
contradict each other?).  
**Output JSON:**

```json
{
  "medications": [
    {"name": "...", "action": "keep|drop|modify", "evidence_quote": "...", "reason": "..."}
  ],
  "seizure_types": [
    {"label": "...", "action": "keep|drop|modify", "evidence_quote": "...", "reason": "..."}
  ],
  "seizure_frequency": {"value": "...", "action": "keep|drop|modify", "evidence_quote": "..."},
  "investigations": {"eeg": {...}, "mri": {...}},
  "diagnosis": {"action": "keep|drop|modify", "evidence_quote": "...", "reason": "..."},
  "consistency_flags": ["..."]
}
```

**Design note:** This is D3 extended with an explicit temporal-scope check and cross-field
consistency check. The `reason` field for `drop` decisions is included in the final output
for error analysis.

---

### Stage 4 — Aggregator Agent (one call per document)

**Input:** Stage 3 verified output.  
**Task:** Produce a single canonical JSON extraction in H6full-compatible format. Add a
per-field confidence marker (`high | medium | low`) where `low` indicates the verifier
flagged the field or evidence was absent.  
**Output:** H6full-compatible JSON, projectable via existing `projected_canonical` in
`src/model_expansion.py`.

---

### Total Call Budget per Document

| Stage | Calls | Can parallelise? | Notes |
|---|---:|---|---|
| 1 Segmentation | 1 | No (required input for stage 2) | ~200–400 output tokens |
| 2a Medications | 1 | Yes (parallel with 2b, 2c, 2d) | ~300–500 output tokens |
| 2b Seizure/Freq | 1 | Yes | ~200–400 output tokens |
| 2c Investigations | 1 | Yes | ~100–200 output tokens |
| 2d Diagnosis | 1 | Yes (merge with 2b if short) | ~100–200 output tokens |
| 3 Verification | 1 | No (waits for all stage 2) | ~400–600 output tokens |
| 4 Aggregation | 1 | No (waits for stage 3) | ~400–600 output tokens |
| **Total** | **6–7** | Stages 2a–2d parallel | Latency: stages 1 + 2(parallel) + 3 + 4 |

**Effective latency for qwen3.6:35b at ~12s/call:**  
Stage 1 (12s) + Stage 2 parallel (12s) + Stage 3 (12s) + Stage 4 (12s) = **~48s/doc**  
cf. H6full at ~12s/doc and E3 at ~24s/doc.

**GPT-5.4-mini cost estimate:**  
~6 calls × ~750 tokens average × $0.15/1M input + $0.60/1M output  
≈ $0.003–0.005/doc → **$0.12–0.20 for 40 docs.** Negligible.

---

## Implementation Plan

### New Files

**`src/multi_agent.py`** — primary implementation.

Functions to implement:

```
stage1_segment(letter_text, model_id, client) -> SegmentationOutput
stage2_medications(letter_text, seg, model_id, client) -> MedicationOutput
stage2_seizure(letter_text, seg, model_id, client) -> SeizureOutput
stage2_investigations(letter_text, seg, model_id, client) -> InvestigationOutput
stage2_diagnosis(letter_text, seg, model_id, client) -> DiagnosisOutput
stage2_all_parallel(letter_text, seg, model_id, client) -> Stage2Bundle
    # uses asyncio.gather or concurrent.futures for parallel calls
stage3_verify(letter_text, stage2_bundle, model_id, client) -> VerifiedBundle
stage4_aggregate(verified_bundle, model_id, client) -> CanonicalOutput
run_ma_pipeline(letter_text, model_id, client) -> CanonicalOutput
```

**Entrypoint:** CLI command `python src/multi_agent.py run --model <id> --split <dev|val> --docs <n>`

### Reuse from Existing Infrastructure

- `projected_canonical` in `src/model_expansion.py` — reuse for final JSON projection
- `src/evaluate.py` — unchanged; MA output is scored identically to H6full output
- `src/normalization.py` — ASM synonyms, canonical investigation result, seizure label collapse
- Existing Ollama adapter from `src/model_expansion.py` for qwen3.6:35b calls
- Existing OpenAI adapter for GPT-5.4-mini and GPT-5.5 calls

### Prompt Design

Each stage prompt is short and narrowly scoped. The Stage 1 prompt is the most novel;
Stages 2a–2d reuse the H6full prompt structure with section-specific context added.
Stage 3 reuses the D3 verifier structure extended with temporal-scope check.
Stage 4 is a new aggregation prompt that takes structured verified fields directly.

Prompt length targets:
- Stage 1: ~800 tokens input
- Stage 2a–2d: ~1,200–1,600 tokens input each (full letter + section highlights)
- Stage 3: ~1,200 tokens input (all field outputs + letter)
- Stage 4: ~600 tokens input (verified fields only)

---

## Experimental Stages

### MA0: Stub Smoke Test (2 dev docs, stub provider)

Verify that the four-stage pipeline produces valid JSON at each stage, calls `projected_canonical`
correctly, and writes the standard artifact set (raw outputs, call report, scorer output).  
**Gate:** parse=100%, schema_valid=100%, all fields present.

### MA1: Development Pilot (10 dev docs, GPT-5.4-mini + qwen3.6:35b)

**Goal:** Establish that the pipeline produces sensible extractions and identify any prompt or
parse failures before the full validation run.  
**Baseline comparison:** S2 GPT-4.1-mini (BenchComp 0.792) and E3 GPT-4.1-mini (BenchComp 0.809)
on the same 10 dev docs from stage_d_h6_h7_diagnostic.  
**Decision gate:** proceed to MA2 if BenchComp ≥ 0.80 for at least one model, or if a specific
hard-field improvement (seizure F1 ≥ 0.680 or zero parse errors) is observed.

### MA2: Validation Scale (40 val docs, GPT-5.4-mini + qwen3.6:35b)

**Goal:** Authoritative validation comparison for the dissertation.  
**Primary baselines:**

| System | BenchComp | Source |
|---|---:|---|
| GPT-4.1-mini S2 | 0.792 | Existing |
| GPT-4.1-mini E3 | 0.809 | Existing |
| qwen3.6:27b H6full v2 | 0.785 | Existing |
| qwen3.6:35b H6full | 0.744 | Existing |
| GPT-5.5 D3 (dev only) | 0.846* | Stage E (dev, not val) |

*D3 on GPT-5.5 is the implicit upper-bound reference. MA_v1 is the first attempt to test D3's
architecture at validation scale with the segmentation component added.

**Acceptance criteria for promotion to MA3 (GPT-5.5):**

- MA_v1 GPT-5.4-mini or MA_v1 qwen3.6:35b achieves BenchComp > 0.810 on validation  
  (beats frontier E3); **or**
- Seizure type F1 collapsed ≥ 0.660 on validation for any model (meaningful gain on the
  hardest remaining field); **or**
- `family_history_trap` perturbation seizure drop < −0.200 (half the current S2 worst-case)
  confirmed by robustness mini-run.

If none of these are met, GPT-5.5 is not run and the result is reported as a clean
negative (MA_v1 does not outperform the simpler harnesses at this scale).

### MA3: GPT-5.5 Validation (40 val docs, conditional)

Run only if MA2 promotion criteria are met.  
**Comparison:** MA_v1 GPT-5.5 vs D3 GPT-5.5 (existing dev result only) and frontier E3.  
This is the direct test of whether full multi-agent architecture improves on D3 verification
alone.

---

## Evaluation

### Metrics (identical to final full-field evaluation)

- `medication_name_f1`, `medication_full_f1`, dose/unit/freq component F1
- `seizure_type_f1_collapsed`
- `epilepsy_diagnosis_accuracy_collapsed`
- EEG accuracy, MRI accuracy
- `current_seizure_frequency_pragmatic_f1`
- `temporal_accuracy`
- `schema_valid_rate`, `quote_presence_rate`, `quote_validity_rate`
- **BenchComp** (benchmark-field composite: med name + seizure + diagnosis + EEG + MRI)
- **FullComp** (all fields including medication full, frequency, temporal, schema, quote)

### Additional MA-Specific Metrics

- `stage1_section_count` — how many sections the segmenter identified (proxy for segmentation quality)
- `stage1_current_seizure_count` — number of current seizure mentions extracted  
- `stage3_drop_rate` — fraction of field items dropped by the verifier (proxy for over-extraction)
- `stage3_modify_rate` — fraction modified (proxy for verifier value-add)
- `per_stage_parse_success` — parse rate at each of the four stages independently
- `total_calls_per_doc` and `total_latency_per_doc`

These are logged in the call report alongside the standard metrics.

### Robustness Mini-Run (MA2 only, 5 docs × 3 perturbations)

Test the three perturbations most relevant to the segmentation hypothesis:

- `family_history_trap` — primary target of Stage 1 isolation
- `negated_investigation_trap` — secondary target of Stage 3 verification
- `bullets_to_prose` — tests whether segmentation degrades on unstructured format

Report worst metric drop per system compared to H6full and S2 baselines.

---

## Artifact Structure

```
runs/multi_agent/
  stage_ma0_stub/
  stage_ma1_dev_pilot/
    gpt_5_4_mini_MA_v1/
      raw_stages/         # per-doc JSON for each stage output
      projected/          # projected_canonical outputs
      call_report.csv
      evaluation.json
    qwen_35b_MA_v1/
      ...
  stage_ma2_validation/
    gpt_5_4_mini_MA_v1/
    qwen_35b_MA_v1/
    comparison_table.csv  # all systems including baselines
    promotion_decision.md
  stage_ma3_gpt55/ (conditional)
    gpt_5_5_MA_v1/
    comparison_table.csv
```

---

## Relationship to Final Dissertation Claims

MA_v1 is positioned as the **architecture ablation** (F8 slot in the final full-field
evaluation plan). It directly answers the supervisor's original research question:

> Does a multi-agent extraction pipeline with explicit section segmentation, per-field-family
> extraction, evidence-grounded verification, and constrained aggregation improve over
> single-prompt extraction under the same budget constraints?

The result will be one of three dissertation outcomes:

**Positive result (BenchComp > 0.810):** MA_v1 is promoted as the best architecture. The
dissertation claims that decomposing extraction into explicit agent roles improves reliability
beyond what single-prompt or event-first approaches achieve, primarily through section
isolation reducing temporal context bleeding.

**Partial result (specific field improves, overall flat):** The dissertation reports that
multi-agent segmentation improves seizure type extraction or robustness under perturbation,
but does not improve overall quality. The finding supports the architectural motivation while
acknowledging that simpler baselines remain competitive on the full field set.

**Negative result (no meaningful improvement):** The dissertation reports that the existing
D3/E3 components already capture most of the value available from multi-step processing, and
the additional segmentation stage does not further improve on the hard fields. This is a clean
experimental finding that validates the supervisor's research question by answer rather than
by absence.

In all three cases the multi-agent pipeline is a genuine dissertation contribution: the first
time the full four-role architecture has been assembled and evaluated on this task.

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Stage 1 segmentation fails on letters without explicit section headers | Prompt must handle flowing prose; fall back to full-letter context if segmentation confidence is low |
| Parallel calls to Ollama cause contention (observed in EL2) | Run Stage 2 calls sequentially for qwen3.6:35b; only parallelise for API models where latency is network-bound |
| Stage 3 verifier over-drops, producing low recall | Track drop_rate metric; if > 20% of items are dropped, inspect Stage 3 prompt for over-aggressive criteria |
| Total latency makes qwen3.6:35b impractical (~48s/doc) | Report latency explicitly; frame as quality-over-speed system distinct from 12s H6full deployment candidate |
| GPT-5.4-mini (with reduced capability) underperforms on multi-step reasoning | If Stage 4 aggregation quality is low for 5.4-mini, test whether Stage 4 can be replaced with a deterministic merge (no LLM call) using Stage 3 verified fields directly |
| New thread delays G4-Full and test-split runs | MA development runs in parallel with G4-Full (no shared dependency). Test split is not touched until MA2 validation is complete. |

---

## Immediate Next Steps

1. Implement `src/multi_agent.py` with the four stages and CLI entrypoint.
2. Write Stage 1 segmentation prompt and verify on 2–3 sample letters manually.
3. Adapt H6full Stage 2a–2d prompts to accept section-specific context.
4. Adapt D3 verifier prompt for Stage 3 (add temporal scope and cross-field consistency checks).
5. Run MA0 stub smoke test (2 docs).
6. Run MA1 dev pilot (10 docs, GPT-5.4-mini + qwen3.6:35b).
7. Evaluate against baselines; make MA3 promotion decision.
8. Run MA2 validation (40 docs) if MA1 passes gate.
