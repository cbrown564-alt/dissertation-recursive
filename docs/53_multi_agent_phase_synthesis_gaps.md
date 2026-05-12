# Multi-Agent Exploration: Key Learnings Missing from MA_v2 Design

**Date:** 2026-05-11  
**Status:** Analysis complete — recommendations for MA-A2 scaling and MA-B/C/D design  
**Scope:** Cross-reference `docs/52_future_work_multi_agent_exploration.md` and `src/multi_agent_exploration.py` against Phases 1–6  

---

## Executive Summary

The MA_v2 pilot (§10 of Doc 52) and its implementation (`src/multi_agent_exploration.py`, `prompts/multi_agent_v2/`) are methodologically sound at the literature-review level, but they fail to incorporate at least **sixteen concrete findings** from the preceding six phases that would materially change the design of agents, prompts, evaluation gates, and claims. This document catalogs those gaps and prescribes targeted fixes before MA-A2 scales to validation or MA-B/C/D are implemented.

The gaps cluster into five areas:
1. **Prompt design** — what the base extractor and verifier are actually told to do
2. **Normalization and scoring alignment** — how the verifier's notion of "correct" relates to the corrected scorer
3. **Model-specific harness effects** — which architectures work for which models
4. **Temporal scope and gold-standard realism** — what a "better" extraction actually looks like against ExECTv2
5. **Infrastructure and budget discipline** — token budgets, latency, and silent failure modes

---

## 1. Phase 1 (Frontier Selection) — Missing in MA_v2

### 1.1 The H7/D3 two-pass architecture already tested verifier-like decomposition

**Finding:** H7 (extract-then-normalize) achieved seizure_type F1 = 0.698 on development — a 37% relative improvement over H0 — by separating *clinical fact extraction* (Pass 1) from *benchmark label mapping* (Pass 2). D3 (candidate+verifier) achieved the highest overall quality (0.846) of any Phase 1 condition. Both are already verifier-augmented designs.

**Gap in MA_v2:** Doc 52 treats MA-A as a novel "verifier-only" idea, but H7 and D3 *are* verifier-augmented pipelines. The MA-A pilot uses a generic verifier prompt that does not replicate the H7/D3 design moves that actually worked:
- H7 Pass 1 explicitly asks for `current_patient_fact=true/false` — temporal scope is resolved at extraction time, not retrofitted
- H7 Pass 2 operates over *rich facts* with quotes, not a projected canonical JSON — this preserves provenance
- D3 Pass 2 (verifier) has an explicit closed-world label constraint that the candidate extractor did not have

**Fix for MA-A2 / MA-B:**
- The verifier should receive the *raw extraction output* (rich facts or candidate list), not the projected canonical JSON. Canonical projection destroys information the verifier needs.
- The corrector should use a closed-world label block (as D3 did), not an open-ended "fix it" instruction.

### 1.2 Evidence-later (H8) underperformed evidence-at-extraction (H7)

**Finding:** H8 removed evidence constraints from Pass 1 and retrofitted them in Pass 2. It underperformed H7 (0.806 vs 0.835). The lesson: **evidence grounding must be enforced at the point of extraction, not retrofitted.**

**Gap in MA_v2:** The corrector prompt (`prompts/multi_agent_v2/corrector.md`) instructs the model to "Preserve schema structure" with empty evidence fields. This is H8-style evidence-later. There is no mechanism to require evidence quotes from the corrector.

**Fix:** If the corrector changes a field, it must also supply a verbatim evidence quote. The corrector prompt should explicitly require `evidence_quote` for any modified field.

### 1.3 Prompt bug sensitivity: one wording change caused 30–35× metric collapse

**Finding:** The May 11 H7/D3 validation runs showed that changing the verifier prompt from structured `medications` objects to flat `medication_names` strings dropped medication_full_f1 from ~0.60 to 0.018 — a 33× collapse. This was not an architectural failure; it was a prompt contract failure.

