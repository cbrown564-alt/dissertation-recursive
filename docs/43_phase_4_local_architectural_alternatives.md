# Phase 4 — Local Architectural Alternatives: Event-First & Multi-Agent

**Date:** 2026-05-10 (EL0–EL2); 2026-05-11 (MA0–MA3)  
**Scope:** Event-first extraction (EL0/EL1/EL2) and multi-agent pipeline (MA_v1) on local models.  
**Purpose:** Test whether complex multi-stage pipelines improve on simple single-pass H6 extraction for locally-hosted models.  
**Status:** Complete. Both approaches produced negative results at validation scale.

---

## 1. Aims & Research Questions

Phase 3 established that local direct models — specifically qwen3.6:35b H6fs — can match frontier medication F1 at zero cost. However, two more complex architectural alternatives remained untested on local hardware:

1. **Event-first extraction (E1/E2/E3):** The strongest frontier system on ExECTv2 (E3 leads every medication metric, most robustness-robust). It was never tested on local models because Stage L1 abandoned H0 after qwen3.5:9b took >30 minutes per document.
2. **Multi-agent decomposition (MA_v1):** A four-role pipeline (segmentation → parallel field extractors → verifier → aggregator) proposed as an alternative to both single-pass direct and event-first architectures.

**Primary research questions:**
1. Does event-first extraction improve local model performance once the original infrastructure barrier (thinking-token bug) is resolved?
2. Does a multi-agent decomposition improve accuracy by reducing per-call cognitive load?
3. Are the dev-pilot gains observed in small-scale tests real, or sampling noise?

**What we knew when we started:**
- Phase 3 (Local Direct) had established H6/H6fs as the best local harness.
- The thinking-token bug (compat shim ignoring `think: false`) had been fixed in Phase 3 via the Ollama native API.
- E3 was the frontier best system, but its full-schema prompts were assumed infeasible for local models.
- Multi-agent had never been tested; it was proposed in `docs/36_multi_agent_pipeline_plan.md` on May 11 as a late architectural experiment.

---

## 2. Event-First Revisited: EL0–EL2

### 2.1 Why revisit event-first?

The original abandonment of event-first for local models (May 8, L1) was based on qwen3.5:9b taking >30 minutes per document with H0. At the time, this was interpreted as "local models cannot handle full-schema prompts." The Phase 3 thinking-token fix revealed that the slowness was largely the compat shim bug, not genuine incapability.

This created a natural experiment: if H0 is technically feasible, is the event-first pipeline (which uses H0-like prompts for E1) better than simple H6 direct extraction?

### 2.2 EL0: Re-Diagnosis (2 dev docs)

**Source code:** `src/local_event_first.py`, `src/el1_rescore.py`

Ran H0 (full canonical schema) under the fixed native Ollama API to determine whether the original L1 failure was the thinking bug or genuine incapability. Also ran EL_micro (new minimal event list format) to check latency and parse.

| Model | Harness | Result | Latency | Output tokens |
|-------|---------|--------|---------|---------------|
| qwen_9b | H0 | Parse=False (truncated at token limit) | 108s/doc | 2048 |
| qwen_35b | H0 | 300s timeout | 300s timeout | — |
| qwen_9b | EL_micro | Parse=False (code bug: `extract_json_object` only extracts `{...}`, not `[...]`) | ~15s | — |
| qwen_35b | EL_micro | Parse=False (same code bug) | ~20s | — |

