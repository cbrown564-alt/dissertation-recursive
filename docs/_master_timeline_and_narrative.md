# Master Timeline & Narrative Coherence Guide

**Purpose:** Reconstructed chronological order of experiments, dependencies between workstreams, and identified discontinuities worth revisiting. All phase documents should reference this timeline to maintain narrative coherence.

---

## Actual Chronology (May 5–12, 2026)

### May 5 — Project Inception
- Literature review matrix completed
- Project scaffold and documentation structure established
- Scope clarified to ExECTv2-native fields

### May 6 — Infrastructure & Baseline Verification
- **Milestone 3:** Direct baseline pipeline (S1/S2/S3) verified with stubs
- **Milestone 4:** Event-first pipeline (E1/E2/E3) verified with stubs
- **Milestone 5:** Evaluation harness artifact-gating verified
- **Milestone 7:** Secondary analyses (JSON vs YAML, local vs frontier, E2 vs E3) structurally verified under stubs
- **Milestone 8:** Write-up support infrastructure established
- **Robustness harness:** 7 perturbation types catalogued and pipeline verified
- Key infrastructure finding: system Python vs `.venv` issues resolved

**Narrative note:** All mechanical pipelines confirmed working before any API spend. This discipline saved significant budget later.

### May 7 — First Real Models & The Scoring Crisis
- **Stage A (Model Expansion):** First real-model calls on 15 dev docs. Frontier models tested: GPT-4.1-mini, GPT-5.5, GPT-5.4-mini, Claude Sonnet 4.6, Gemini 3.1 Flash/Pro.
  - Finding: benchmark quality tightly clustered (0.781–0.791)
  - GPT-4.1-mini selected as primary by cost-effectiveness
  - Gemini excluded due to quota/empty-response failures
- **Stage B:** Development pilot promotion criteria established
- **Stage C0:** Strict validation on 40 val docs — S2 (GPT-4.1-mini) and E2 selected
- **Recovery Phase 0–1 initiated:** After seeing suspiciously low scores (seizure type 0.187–0.261, medication full tuple 0.372–0.496, frequency 0.000), opened performance recovery programme rather than declare failure
  - Phase 0: Benchmark reconciliation (mapping Fang et al. tasks to local fields)
  - Phase 1: Failure localization — 725 errors classified into 8 categories
- **Recovery Phase 2–3 begun:** 
  - Scoring audit revealed gold-loader null-string bug (literal `"null"` treated as token)
  - Medication component scoring fixed (all-or-nothing → per-component F1)
  - ASM synonym expansion initiated
  - Collapsed label approach conceived for seizure type
- **Event-first aggregation refined:** Ranked candidate oracle analysis begun

**Critical narrative thread:** The scoring crisis emerged *simultaneously* with first real-model results. The original final_validation numbers were invalid — this realization retroactively changed the meaning of all Stage A–C results.

### May 8 — The Busiest Day: Local Models, Frequency, and Recovery Convergence
This was the day when three major workstreams ran in parallel and influenced each other:

**Morning — Local Models Workstream launched:**
- L0: Ollama connectivity confirmed
- L1: H0 strict canonical abandoned (>30 min/doc on qwen3.5:9b)
- L2: H4 json_mode validated (qwen3.5:9b/4b)
- L3: H6/H3/H7 comparison on 5 dev docs — H3 looked best on dev
- **Critical infrastructure fix:** Ollama native API rewrite (compat shim silently ignored `think: false`)
- L5 validation (5 then 40 docs): H3 underperformed on validation vs dev — first instance of the "dev-validation divergence" pattern
- N1: Seizure type gap investigation (40 docs) — `unknown seizure type` meta-label problem identified
- N2–N6 and variants: H6fs, H6v2, H6qa, H6ev tested on 40 val docs
- Large models: qwen3.6:27b and 35b validated
- **Finding:** Few-shot examples have model-specific effects (help qwen, harm gemma)

**Afternoon/Evening — Gan Frequency Workstream launched:**
- G0: Gold audit and metric lock
- G1: Prediction harness stub verification
- G2: 3 models × 4 harnesses sweep on 50 dev docs ($4.54)
  - GPT-5.5 + Gan_cot_label = 0.80 Pragmatic F1 (promoted)
  - Two-pass performed worst
- G3: Hard-case prompt development — few-shot examples *reduced* performance (same pattern as local models)

