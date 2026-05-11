# Local Event-First Investigation Plan

**Date:** 2026-05-10  
**Status:** Planned  
**Motivation:** The event-first pipeline (E1/E2/E3) is the strongest frontier system on ExECTv2
(E3 leads every medication metric; most robust to perturbations). It was never tested on local
models. The original abandonment (Stage L1) was almost certainly a misdiagnosis: the >30-minute
timeouts are the signature of extended-thinking token exhaustion via the OpenAI-compat shim,
not genuine evidence that local models cannot handle the task. The native `/api/generate` +
`think: false` fix reduced H6 latency from >6 minutes to 5–25 seconds. L1 should be re-run
under the fixed infrastructure before drawing any conclusion.

A secondary motivation is the gemma4 schema-extension finding: all three schema additions
(H6qa, H6ev, H6fs) regressed gemma4:e4b, with H6qa and H6ev producing parse_error=40. This
suggests that for gemma4, the problem is not capability but format compliance under schema
complexity. A stripped-down event-first harness might avoid that failure mode entirely by
asking for a compact list rather than a fully annotated JSON object.

**Research questions:**

1. With the native API fix, can local models produce valid E1 event outputs without timeout?
2. Is the full E1/E2/E3 harness viable for any local model, or is a stripped-down variant
   needed?
3. Does event-first improve quality over H6/H6fs for models at ≥27B scale, where schema
   compliance is reliable?
4. Does deterministic E2 aggregation (no second LLM call) recover most of the E3 gain at
   lower latency cost?
5. Is there a model-capability threshold below which event-first degrades (e.g., 4B cannot
   produce consistent event schemas) but above which it helps (e.g., 27B benefits from the
   structured decomposition)?

---

## Background: What Was Diagnosed, What Was Not

**Stage L1 original note:**
> "H0 is unusable for local models. The canonical schema prompt (~3,700 tokens input) causes
> qwen3.5:9b to generate responses that take >30 minutes per document even with thinking
> disabled."

**Why this is probably a misdiagnosis:**
- The >30-minute figure matches the extended-thinking token exhaustion symptom observed for
  qwen3.5 on the OpenAI-compat endpoint: the `think: false` parameter is silently ignored by
  the shim, all tokens are consumed by reasoning, and the request stalls.
- The same symptom was observed in G2 for GPT-5.5 (`max_output_tokens=512` exhausted by
  reasoning), confirming the pattern.
- With the native API fix, H6 (benchmark-only JSON, ~500-token prompt) runs in 5–25 seconds.
  H0 (full canonical schema, ~3,700-token prompt) would produce a longer output (~2,000–3,000
  tokens) but at 30–50 tok/s that is 60–100 seconds — not 30 minutes.
- The "fails to terminate cleanly" observation may also reflect the thinking loop rather than
  genuine schema complexity.

**What has not been tested:**
- H0 on any local model with the fixed native API endpoint
- E1 event extraction on any local model
- E2 or E3 aggregation on any local model
- Any stripped-down event-first variant on any local model

---

## Harness Variants

Five event-first harness variants to test, from simplest to fullest:

### EL-micro: Event List, Minimal Fields
Prompt asks for a flat JSON array. Each element has three fields only:
```json
[
  {"type": "medication", "value": "levetiracetam 500mg twice daily", "quote": "..."},
  {"type": "seizure_type", "value": "focal aware seizure", "quote": "..."},
  {"type": "diagnosis", "value": "focal epilepsy", "quote": "..."}
]
```
Aggregation: deterministic (E2-style rule-based, no second LLM call). Requires minimal output
tokens. Designed to stay within gemma4's demonstrated schema compliance range.

### EL-compact: Event List, Benchmark Fields Only
Prompt asks for a JSON array with five typed event structures (medication, seizure_type,
seizure_frequency, investigation, diagnosis), each with `value`, `quote`, and `current: bool`.
No event IDs, no full canonical schema. Aggregation: deterministic E2-style.

### EL-E1only: Full E1 Events, Deterministic Aggregation (E2)
Full canonical E1 event schema with event IDs, temporal scope, certainty fields — identical
to the frontier E1 prompt. Aggregation: deterministic E2 only (no second LLM call). This
isolates the event-extraction quality question from aggregation LLM costs.

### EL-E1E2: Full E1 Events + Deterministic Aggregation
Same as EL-E1only. Same thing, separate label to track whether it was run as a standalone
or as the first stage of EL-E1E3.

### EL-E1E3: Full E1/E2/E3 (frontier equivalent)
Full canonical E1 extraction followed by constrained LLM aggregation (E3 second call). This
is the direct equivalent of the frontier E3 system — same harness, local model.