**Key findings:**
- L1 was a misdiagnosis — but only for qwen_9b. qwen_35b genuinely cannot run H0 within a 300s timeout.
- E1 event extraction produces ~1,000 output tokens (less than H0's 2,000–3,000), making EL_E1E2 potentially viable for qwen_35b.
- A parse bug was discovered: `extract_json_object` in the existing `parse_json_response` only extracts `{...}` delimiters, not `[...]` arrays. Fix applied to `_parse_event_list`; re-parsing cached outputs confirmed all four responses were valid JSON arrays.

### 2.3 EL1: Development Pilot (10 dev docs)

**Harnesses tested:** EL_micro (flat event array), EL_compact (typed events with structured fields), EL_E1E2 (full frontier E1 prompt + deterministic E2 aggregation).

**Models:** qwen_9b, gemma_4b, qwen_35b. (qwen_4b excluded — HTTP 404, not pulled; qwen_27b excluded — compact docs hitting 278s, EL_E1E2 would all timeout.)

**Parse success rates:**

| Model | EL_micro | EL_compact | EL_E1E2 |
|-------|----------|------------|---------|
| qwen_9b | 10/10 | 10/10 | 10/10 |
| gemma_4b | 10/10 | 8/10 | **2/10** |
| qwen_35b | 10/10 | 10/10 | 9/10 (1 timeout) |

gemma_4b EL_E1E2 at 2/10 parse: the full E1 event schema is a schema extension that gemma4 refuses to follow, exactly as H6qa/H6ev produced parse_error=40 in Phase 3. The schema-extension aversion generalizes to the E1 format.

**Dev pilot quality (10 docs, corrected scorer):**

| Model | Harness | Med F1 | Sz F1c | Δsz vs H6 | Dx Acc |
|-------|---------|--------|--------|-----------|--------|
| gemma_4b | EL_micro | 0.973 | **0.769** | **+0.176** | 0.900 |
| qwen_35b | EL_micro | 0.973 | **0.692** | **+0.099** | 0.900 |
| qwen_9b | EL_E1E2 | 0.947 | **0.696** | **+0.094** | 0.800 |
| qwen_9b | EL_micro | 0.919 | 0.609 | +0.007 | 0.700 |
| qwen_35b | EL_compact | 0.947 | 0.455 | −0.138 | 0.900 |
| gemma_4b | EL_compact | 0.933 | 0.500 | −0.093 | 0.875 |
| qwen_9b | EL_compact | 0.895 | 0.571 | −0.031 | 0.800 |

Three conditions cleared the +0.03 seizure threshold on dev. EL_compact regressed all three models on seizure F1. EL_micro appeared to strongly help gemma_4b and qwen_35b. EL_E1E2 appeared to strongly help qwen_9b.

**Promotion to EL2:** EL_micro for all three models; EL_E1E2 for qwen_9b only.

### 2.4 EL2: Validation Scale (40 val docs)

**Runs:** EL_micro (qwen_9b + gemma_4b + qwen_35b); EL_E1E2/qwen_9b. Both ran in parallel, sharing the Ollama server — contention caused qwen_9b EL_micro to slow from 12s to ~65s/doc during overlap.

**Final combined EL2 results:**

| Model | Harness | Parse | Med F1 | Sz F1c | Δsz | Dx Acc | Lat/doc |
|-------|---------|-------|--------|--------|-----|--------|---------|
| qwen_9b | EL_micro | 1.00 | 0.779 | 0.538 | −0.064 | 0.825 | 61s |
| qwen_9b | EL_E1E2 | 0.95 | 0.807 | 0.594 | −0.008 | 0.816 | 77s |
| gemma_4b | EL_micro | 1.00 | 0.818 | 0.506 | −0.087 | 0.825 | 64s |
| qwen_35b | EL_micro | 1.00 | 0.855 | 0.585 | −0.008 | 0.825 | 41s |

**Flags (Δsz ≥ +0.03): None.** Every condition is at or below its H6 baseline on seizure type.

**What happened to the dev pilot gains:**

| Dev pilot claim | Validation | Verdict |
|-----------------|------------|---------|
| gemma_4b EL_micro +0.176 sz | −0.087 | Noise — reversed sign |
| qwen_35b EL_micro +0.099 sz | −0.008 | Noise — vanished |
| qwen_9b EL_E1E2 +0.094 sz | −0.008 | Noise — vanished |

### 2.5 Root cause of EL_micro underperformance

The extract-then-aggregate path forces the model to list raw event mentions before mapping to closed benchmark labels. The aggregation step then has to re-map those mentions — exactly the problem H6 solves in a single pass with an explicit `Allowed labels:` block.

The two-step design adds latency and re-introduces the label-mapping problem without providing any structural benefit on seizure type. EL_compact performed worst of all three harnesses because its richer schema (with dose/unit/frequency/modality fields) creates cognitive overhead without a corresponding quality gain.

**Note on qwen_35b EL_micro diagnosis accuracy:** +0.025 above H6fs baseline (0.825 vs 0.800). This was the one positive signal, but at 3.4× latency cost and with no improvement on the primary seizure type metric, it is not sufficient to justify using EL_micro in deployment.

### 2.6 Definitive conclusion

**H6/H6fs remains the correct harness for all local models on this task.** Event-first extraction does not provide a seizure-type advantage at any model size tested (4B–35B). The L1 re-diagnosis confirmed the original abandonment was a bug for qwen_9b — but fixing the bug does not change the substantive experimental outcome. The simpler single-pass harness outperforms the more complex event-first pipeline on all primary metrics.

---

## 3. Multi-Agent Pipeline: MA_v1

### 3.1 Motivation and design

**Source code:** `src/multi_agent.py`  
**Plan:** `docs/36_multi_agent_pipeline_plan.md`

MA_v1 was conceived on May 11 as a four-role decomposition:
1. **Segmentation:** Split the letter into coherent sections (history, current status, investigations, plan)
2. **Parallel field extractors (2a–2d):** One extractor per field (medications, seizure types, diagnosis, investigations)
3. **Verification:** Keep/drop/normalize verifier for each extraction
4. **Aggregation:** Combine verified extractions into canonical JSON

**Hypothesis:** By reducing the cognitive load per call (each extractor sees only relevant sections and outputs only one field), smaller models could achieve higher accuracy than single-pass full-schema extraction.

**What we knew when we started:**
- Local direct models (Phase 3) had plateaued on seizure type (~0.60 F1).
- Local event-first (EL0–EL2) had just produced a negative result.
- Multi-agent had never been tested. It was a late attempt to find an architectural win.

### 3.2 MA0: Stub verification

Standard stub discipline: verify mechanics before API spend. All four stages produced valid empty canonical outputs.

### 3.3 MA1: Development pilot (10 docs)

| Condition | Med F1 | Sz F1 collapsed | Dx Acc | EEG | MRI | BenchComp |
|-----------|--------|-----------------|--------|-----|-----|-----------|
| gpt_5_4_mini:MA_v1 | 1.000 | 0.720 | 0.900 | 1.000 | 0.900 | **0.898** |
| qwen_35b_local:MA_v1 | 0.947 | 0.583 | 0.900 | 0.900 | 0.900 | 0.835 |

GPT-5.4-mini leads this pilot on BenchComp; local qwen_35b stays close on diagnosis and investigations but trails on medication and seizure collapsed F1.

### 3.4 MA2: Validation scale (40 docs), promotion gate

| Condition | Med F1 | Sz F1 collapsed | Dx Acc | EEG | MRI | BenchComp |
|-----------|--------|-----------------|--------|-----|-----|-----------|
| gpt_5_4_mini:MA_v1 | 0.868 | 0.610 | 0.775 | 0.925 | 0.825 | 0.757 |
| qwen_35b_local:MA_v1 | 0.868 | 0.603 | 0.800 | 0.950 | 0.900 | 0.772 |

**Promotion gates (MA2 → MA3):** BenchComp > **0.810** (beats frontier E3 composite anchor); seizure F1 collapsed ≥ **0.660**.

**Promotion decision:** **No promotion** — BenchComp 0.757 / 0.772 are below 0.810; seizure collapsed 0.610 / 0.603 are below 0.660.

### 3.5 MA3: GPT-5.5 on validation (40 docs)

| Condition | Med F1 | Sz F1 collapsed | Dx Acc | EEG | MRI | BenchComp |
|-----------|--------|-----------------|--------|-----|-----|-----------|
| gpt_5_5:MA_v1 | 0.769 | 0.379 | 0.750 | 0.875 | 0.800 | 0.650 |

**Learning:** MA_v1 with GPT-5.5 **regresses** versus MA2 conditions on BenchComp and especially seizure collapsed F1, suggesting error propagation across stages rather than a fix from scaling model size alone.

### 3.6 Error analysis: Why MA_v1 failed

The multi-agent pipeline introduces multiple new failure modes:
1. **Segmentation errors:** If the segmentation stage misidentifies the boundary between history and current status, all downstream extractors see the wrong context.
2. **Extractor inconsistency:** Parallel extractors may disagree on temporality (e.g., one says "current," another says "historical").
3. **Verifier over-pruning:** The keep/drop verifier is conservative. It drops ambiguous extractions, which improves precision but harms recall.
4. **Aggregation loss:** The final aggregator must reconcile conflicting evidence without seeing the original letter. This is harder than single-pass extraction where the model sees everything at once.

The MA2 results show that these error-propagation costs outweigh the cognitive-load benefits. The pipeline achieves strong dev results (0.898 BenchComp) because 10 documents are easy to segment consistently. At 40 documents, segmentation variance increases and error propagation kills performance.

---

## 4. Cross-Architectural Comparison

| Architecture | Best local result (val) | Med F1 | Sz F1c | Dx Acc | Lat/doc | Complexity |
|--------------|------------------------|--------|--------|--------|---------|------------|
| Direct H6fs (Phase 3) | qwen3.6:35b | 0.852 | 0.593 | 0.800 | 12s | Single call |
| Event-first EL_micro (EL2) | qwen_35b | 0.855 | 0.585 | 0.825 | 41s | Two calls |
| Event-first EL_E1E2 (EL2) | qwen_9b | 0.807 | 0.594 | 0.816 | 77s | Two calls |
| Multi-agent MA_v1 (MA2) | qwen_35b | 0.868 | 0.603 | 0.800 | ~60s | 4+ calls |

**Interpretation:** Multi-agent achieves the highest medication F1 (0.868) and competitive seizure F1 (0.603), but at 4+ calls per document and still below the 0.810 BenchComp promotion gate. Event-first provides no advantage over direct. The simplest architecture (single-pass H6fs) is Pareto-optimal for local deployment.

---

## 5. What We Learned

1. **Complexity does not help local models.** Both event-first and multi-agent add latency, failure modes, and cognitive overhead without improving the primary seizure-type metric.
2. **Dev-pilot gains are unreliable.** All three EL1 apparent gains (+0.176, +0.099, +0.094) reversed or vanished at validation scale. This is a warning against over-interpreting small-sample results.
3. **Error propagation dominates in multi-stage pipelines.** A pipeline is only as strong as its weakest stage, and the product of stage accuracies is punishing.
4. **Schema-extension aversion is model-family specific.** gemma4 refuses to follow rich schemas (H6qa, H6ev, EL_E1E2), while qwen follows them obediently. This reinforces the Phase 3 finding that harness design must be model-specific.

---

## 6. Discontinuity Addressed

**Discontinuity 4: Event-first abandoned, then revisited.**

The EL0–EL2 revisit was not a random restart. It was a disciplined retest motivated by a root-cause fix (thinking-token bug). The narrative should emphasize:
- May 8: L1 abandoned event-first due to observed slowness (>30 min)
- May 8 (later): Thinking-token bug discovered and fixed
- May 10–11: EL0–EL2 run to determine whether the original abandonment was justified
- Result: The abandonment was justified for substantive reasons (single-pass H6 is better), not just the bug. The bug masked the true conclusion.

This is an example of **infrastructure confounding:** a tooling bug created the appearance of model incapability, and fixing the bug allowed a cleaner test of the architectural hypothesis.

---

*Document compiled from: `docs/_master_timeline_and_narrative.md`, `docs/34_full_experiment_record.md` (§5.14–5.15), `docs/35_local_event_first_plan.md`, `docs/36_multi_agent_pipeline_plan.md`, `src/local_event_first.py`, `src/multi_agent.py`, and run artifacts in `runs/local_event_first/` and `runs/multi_agent/`.*