**Throughout — Recovery workstream completed:**
- P1: ASM synonym expansion (~22 → ~80 entries)
- P2: Collapsed seizure-type and epilepsy-type labels added to scorer
- P3: E2 diagnosis aggregation fix (`"epilepsy" in value` → `"epilept" in value`)
- Corrected metrics produced for validation and test splits
- Aggregation oracle completed (29.2% seizure frequency hard ceiling)
- Robustness testing on final validation/test
- H7 two-pass and D3 candidate+verifier evidence reconstruction implemented
- Relaxed projection (H3) tested on 15 dev docs

**Key discontinuity:** The local models and frequency workstreams were launched *before* the recovery scoring fixes were fully complete. Early local model numbers (L3-L5) were scored with the original broken scorer, then rescored. This means the "H3 looked great on dev" finding was actually measured with the old scorer — though the qualitative conclusion (dev-validation divergence) held after rescoring.

### May 9 — Frequency Retrieval & Final Evaluation Planning
- G4-Retrieval initial run (512 token limit) — GPT-5.5 parse failures due to reasoning token exhaustion
- G4-Fixed run planned with 2048 token limit
- Final full-field evaluation plan written
- Minimal frequency port plan for qwen35 local

**Learning continuity:** G4-Retrieval's failure directly built on the G2 finding that GPT-5.5 needs large output tokens. The 512 default that worked for GPT-4.1-mini failed for the reasoning model.

### May 10 — Gold Standard Deep Dive & Local Event-First Planning
- Gold label quality analysis (doc 28)
- Gold audit plan (29), results (30), qualitative analysis (31)
- G3 deep investigation (32)
- Gold audit synthesis (33)
- Local event-first plan written (35)
- Final full-field evaluation plan finalized (27)

**Narrative thread:** The gold audits were triggered by the recovery workstream's oracle findings. Once we knew 29.2% of frequency was unscoreable even with perfect extraction, we needed to understand *why*. This led to the qualitative review of annotation gaps.