---

## Models to Test

| Model | Size | Expected latency/call | Architecture | Priority |
|---|---|---|---|---|
| qwen3.5:9b | ~6 GB | 5–25s | Dense transformer | High — reference local model |
| qwen3.5:4b | ~3 GB | 3–15s | Dense transformer | High — test minimum viable scale |
| gemma4:e4b | ~10 GB | 20–40s | Multimodal dense | High — schema-extension issue to retest |
| qwen3.6:35b | ~23 GB | 10–20s | MoE 8/256 active | High — best speed at large scale |
| qwen3.6:27b | ~17 GB | 25–45s | Dense 27B | Medium — best medication F1 |

The 27B and 35B models are the most interesting for event-first because schema compliance
should be better at larger scale. The 4B model is included to characterize the capability
floor.

---

## Stage EL0: Re-Diagnosis (2 dev docs, no scoring)

**Purpose:** Determine whether H0/E1 is viable at all on local models under the fixed native
API. This is a latency-only check — not a quality run.

**Actions:**
1. Run H0 (full canonical schema direct extraction) on 2 development documents.
   Models: qwen3.5:9b, gemma4:e4b, qwen3.6:35b.
   Record: latency, parse success, output length in tokens.
2. Run E1 (full event extraction prompt) on the same 2 documents.
   Same models. Record: latency, parse success, event count, quote presence.
3. Do not score — this is purely to verify termination and format.

**Expected outcome:**
- qwen3.5:9b: H0 completes in 60–180s (not 30 min). E1 shorter (~1,000–1,500 token output).
- gemma4:e4b: H0 completes without parse failure.
- qwen3.6:35b: H0 and E1 complete fastest due to MoE speed.

**Decision rule:**
- If any model times out (>5 minutes) with thinking disabled on native API: that model's H0
  is genuinely infeasible. Note separately from models that produce output but fail to parse.
- If all models complete in <3 minutes: proceed to EL1 with full model set.
- If only larger models complete: proceed to EL1 with ≥9B models only.

**Outputs:** `runs/local_event_first/el0_rediagnosis/latency_report.csv`

---

## Stage EL1: Development Pilot (10 dev docs, all variants)

**Purpose:** Identify which model × harness combinations are worth taking to validation scale.
Small enough to be cheap; large enough to distinguish systematic quality differences from noise.

**Design:**
- Split: development, 10 documents (same 10 for all conditions)
- Models: all five (qwen3.5:4b, qwen3.5:9b, gemma4:e4b, qwen3.6:35b, qwen3.6:27b)
- Harnesses: EL-micro, EL-compact, EL-E1E2, EL-E1E3 (skip EL-E1only as it is identical to EL-E1E2)
- Harness × model combinations to deprioritize: qwen3.5:4b on EL-E1E3 (likely schema failure);
  gemma4:e4b on EL-E1E3 (second LLM call may produce schema extension failures)
- Comparison baselines: qwen3.5:9b H6, gemma4:e4b H6, qwen3.6:35b H6fs (already run)
- Repeats: 1
- Scoring: corrected scorer

**Metrics per condition:**
- Parse success rate (E1 output)
- Event count per document (mean, min, max)
- Quote presence rate
- E2 aggregation success rate (field coverage)
- Med Name F1, Sz Collapsed F1, Dx Acc (corrected scorer)
- Latency per document (E1 call, E2/E3 call if applicable, total)
- Estimated tokens per document

**Expected patterns:**
- qwen3.5:4b: likely fails or produces malformed events on EL-E1E2/EL-E1E3; may succeed on
  EL-micro
- qwen3.5:9b: should succeed on EL-compact; uncertain on full E1 schema
- gemma4:e4b: EL-micro and EL-compact may succeed where H6qa/H6ev failed — the event list
  format is structurally different from schema extension
- qwen3.6:35b: best candidate for full E1/E3; MoE speed means total latency may be acceptable
- qwen3.6:27b: best candidate for E1 quality; latency is the tradeoff

**Promotion decision rule:**
A condition is promoted to EL2 if:
- Parse success ≥ 0.80 on E1 output
- Any benchmark-aligned metric improves over the same model's best H6 result by ≥ 0.03
- Total latency per document ≤ 3× the model's H6 latency (e.g., ≤ 36s for qwen3.5:9b)

A condition is retained as informative-only if it improves quality but exceeds the latency
gate — report it as an upper bound.

**Outputs:**
- `runs/local_event_first/el1_dev_pilot/comparison_table.csv`
- `runs/local_event_first/el1_dev_pilot/latency_table.csv`
- `runs/local_event_first/el1_dev_pilot/promotion_decision.md`