**Gap in MA_v2:** The verifier prompt (§10.1, bug fix #2) mentions that the verifier "corrected benchmark-normalized labels back to raw text." But there is no unit-test or schema-gate that prevents the corrector from emitting flat strings instead of structured objects. The `h6fs_to_canonical` projection had to be patched during the pilot for the same reason.

**Fix:** Before any MA experiment scales, add a **contract freeze test**: run the verifier+corrector on 5 manually constructed malformed inputs and assert that the output schema is valid. This is Milestone 5 discipline from Phase 1.

### 1.4 The E3 event-first base harness is not the best base for all fields

**Finding:** On validation, E3 leads medication metrics (0.872 name, 0.707 full) but S2 leads test-split diagnosis accuracy (0.850). The "best single harness" is field-dependent.

**Gap in MA_v2:** MA-A uses a single base harness (H6full or E3). Doc 52 §5.4 proposes MA-D (hierarchical dispatcher) as a future idea, but does not connect it to the already-known field-dependent performance landscape.

**Fix:** MA-A should report *per-field* promotion gates, not just BenchComp. If the verifier improves seizure type but harms diagnosis, that is a meaningful finding — especially given that E3 already leads medication and S2 leads diagnosis.

---

## 2. Phase 2 (Measurement Recovery) — Missing in MA_v2

### 2.1 The corrected scorer uses collapsed labels and ASM synonyms — verifier should too

**Finding:** The largest single improvement in the entire project (3× seizure-type F1 jump) came from scorer-side normalization: collapsed labels and ASM synonym expansion. These are *not* model capabilities; they are measurement alignments.

**Gap in MA_v2:** The verifier prompt mentions that "benchmark-normalized labels are CORRECT" but does not explicitly arm the verifier with the same collapsed-label dictionary and ASM synonym list that the scorer uses. The verifier is therefore evaluating "correctness" against a different standard than the scorer.

**Specific example:** The verifier prompt says:
> "focal epilepsy" for "right temporal lobe epilepsy" = CORRECT

But it does not say:
> "focal seizure" for "focal impaired awareness seizure" = CORRECT  
> "sodium valproate" for "Keppra" = INCORRECT (should be levetiracetam)  
> "sodium valproate" for "Depakote" = CORRECT

**Fix:** Inject `BENCHMARK_SEIZURE_LABELS`, `BENCHMARK_EPILEPSY_LABELS`, and `ASM_SYNONYMS` directly into the verifier prompt, exactly as H6 does for the base extractor. The verifier and the scorer must share the same normalization worldview.

### 2.2 Per-component medication scoring — verifier flags should be component-specific

**Finding:** Medication full-tuple F1 is the harmonic mean of name, dose, unit, and frequency component scores. A single missing dose does not zero the entire tuple.

**Gap in MA_v2:** The verifier prompt treats a medication as a monolithic item: "Flag only historical/stopped/planned... medications." It does not distinguish between "name is wrong" (severe) and "frequency says 'bd' instead of 'twice daily'" (normalization match, not an error).

**Fix:** The verifier should emit component-level flags:
```json
{"field_path": "fields.current_anti_seizure_medications[0].frequency", "issue": "normalization_gap", "reason": "'bd' is equivalent to 'twice daily' under scorer normalization", "suggested_fix": "none"}
```

### 2.3 The `unknown seizure type` meta-label is a structural ceiling, not a fixable error

**Finding:** 13–15 out of 26 documents with this gold label are missed consistently across all models (4B–35B) and all harnesses. No prompt improvement in Phase 3 closed this gap.

**Gap in MA_v2:** The verifier prompt instructs: "'unknown seizure type' is valid when supported." This implies the verifier should *defend* the meta-label against base-extractor over-inference. But the base extractor (H6full/H6fs) is already the component that decides whether to infer or abstain. If the base extractor outputs `focal seizure`, the verifier reviewing the source letter may well agree that inference is clinically reasonable — and the gold standard will still penalize it.

**Fix:** The verifier prompt should explicitly acknowledge the structural ceiling:
> "If the letter describes ambiguous episodes without a clear seizure type, the benchmark may expect 'unknown seizure type'. However, if the base extractor has inferred a specific type from clinical context, do NOT flag this as an error unless the inference is clinically absurd."

More importantly: **Do not count `unknown seizure type` disagreements as verifier value.** They are noise.

### 2.4 Temporal flatness in the gold standard punishes clinical precision

**Finding:** The gold standard annotates historical seizure mentions as current (Example 5 in guidelines). A temporally precise extractor that outputs `seizure free` when the letter says "seizure free for 18 months" receives F1 = 0.0 if the gold contains the historical type.

**Gap in MA_v2:** The verifier prompt's Rule 3 says: "Flag only types from family history, historical sections, or inferred types." This instructs the verifier to enforce temporal discrimination — which **lowers** F1 against the temporally flat gold. Doc 37 (Clinical Accuracy vs Gold Standard Tension) documents this explicitly: a "better" pipeline can score worse.

**Fix:** The verifier should be benchmark-aware: it should know that the gold is temporally flat and should NOT flag historical-as-current unless the letter explicitly states the patient is seizure-free. The promotion gate for MA-A should use a **temporally-adjusted seizure-type metric** alongside the raw metric.

---

## 3. Phase 3 (Local Direct) — Missing in MA_v2

### 3.1 H6full already incorporates structured medications and seizure-type guidance

**Finding:** H6full outputs structured medications (dose/unit/frequency), includes few-shot examples, and has explicit temporality restriction and `unknown seizure type` guidance. H6fs outputs flat `medication_names` only.

**MA gap:** H6full was used in the pilot and is the correct base harness. It subsumes the key H6fs learnings — few-shot examples with structured medications and temporality guidance. **MA-A2 on qwen_35b_local should continue to use H6full as the base harness.**

### 3.2 Model-specific harness effects: few-shot helps qwen, harms gemma

**Finding:** H6fs improved qwen3.5:9b (+6.1pp seizure F1) but regressed gemma4:e4b (−3.2pp). The model-specific harness effect is one of the dissertation's most important findings.

**Gap in MA_v2:** Doc 52 plans MA-A2 on qwen_35b_local, which is appropriate (qwen benefits from guidance). But MA-B/C/D are proposed as generic designs without model-specific prompt variants.

**Fix:** Any multi-agent design that adds schema richness (parallel specialists, debate, hierarchical dispatcher) must be tested against **gemma's schema-extension aversion**. If the specialist prompt is richer than H6, gemma will parse-fail. The experimental grid should include a "schema-minimal" variant for gemma.

### 3.3 H7 two-pass had 7–8× latency with no quality gain locally

**Finding:** On local models, H7 added 7–8× latency versus H6 with no measurable quality improvement. Multi-pass overhead is punishing at local inference speed.

**Gap in MA_v2:** Doc 52 §4.3 proposes matched-latency budgets but does not internalize just how severe sequential-stage latency is for local models. MA-A on qwen_35b_local already uses 3.7× more tokens than SAS long-CoT. At local GPU speed, this could mean 3–4× wall-clock time per document.

**Fix:** For local models, the latency budget is often the binding constraint. MA-A2 on qwen_35b_local should report **wall-clock latency per document**, not just token counts. If MA-A takes >45s/doc, it is not deployable regardless of accuracy.

### 3.4 Schema-extension aversion generalizes across pipelines

**Finding:** gemma4 refused H6qa, H6ev, EL_E1E2, and EL_compact — any schema richer than plain H6. Parse success dropped to 2/10 for EL_E1E2.

**Gap in MA_v2:** MA-B (parallel field specialists) proposes "each specialist is prompted for exactly one field family." If those prompts include structured JSON schemas, gemma will fail. MA-C (debate/ensemble) and MA-D (hierarchical dispatcher) similarly assume rich structured outputs from subsidiary agents.

**Fix:** Before building MA-B/C/D, test whether the proposed specialist prompt parses on gemma4:e4b with 100% success. If not, the design is not generalizable across the local model families the dissertation covers.

---

## 4. Phase 4 (Local Architectural Alternatives) — Missing in MA_v2

### 4.1 MA_v1 failed because of four specific error-propagation channels

**Finding:** MA_v1's four-stage pipeline failed its promotion gate because:
1. Segmentation errors poisoned downstream extractors
2. Parallel extractors disagreed on temporality
3. Verifier over-pruned (conservative keep/drop)
4. Aggregator had to reconcile conflicts without seeing the original letter

**Gap in MA_v2:** Doc 52 §3.6 acknowledges these failure modes in the literature review but does not harden the new designs against them.

**Specific hardening missing:**
- **No segmentation stage in MA-A?** Good — but MA-B reintroduces "specialists" reading the full letter. This is safer than MA_v1's segmentation, but the "judge" agent in MA-B must resolve cross-section contradictions — exactly the MA_v1 aggregation problem.
- **Verifier over-drops are not gated in code.** The `drop_rate` and `modify_rate` are computed but there is no abort logic: if drop_rate > 15%, the corrector should not run.
- **Corrector does not see original letter context for unflagged fields.** Rule 1 says "Preserve all unflagged fields exactly as they were." But if the base extractor made a temporally subtle error that the verifier missed, the corrector cannot catch it.

**Fix:** Add an **aggregation-oracle checkpoint** to MA-A: for 5 documents, manually construct the "best possible" extraction and measure whether the verifier+corrector can reach it. If the oracle is unreachable because the corrector lacks context, the design is MA_v1-style aggregation-loss all over again.

### 4.2 Dev-pilot gains reversed at validation scale

**Finding:** EL1 dev-pilot gains of +0.176, +0.099, and +0.094 all reversed or vanished at EL2 validation. The 10-document pilot was misleading.

**Gap in MA_v2:** The MA-A pilot in §10 is on the same 10-document development subset (EA0001–EA0013). The local qwen result (0.882 BenchComp) looks promising, but the EL1 experience says 10-document gains are noise.

**Fix:** Do not promote MA-A2 based on a 3.5 pp gain on 10 documents. Run on the full 40-document validation split before any claims about verifier value. The experimental grid (§7) already says this; the narrative in §10.4 should be more skeptical.

### 4.3 "Product of stage accuracies is punishing"

**Finding:** A four-stage pipeline with 95% stage accuracy has 0.95⁴ ≈ 81% end-to-end accuracy. MA_v1 demonstrated this empirically.

**Gap in MA_v2:** MA-A adds two stages (verifier + corrector) to a base harness. If the base is already 95% accurate and the verifier catches 50% of the 5% errors but introduces 2% new errors, the net is: 95% + (5% × 50% × 98%) − 2% ≈ 95.5%. The gain is tiny and easily lost to noise.

**Fix:** The verifier must be evaluated with **error-rate-conditional analysis**: on documents where the base extractor is correct, what does the verifier do? On documents where the base extractor is wrong, does the corrector fix it? The pilot reports aggregate numbers, not conditional numbers.

---

## 5. Phase 5 (Gan Frequency / Retrieval) — Missing in MA_v2

### 5.1 Retrieval-highlight is the strongest augmentation found in the entire project

**Finding:** Gan_retrieval_highlight achieved 0.840 Pragmatic F1, +8pp over the best non-retrieval harness. The retrieval mechanism highlights frequency-relevant spans before extraction.

**Gap in MA_v2:** Doc 52 §5.4 proposes MA-D (hierarchical dispatcher with retrieval) but does not connect it to the G4 finding that retrieval *alone* (without routing) provides the largest measured gain of any prompt augmentation in the project.

**Fix:** Before building MA-D, implement a **retrieval-only MA variant**: retrieve clinically relevant spans (medication mentions, seizure descriptions, diagnosis phrases) and prepend them as highlighted context to a single-pass extractor. This is lower complexity than MA-D and has empirical support from Phase 5.

### 5.2 Retrieval-only ablation: retrieved spans are cues, not sufficient context

**Finding:** Retrieval-only (no extraction instruction) scored 0.520 — 32pp below retrieval-highlight. The extraction instruction does the work; retrieval primes attention.

**Gap in MA_v2:** MA-D's retrieval layer is described as "pre-fetch letter-type-specific prompt fragments or canonical label definitions." This sounds like retrieval-only (context replacement), not retrieval-highlight (context augmentation).

**Fix:** The retrieval layer must *augment* the full letter, not replace it. The prompt should contain both the full source text and the highlighted spans. This is exactly what Gan retrieval_highlight did.

### 5.3 Hard-case few-shot examples actively harmed performance

**Finding:** Gan_fs_hard reduced Pragmatic F1 from 0.80 to 0.64. Adding examples for specific hard patterns harmed easy-majority performance. This replicated the Phase 3 gemma4/H6fs regression.

**Gap in MA_v2:** MA-B proposes "field-specialist agents" that are "narrowly prompted." If those narrow prompts include hard-case guidance (as H6fs does), they may harm the specialist's performance on routine cases.

**Fix:** Field specialists should use *minimal* closed-label constraints (like H6), not hard-case few-shot examples (like H6fs). The few-shot guidance, if any, belongs at the base-extractor level where it has been validated (H6fs for qwen, plain H6 for gemma).

### 5.4 512-token output budget is silently catastrophic for reasoning models

**Finding:** GPT-5.5 consumed its entire 512-token budget on internal reasoning, producing empty outputs. The fix was `--max-output-tokens 2048`.

**Gap in MA_v2:** `_call_model` in `src/multi_agent_exploration.py` defaults to `max_tokens=512` for the base extraction and `max_tokens=1024` for verifier/corrector. For GPT-5.5 (a reasoning model), 1024 may still be insufficient if the verifier generates extensive CoT before outputting JSON.

**Fix:** Add model-specific token budgets. For reasoning models (GPT-5.5, o3, etc.), verifier/corrector should use `max_tokens=2048`. Better yet, log `reasoning_tokens` separately from `output_tokens` and alarm if reasoning > 50% of budget.

---

## 6. Phase 6 (Gold Standard Quality) — Missing in MA_v2

### 6.1 The four clinical-validity criteria should be built into verifier design

**Finding:** Doc 37 proposes four criteria for valid extraction even when gold mismatches:
1. Semantic equivalence under domain normalization
2. Temporal correctness relative to letter
3. Granularity match to task requirements
4. Evidence presence (verbatim quote)

**Gap in MA_v2:** The verifier prompt evaluates against benchmark alignment (Rule 5) but does not explicitly implement these four criteria. It treats the gold standard as the arbiter of correctness, when Phase 6 showed that clinical accuracy often exceeds gold-string accuracy.

**Fix:** Rewrite the verifier prompt to evaluate against the four criteria, not just benchmark labels. Example addition:
> "If the base extractor says 'focal impaired awareness seizure' and the gold says 'focal seizure', this is a GRANULARITY MATCH, not an error. Do not flag."

### 6.2 Split-dose ambiguity should not be flagged

**Finding:** 10.8% of documents have split-dose prescriptions that the schema cannot represent cleanly. The gold annotates them as overlapping entries.

**Gap in MA_v2:** The verifier prompt says nothing about split-dose. If the base extractor outputs one medication tuple for "500mg morning, 250mg evening" and the gold expects two, the verifier may flag this as a missing dose.

**Fix:** Add an explicit rule: "Split-dose prescriptions (e.g., '500mg mane, 250mg nocte') may be extracted as one or two medication entries. Do not flag either representation as incorrect."

### 6.3 Seizure-frequency claims belong on Gan, not ExECTv2

**Finding:** 29.2% oracle failure rate on ExECTv2 frequency. The field is unscoreable.

**Gap in MA_v2:** The BenchComp composite in `src/multi_agent_exploration.py` does not include frequency. Good. But the verifier prompt does not explicitly exclude frequency from its scope — it just omits it from the example rules.

**Fix:** Explicitly state in verifier and corrector prompts: "Do not evaluate seizure_frequency. This field is not benchmark-reliable on ExECTv2."

---

## 7. Code-Level Gaps in `src/multi_agent_exploration.py`

### 7.1 Best-of-N selector uses naive heuristic, not scoring

**Finding:** `run_sas_best_of_n` selects the "best" trial by `(schema_valid, field_count, tokens)`. Field count is a poor proxy for accuracy. A trial that hallucinates extra medications will have a higher field count than a correct trial.

**Gap:** There is no self-consistency mechanism (majority vote) as proposed in Doc 52 §4.1. The "best-of-N" is really "biggest-of-N."

**Fix:** Implement true self-consistency: extract medication names, seizure types, and diagnosis from each trial; select the most frequent answer per field (Plurality voting). This aligns with the Tran et al. matched-budget methodology.

### 7.2 Long-CoT prompt is generic, not field-sequenced

**Finding:** H7's Pass 1 prompt sequences extraction explicitly: "First list all medications... Then identify current seizure status and types... Then determine diagnosis..." This reduced cognitive load.

**Gap:** `run_base_h6fs` with `long_cot=True` prepends a generic "Think step by step..." paragraph. It does not sequence the fields.

**Fix:** Use the H7 step sequence in the long-CoT prompt. The exact text from Phase 1 §3.5 should be adopted.

### 7.3 No token-budget alarm for reasoning models

**Finding:** GPT-5.5 silently failed when reasoning consumed the output budget.

**Gap:** `_call_model` logs token usage but does not alarm if `output_tokens == max_tokens` (budget exhaustion).

**Fix:** After each call, if `response.token_usage.output_tokens >= max_tokens - 10`, log a warning and mark the response as potentially truncated. This would have caught the G2/G4 GPT-5.5 failures.

### 7.4 Verifier does not receive the same label blocks as the base extractor

**Finding:** H6 prompts dynamically append `BENCHMARK_SEIZURE_LABELS` and `BENCHMARK_EPILEPSY_LABELS`.

**Gap:** `build_verifier_prompt` reads `verifier.md` but does not append the label blocks.

**Fix:** Append the allowed-label blocks to the verifier prompt, exactly as H6 does.

---

## 8. Recommended Priority Order

| Priority | Fix | Affects | Effort |
|---|---|---|---|
| **P0** | Scale MA-A2 to 40 validation docs before any claims | MA-A2 | 1 run |
| **P0** | Use **H6full** as base harness (already has structured meds + few-shot) | MA-A2 | Config |
| **P1** | Inject collapsed-label blocks + ASM synonyms into verifier prompt | MA-A, MA-B | Prompt edit |
| **P1** | Add component-level medication flags to verifier | MA-A | Prompt edit |
| **P1** | Require evidence quotes from corrector for any modified field | MA-A | Prompt + schema edit |
| **P1** | Implement true self-consistency (plurality vote) in best-of-N | SAS baseline | Code |
| **P2** | Add model-specific max_token budgets (2048 for reasoning models) | All MA | Code |
| **P2** | Add token-budget-exhaustion alarm | All MA | Code |
| **P2** | Add contract-freeze unit tests for verifier+corrector | All MA | Tests |
| **P2** | Report per-field promotion gates, not just BenchComp | Evaluation | Code |
| **P3** | Test retrieval-highlight as a standalone MA variant before MA-D | MA-D precursor | New design |
| **P3** | Evaluate conditional accuracy (base-correct vs base-wrong) | MA-A analysis | Analysis |

---

## 9. Dissertation Narrative Implications

If these gaps are addressed, the multi-agent story becomes more tightly integrated with the rest of the dissertation:

1. **MA-A is not a new idea** — it is a generalization of H7/D3 verifier architectures from Phase 1, now tested under matched-compute conditions.
2. **The verifier's value is model-dependent and error-rate-dependent** — this connects the Kim et al. (2025) finding (Phase 3) to the MA results.
3. **Retrieval-highlight should be tested before complex orchestration** — the Gan workstream (Phase 5) already found the strongest augmentation; MA-D should build on it.
4. **Gold-standard realism limits what any architecture can achieve** — Phase 6 findings bound the claims. A verifier cannot fix a 13.3% oracle ceiling or a temporally flat gold.

The dissertation claim should therefore be:
> "Targeted verifier augmentation (MA-A) can improve clinical extraction for weaker models under matched-compute evaluation, but the gain is bounded by the base extractor's error rate and the gold standard's structural ceilings. Complex orchestration (MA-B/C/D) is not justified unless retrieval-highlight and self-consistency baselines are first shown to be insufficient."

This is a stronger, more defensible claim than either "multi-agent is harmful" or "multi-agent might help."