### May 10–11 — Local Event-First Revisited
- **EL0:** Re-diagnosis — fixed Ollama native API used for H0 on qwen_9b (108s/doc, truncated) and qwen_35b (300s timeout)
  - Confirmed L1 abandonment was the thinking-token bug for qwen_9b, but 35B genuinely too slow for H0
  - EL_micro parse bug discovered (`extract_json_object` didn't handle arrays)
- **EL1:** Dev pilot (10 docs, 3 harnesses × 3 models)
  - Apparent gains: gemma_4b EL_micro +0.176 sz, qwen_35b EL_micro +0.099 sz, qwen_9b EL_E1E2 +0.094 sz
- **EL2:** Validation scale (40 docs)
  - All gains vanished or reversed
  - EL_micro: qwen_9b −0.064 vs H6fs, gemma_4b −0.087, qwen_35b −0.008
  - EL_E1E2: qwen_9b −0.008 vs H6fs

**Discontinuity analysis:** EL0–EL2 was a "revisit of abandonment." L1 was abandoned on May 8 because qwen_9b took >30 min. On May 10, we discovered this was the thinking-token bug, not genuine incapability. This created a natural experiment: if H0 is feasible, is event-first better? The EL2 result was negative, but the *process* of revisiting was itself informative. The narrative should make clear: we didn't randomly try event-first again; we fixed a root cause (thinking bug) that had poisoned the original conclusion, then retested.

### May 11 — Multi-Agent Pipeline & Final Frontier Harness Fixes
- **MA_v1 Multi-Agent:**
  - MA0: stub verification
  - MA1: dev pilot (10 docs) — strong results (GPT-5.4-mini BenchComp 0.898)
  - MA2: validation (40 docs) — failed promotion gates (BenchComp 0.757/0.772 vs gate 0.810)
  - MA3: GPT-5.5 validation (40 docs) — regressed further (BenchComp 0.650)
  - Multiple pre-fix and stage1-fix iterations visible in git history
- **H7/D3 Prompt Bug Discovery:**
  - Initial validation runs (May 11) showed medication_full_f1 ≈ 0.018 for both H7 and D3
  - Investigation: verifier prompt instructed to output flat `medication_names` (name + quote only), stripping dose/unit/frequency
  - Fix: changed verifier/normalize prompt to output structured medications with dose/unit/frequency
  - Reruns: medication_full_f1 recovered to ~0.60 (30–35× improvement)
  - Promotion decision: still not promoted (below E3 benchmark_quality)

**Major discontinuity:** H7 and D3 were explored in Stage E (May 7) and appeared promising. They were then left dormant while local models and frequency workstreams ran. On May 11, they were revisited for validation-scale runs, but the *initial* validation results were catastrophically bad due to a prompt bug — not an architectural limit. After fixing the bug, they recovered to competitive levels but still didn't beat E3. The narrative should show: (1) H7/D3 were promising in Stage E, (2) they were deprioritized for other work, (3) when revisited, a bug nearly killed them, (4) after fixing, they're viable but not best-in-class.

### May 11–12 — Final Documentation & Gold Tension Analysis
- Full experiment record written (doc 34)
- Clinical accuracy vs gold standard tension analysis (37)
- Gold standard quality audit HTML and markdown (38)

---

## Identified Discontinuities & Coherence Gaps

### Discontinuity 1: The Scoring Fix Changed History Retroactively
All Stage A–C results were originally scored with the broken scorer. After May 7–8 recovery, they were rescored. This means "Stage C0 selected S2 and E2" is technically correct but the *reasons* changed — originally S2 had med_name=0.842, sz_type=0.213; after correction, the same run had med_name≈0.85, sz_collapsed≈0.61. The phase documents should make clear that selection decisions were validated against corrected metrics, not the original broken ones.

### Discontinuity 2: Local Models Started Before Recovery Complete
Local model work began May 8 morning while recovery P2/P3 were still in progress. Early local results (L3-L5) used mixed scoring states. The `22_local_models_workstream.md` document was updated in the evening with completed results, suggesting the doc was revised as fixes landed.

### Discontinuity 3: H7/D3 Dormancy and Resurrection
H7 and D3 were tested on 15 dev docs in Stage E (May 7), showed strong results, then were not mentioned again until May 11 validation-scale runs. In between, local models and frequency dominated attention. The May 11 runs were motivated by `27_final_full_field_evaluation_plan.md` (May 10), which explicitly planned to revisit H7 and D3 at validation scale.

### Discontinuity 4: Event-First Abandoned, Then Revisited for Local
Event-first E1/E2/E3 was the *frontier* best system (E3 leads medication metrics). But for local models, L1 abandoned H0 (full schema) because it was too slow — and by extension, event-first (which also uses H0-like prompts) was assumed infeasible. The EL0–EL2 revisit was specifically motivated by the realization that the L1 slowness was the thinking-token bug. This is a coherent thread but doc 34 buries it.

### Discontinuity 5: Gan Frequency Ran in Parallel Without Cross-Pollination
The Gan workstream (G0–G4) ran almost entirely in parallel with ExECTv2 work. There was limited cross-pollination: Gan's retrieval-highlight approach was never tested on ExECTv2, and ExECTv2's evidence-grounding discipline was only partially ported to Gan. The frequency workstream was a "fresh start" on a different benchmark rather than an evolution of the ExECTv2 pipeline.

### Discontinuity 6: Multi-Agent as a "Hail Mary"
MA_v1 was conceived and implemented on May 11, after local direct models were finalized and local event-first was shown to be negative. It was a late attempt to find an architectural win. The multi-agent plan doc (36) was written May 11 morning, and all MA0–MA3 stages ran that same day. This was extremely fast turnaround — suggesting it was a targeted experiment rather than a major new direction.

---

## Cross-Cutting Dependencies

```
May 6: Infrastructure baseline (all pipelines work)
    ↓
May 7: Frontier model selection (Stage A–C0)
    ↓
May 7: Scoring crisis → Recovery initiated
    ↓
May 8: Recovery P1–P3 complete (metrics now valid)
    ├─→ May 8: Local direct models (uses corrected scorer)
    ├─→ May 8: Gan frequency launched (uses locked metric)
    └─→ May 7–8: H7/D3 explored, then dormant
        ↓
May 9: G4 retrieval planned; final eval plan written
    ↓
May 10: Gold audits (triggered by oracle findings)
    ├─→ May 10–11: Local event-first revisit (EL0–EL2)
    └─→ May 10: Final eval plan specifies H7/D3 revisit
        ↓
May 11: H7/D3 validation-scale runs + prompt bug fix
    ├─→ May 11: Multi-agent rapid experiment (MA0–MA3)
    └─→ May 11: Full experiment record compiled
        ↓
May 12: Gold tension analysis; synthesis
```

## Recommended Narrative Framing for Phase Docs

Each phase doc should explicitly answer:
1. **What did we know when we started?** (What previous phase(s) informed this one?)
2. **What did we try?** (Harnesses, models, data)
3. **What blocked us?** (Bugs, infrastructure, conceptual misunderstandings)
4. **What did we learn?** (Findings that propagate forward)
5. **What did we leave behind?** (Abandoned paths and why)
6. **What did we revisit?** (Paths that were resurrected and why)