---

## Stage EL2: Validation Scale (40 docs)

**Purpose:** Validate promoted conditions on the held-out 40-doc validation split.

**Design:**
- Split: validation (40 documents)
- Models/harnesses: promoted from EL1 only
- Baselines for comparison: qwen3.5:9b H6fs, gemma4:e4b H6, qwen3.6:35b H6fs, qwen3.6:27b H6
  (all already run at 40-doc scale)
- Frontier comparisons: GPT-4.1-mini S2, GPT-4.1-mini E3 (corrected scorer)
- Repeats: 1

**Metrics (full corrected scorer):**
- Med Name F1, Med Full F1, Med component F1 (dose, unit, freq)
- Sz Strict F1, Sz Collapsed F1
- Dx Acc, Dx Collapsed
- Freq Loose (ExECTv2 crosswalk)
- Schema validity, Quote validity, Temporal accuracy
- Latency p50/p95, total call cost

**Hypothesis testing:**
- Does event-first improve seizure type F1 collapsed on local models as it did on frontier (E3 0.633 vs S2 0.610)?
- Does event-first improve medication full tuple F1 on local models?
- Does the unknown-seizure-type miss count (consistently 13–15 across all H6 variants) change under event extraction?
- Does gemma4:e4b benefit from event-first where it resisted schema extensions?
- Is there a crossover point (model size or architecture) where event-first starts to help?

**Outputs:**
- `runs/local_event_first/el2_validation/comparison_table.csv`
- `runs/local_event_first/el2_validation/field_prf_table.csv`
- `runs/local_event_first/el2_validation/el2_decision.md`

---

## Anticipated Findings and Their Implications

| Scenario | Implication |
|---|---|
| EL0 confirms H0/E1 terminates cleanly on fixed API | L1 was a misdiagnosis; event-first is viable for local models |
| EL0 still times out for some models | Genuine capability/output-length constraint; EL-micro/EL-compact are the right designs |
| EL1: gemma4 succeeds on EL-micro where H6qa/H6ev failed | Schema extension failures were format-specific, not capability-specific |
| EL1: quality improvement only appears at 27B/35B | Capability threshold finding: event-first requires a certain extraction quality to be worth its complexity |
| EL1: E2 (deterministic) captures most of E3 gain | Second LLM aggregation call is not worth its latency cost at local model scale |
| EL2: event-first closes the unknown-seizure-type gap | Event extraction forces the model to explicitly classify each mention, reducing the meta-label miss |
| EL2: event-first does not change the 13–15 miss count | The meta-label gap is structural and not addressable via output format alone |

---

## Relationship to Existing Results

This plan adds event-first coverage to the existing local models workstream. It does not
replace any existing results. The H6/H6fs results (40-doc validation for all five local
models) remain the benchmark for comparison — any event-first condition must beat the
same model's best H6 variant to justify its complexity and latency cost.

If EL2 produces competitive results for any model × harness pair, those candidates should be
added to the `final_full_field` candidate registry alongside F1–F5c.

The most dissertation-relevant outcome is a clear statement of whether event-first is worth
its overhead at local model scale, with the model size × architecture dimension resolved:
- If small models (4B, 9B) cannot reliably produce valid event schemas, that is a finding.
- If large models (27B, 35B) benefit meaningfully from event-first, that strengthens the
  local deployment claim.
- If no local model benefits, the architecture conclusion is that event-first adds value
  through stronger frontier aggregation, not through the event-extraction step itself.

---

## Cost and Time Estimate

| Stage | Docs × models × conditions | Estimated wall time | API cost |
|---|---|---|---|
| EL0 (re-diagnosis) | 2 × 3 × 2 = 12 calls | ~15–30 min | $0 |
| EL1 (dev pilot) | 10 × 5 × 3 (deprioritized) ≈ 100–150 calls | ~2–4 hrs | $0 |
| EL2 (validation) | 40 × ~3 promoted ≈ 120 calls | ~3–6 hrs | $0 |
| **Total** | | **~6–11 hrs** | **$0** |

All costs are zero because all models are Ollama-hosted. The latency investment is the real
cost. EL0 is the cheapest and highest-value stage — run it first.

---

## Immediate Next Action

Run EL0 re-diagnosis on qwen3.5:9b and qwen3.6:35b, 2 development documents, H0 canonical
and E1 event extraction, native `/api/generate` endpoint with `think: false`. If both models
complete within 3 minutes, L1 was a misdiagnosis and event-first investigation is justified
at full scale.
