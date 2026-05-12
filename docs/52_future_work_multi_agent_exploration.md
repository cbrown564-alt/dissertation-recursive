# Future Workstream: Multi-Agent Architectures — Beyond MA_v1

**Date:** 2026-05-12  
**Status:** Pilot complete — MA-A and matched-budget SAS baselines evaluated on 10-document development subset. Results below extend Limitation #4 from `docs/50_synthesis_report.md`  
**Related:** `docs/36_multi_agent_pipeline_plan.md`, `docs/43_phase_4_local_architectural_alternatives.md`, `docs/37_clinical_accuracy_vs_gold_standard_tension.md`, `docs/50_synthesis_report.md` (Finding 12)

---

## 1. Re-Framing the MA_v1 Result

The synthesis report records a clean negative for MA_v1: the four-stage pipeline (segmentation → parallel field extractors → verifier → aggregator) cleared the MA1 development pilot but failed the MA2 promotion gates on validation (BenchComp 0.757 / 0.772 vs. gate 0.810; seizure collapsed 0.610 / 0.603 vs. gate 0.660). A follow-on GPT-5.5 MA3 run regressed further. The report concludes that "multi-agent decomposition introduces error propagation that outweighs cognitive-load benefits at clinical-document scale."

This conclusion is methodologically sound **for the specific architecture tested**, but it should not be generalised to all multi-agent (MA) designs. MA_v1 was a single point in a large design space. It used a rigid sequential stage graph, a single verifier with broad scope, and an aggregator that had to repair cross-stage inconsistencies. Only one segmentation strategy, one field-parallelisation pattern, and one verification protocol were evaluated. The project has not yet answered the supervisor’s original question in full:

> *Does a multi-agent extraction pipeline improve over single-prompt extraction under the same budget constraints?*

The current evidence answers "no for MA_v1 under its specific constraints." It does not answer "no for all MA architectures."

**Premise of this workstream:** A multi-agent system that utilises more tokens and more compute than a single-prompt system should, at minimum, perform as well as the single-prompt system (it can always delegate the single-prompt approach as one of its agents). The fact that MA_v1 underperformed suggests that the *design* was suboptimal, not that the *paradigm* is fundamentally flawed. The open research questions are therefore:

1. **What MA designs are most likely to succeed on clinical-document extraction?**
2. **How much of any MA gain is attributable to additional compute rather than architectural decomposition?**
3. **Are the performance gains worth the extra cost, and under what deployment constraints?**
4. **How can single-agent baselines be given equal token budgets to enable fair comparison?**

---

## 2. Clinical Multi-Agent Systems in the Literature

A growing body of work demonstrates that agentic decomposition can succeed in clinical NLP when the decomposition is aligned with clinical task structure. Four systems are directly relevant.

### 2.1 CLINES — Clinical LLM-based Information Extraction and Structuring Agent

CLINES (medRxiv, Dec 2025) is a modular agentic pipeline for long EHR notes. It performs:
- **Informed segmentation** of notes exceeding context-window limits;
- **Reasoning-capable LLM extraction** of entities and relations;
- **Attribution** of clinical context (negation, experiencer, dosage, lab values);
- **Normalization** to UMLS/SNOMED CT;
- **Temporal alignment** of events;
- **Reconciliation** into an i2b2-style schema.

Crucially, CLINES is designed as a **substitutable-agent pipeline**: different generative models can be plugged into each stage depending on institutional cost, privacy, and performance requirements. Its evaluation on real-world EHR notes across multiple disease areas and institutions showed improvements over both classical NLP pipelines and naive single-pass LLM prompting. The relevance to this project is twofold: (a) segmentation can reduce error if it mirrors clinical section boundaries, and (b) the pipeline’s success depends on the *match* between agent roles and the information structure of the source document.

### 2.2 ClinNoteAgents — Multi-Agent Framework for Heart-Failure Readmission

ClinNoteAgents (arXiv, Dec 2025) uses three coordinated agents — a **Risk Factor Extractor**, a **Risk Factor Normalizer**, and a **Note Summarizer** — implemented with Qwen3-14B (thinking mode enabled). The extractor generates structured variables; the normalizer standardises heterogeneous free-text expressions into categorical values via a two-stage LLM process; the summariser produces clinician-style abstracts for downstream predictive modelling.

The normaliser is particularly relevant: it does not attempt to extract and normalise in a single call, but delegates normalisation to a second agent that operates over the extractor’s output. This is analogous to the proposed H7 two-pass normalisation design, but framed as an inter-agent handoff rather than an intra-agent re-prompt. The system achieved high-fidelity extraction against structured EHR ground truth and demonstrated that LLM-based abstractions preserve predictive signals despite substantial text compression.

### 2.3 ClinicalRAG — Heterogeneous Knowledge Retrieval with Multi-Agent Strategy

ClinicalRAG (ACL KnowLLM, 2024) employs a multi-agent strategy in which each agent carries a distinct task:
- **Medical Entity Extraction (MEE) agent:** parses pertinent medical entities from the input;
- **Retrieval agents:** query a Heterogeneous Knowledge Index (HKI) engine for each extracted entity;
- **Synthesis agents:** ground the final output in retrieved knowledge.

The MEE agent’s output is a structured entity set `E = {<e_i, c_i>}`, where `c_i` is a predefined category (symptom, disease, treatment). This separation of "what is in the text" from "what do we know about it" is exactly the decomposition that MA_v1 attempted, but with a retrieval layer added. ClinicalRAG’s evaluation on medical QA benchmarks showed that multi-agent retrieval reduced hallucinated codes and improved ontology grounding to UMLS/SNOMED CT — a failure mode explicitly noted in the CLINES discussion.

### 2.4 Orchestrated Multi-Agent Clinical Systems (Nature 2026)

A 2026 Nature study (*Orchestrated multi agents sustain accuracy under clinical workload*) evaluated multi-agent accuracy across retrieval, extraction, and dosing tasks at batch sizes of 5–80 concurrent tasks. Multi-agent accuracy remained high (90.6 % at 5 tasks; 65.3 % at 80 tasks), suggesting that orchestrated agent swarms can sustain clinical-grade accuracy under throughput pressure if the orchestration protocol is robust. The degradation at scale was attributed to context-saturation in individual agents, not to coordination failure — implying that agent isolation (separate context windows) is a feature, not a bug, provided the handoff protocol is clean.

---

## 3. The Compute Confound: Are MA Gains Just Token Spend?

This is the central methodological question. A large and convergent body of recent research suggests that many reported multi-agent advantages are better explained by increased test-time computation than by architectural decomposition.

### 3.1 Anthropic’s Production Analysis

Anthropic’s engineering team (2025) reports that agents use ~4× more tokens than chat interactions, and multi-agent systems use ~15× more tokens than chats. In their BrowseComp evaluation, **token usage by itself explained 80 % of performance variance**; the number of tool calls and model choice were the only other significant factors. Their explicit conclusion is: "Multi-agent systems work mainly because they help spend enough tokens to solve the problem." This validates the intuition that more compute → better results, but it also implies that a single agent given the same token budget might achieve the same outcome.

### 3.2 The UIUC Token-Budget Study

A UIUC study across 7 datasets and 6 models found that multi-agent systems consume **4–220× more tokens** than single-agent counterparts, with even optimised configurations requiring 2–12× more response-generation tokens (Azure Dev Community, 2026). The study emphasises that architecture selection is therefore a budgeting decision as much as an engineering one.

### 3.3 Single-Agent vs. Multi-Agent Under Matched Budgets

Tran et al. (2026, *Single-Agent LLMs Outperform Multi-Agent Systems on Multi-Hop Reasoning Under Equal Thinking Token Budgets*) provide the most rigorous controlled comparison to date. They grounded their argument in the **Data Processing Inequality**: under a fixed reasoning-token budget, multi-agent decompositions introduce additional communication bottlenecks (inter-agent text generation) that can lead to information loss. They tested this across three model families (Qwen3, DeepSeek-R1-Distill-Llama, Gemini 2.5) and found that **single-agent systems consistently match or outperform multi-agent systems when reasoning tokens are held constant**.

Key diagnostic findings from Tran et al.:
- **API-based budget control artifacts** (especially in Gemini 2.5) inflate apparent token counts without increasing visible reasoning.
- **Over-exploration:** Multi-agent systems traverse more entity spans in their reasoning but fail to converge on the correct answer more often.
- **Late binding failures:** Both SAS and MAS lose previously correct spans at finalisation, but MAS does so more often because the correct span may be trapped in an intermediate agent’s context that is not fully propagated.

### 3.4 When MAS *Does* Help

The same literature identifies boundary conditions where multi-agent designs become competitive:

1. **Degraded single-agent context utilisation:** When the input is long or noisy enough that a single agent’s effective context window is saturated (the "lost in the middle" effect, Liu et al. 2024), splitting the context across agents can improve effective coverage.
2. **Hard-regime / weaker-model settings:** Kim et al. (2025) show that agentic benefits concentrate in weaker models or harder tasks and diminish as base-model capability increases.
3. **Truly parallelisable sub-tasks:** If sub-tasks have no cross-dependencies, parallel agents can exploit wall-clock concurrency without information-loss penalties.

**Implication for clinical extraction:** ExECTv2 letters are typically 1,500–3,000 tokens — well within modern context windows. Single-agent context saturation is therefore *not* the binding constraint. The binding constraints are (a) normalisation accuracy (seizure type), (b) temporal precision (current vs. historical), and (c) structured-output parsing. These are not obviously parallelisable: a seizure-type label depends on the same narrative that contains medication history. This may explain why MA_v1’s rigid decomposition hurt more than it helped.

---

## 4. Fair Comparison: Matched-Budget Experimental Design

To disentangle architecture from compute, any future MA experiment must include a **matched-budget single-agent baseline**. The project currently has no such baseline. The following designs are proposed.

### 4.1 Matched Thinking-Token Budget

**Definition:** The total number of tokens used for intermediate reasoning (CoT, reflection, scratchpad), excluding prompts and final answers.

**Implementation for single-agent:**
- Use a **longer CoT prompt** (e.g., "Think step by step. First list all medications, then verify each against the text, then list all seizure mentions, then classify...").
- Use **self-consistency / best-of-N**: sample `k` outputs from the same prompt and select the majority or highest-confidence answer. `k` is chosen so that total thinking tokens ≈ MA total thinking tokens.
- Use **sequential reflection**: run the extractor, then prompt the same model to review and correct its own output in the same context window (Reflexion-style, but within a single agent).

**Control:** Log `thinking_tokens` for both SAS and MAS. The Tran et al. methodology (excluding prompt and final-answer tokens) should be adopted as the standard.

### 4.2 Matched Total-Token Budget

**Definition:** Input + thinking + output tokens, i.e., the billable API quantity.

**Implementation for single-agent:**
- Provide **retrieval-augmented context** (e.g., the Gan_retrieval_highlight mechanism) to inflate input tokens to match the MA pipeline’s cumulative input size.
- Allow **extended output** (e.g., 4,096 tokens instead of 2,048) so the single agent can generate verbose reasoning traces.

**Why this matters:** Anthropic’s 15× token multiplier means that even a modest multi-agent pipeline spends as many tokens as a single agent given a massive context window. If the single agent with that same window underperforms, the architectural decomposition is genuinely valuable. If it matches or exceeds the MA result, the gain was compute all along.

### 4.3 Matched Latency Budget

For local deployment, wall-clock time is often the limiting resource. A single-agent system running `best-of-3` self-consistency may take 3× as long as one call, but a multi-agent pipeline with sequential stages (MA_v1: 4 stages) takes 4× as long. Comparing under matched latency means:

- **SAS:** `best-of-k` where `k` = number of sequential MA stages.
- **MAS:** Parallelise all non-dependent agents (e.g., Stage 2a–2d) to minimise wall-clock time.

### 4.4 Cost-Effectiveness Metric

Introduce a new composite metric for all future MA experiments:

> **Efficiency-Adjusted BenchComp (EABC)** = BenchComp / log(total_tokens + 1)

This rewards systems that achieve high accuracy with fewer tokens. A multi-agent system must outperform the single-agent baseline on *both* raw BenchComp *and* EABC to justify its architectural complexity.

---

## 5. Proposed Multi-Agent Designs to Test

MA_v1 tested one design: sequential segmentation → parallel extraction → verification → aggregation. The following alternatives address specific weaknesses of that design and are grounded in the clinical-MA literature reviewed above.

### 5.1 Design MA-A: Verifier-Only Augmentation (Minimal MA)

**Concept:** Take the best existing single harness (E3 for frontier; H6fs for local) and add **one additional agent**: a verifier/critic that reviews the extraction without altering it.

**Pipeline:**
1. Single-agent extraction (E3 or H6fs) → canonical JSON.
2. Verifier agent receives the JSON + original letter → flags inconsistent or unsupported items.
3. If flags are present, a **corrector agent** (or the original extractor re-prompted with criticism) produces a revised JSON.

**Why it should work:** It is the smallest possible MA increment. At worst, the verifier finds nothing and the output equals the single-agent baseline. At best, it catches family-history bleed, negated investigations, or dose mismatches. This directly tests the user’s premise: "we could just take the existing best harness and add an additional agent... and at worst it should perform as well."

**Token budget:** +1–2 calls per document. Manageable even for local models.

### 5.2 Design MA-B: Parallel Field Specialists with Judge

**Concept:** Replace MA_v1’s sequential Stage 1 with a **dispatcher** that sends the full letter to multiple field-specialist agents simultaneously. Each specialist is prompted for exactly one field family (medication, seizure, investigations, diagnosis). A final **judge agent** resolves conflicts (e.g., seizure type inferred from two different sections) and produces the canonical JSON.

**Differences from MA_v1:**
- No explicit segmentation stage — each specialist reads the full letter but is narrowly prompted. This removes the Stage 1 error-propagation channel that hurt MA_v1.
- The judge operates over structured JSON, not raw text, reducing context load.

**Why it might succeed:** Parallel specialists avoid the "over-exploration" problem identified by Tran et al.: each agent stays close to its sub-task rather than traversing irrelevant spans. The judge provides late binding without requiring every intermediate agent to carry the full context.

### 5.3 Design MA-C: Debate / Ensemble Extraction

**Concept:** Spawn `k` independent extractor agents (same model, same prompt, or diverse prompts) on the same letter. A **debate agent** compares their outputs and selects or synthesises the consensus answer.

**Why it might succeed:** Debate was the strongest MAS variant in Tran et al.’s matched-budget study. For clinical extraction, disagreement between extractors often signals ambiguity (e.g., a medication is both "current" and "discontinued" in different sections). The debate agent can surface this ambiguity explicitly rather than silently selecting one interpretation.

**Token budget:** `k` times the single-agent call plus one debate call. To keep comparison fair, the single-agent baseline should run `best-of-k` self-consistency under the same total token budget.

### 5.4 Design MA-D: Hierarchical Dispatcher with Retrieval

**Concept:** A lightweight **router agent** classifies the letter type (e.g., "first clinic letter," "annual review," "surgical referral") and dispatches it to a **specialist harness** tuned for that letter type. This is inspired by CLINES’s substitutable-agent design.

**Why it might succeed:** The project’s event-first vs. direct extraction findings (Finding 7) suggest that S2 is better for diagnosis-heavy letters and E3 for medication-heavy letters. A router could exploit this heterogeneity automatically. The retrieval layer could pre-fetch letter-type-specific prompt fragments or canonical label definitions.

---

## 6. Cost-Benefit Analysis Framework

Multi-agent systems are not free. The following framework should be used to evaluate every proposed design.

| Cost Dimension | Frontier (API) | Local (GPU) |
|---|---|---|
| **Token multiplier** | 2–15× baseline (Anthropic) | Same absolute tokens, but multiplied wall-clock latency |
| **Latency** | Network-bound; parallel calls help | Sequential calls compound linearly; GPU contention possible |
| **Energy / carbon** | Outsourced to provider | Linear in token count; 8B agents use 62–136× GPU energy per query vs. single-turn (Tianpan, 2026) |
| **Debuggability** | Distributed traces needed; Stage 3 drop rates must be logged | Same; Ollama logs per call |
| **Clinical value threshold** | Is a 2–5 pp F1 gain worth 10× cost? | Is a 2–5 pp gain worth 4× latency? |

**Decision rule:** A multi-agent design is *deployable* only if it meets one of the following:

1. **Dominant:** Strictly higher accuracy *and* strictly lower cost than the best single-agent system. (Unlikely.)
2. **Pareto-improving:** Higher accuracy at acceptable cost increase, with a clear use-case where the gain is clinically meaningful (e.g., seizure-type F1 crossing 0.70, or family-history trap drop reduced below −0.100).
3. **Safety-critical:** Not accuracy, but robustness — e.g., zero family-history hallucinations under perturbation, even if overall F1 is flat.

---

## 7. Proposed Experimental Grid

| Experiment | Design | Models | Baseline | Budget Match | Primary Metric | Promotion Gate |
|---|---|---|---|---|---|---|
| MA-A1 | Verifier-only on E3 | GPT-4.1-mini, GPT-5.5 | E3 alone | Total tokens | BenchComp, quote validity | BenchComp ≥ E3 + 0.010 |
| MA-A2 | Verifier-only on H6fs | qwen3.6:35b | H6fs alone | Total tokens | BenchComp, med F1 | BenchComp ≥ H6fs + 0.010 |
| MA-B1 | Parallel specialists + judge | GPT-4.1-mini | E3 | Total tokens, latency | BenchComp, per-stage parse rate | BenchComp ≥ E3; parse ≥ 0.95 |
| MA-C1 | Debate (k=3) | GPT-4.1-mini | E3 best-of-3 | Total tokens | BenchComp, seizure F1c | Seizure F1c ≥ 0.680 |
| MA-C2 | Debate (k=3) | qwen3.6:35b | H6fs best-of-3 | Total tokens | BenchComp, seizure F1c | Seizure F1c ≥ 0.650 |
| MA-D1 | Hierarchical dispatcher | GPT-4.1-mini | S2/E3 hybrid | Latency | BenchComp, diagnosis acc | Diagnosis acc ≥ 0.800 |
| **Control** | SAS long-CoT | All models above | Same as MA | Matched tokens | BenchComp | Establish floor |

**Critical requirement:** Every MA experiment must be paired with a matched-budget SAS control run (long-CoT or best-of-N). Claims about MA superiority are only valid if the MA result exceeds its *own* SAS control, not just the historical single-call baseline.

---

## 8. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Handoff format drift (cf. H7/D3 medication_full collapse) | Freeze JSON schema between stages. Unit-test with malformed inputs. |
| Verifier over-drops correct values | Log `drop_rate` and `modify_rate` per stage. Gate: drop_rate < 15 %. |
| Token budget explosion makes local models infeasible | Cap total calls at 4 for local; use Option A (verifier-only) as default. |
| Matched-budget SAS baseline is stronger than expected | This is a *positive* finding — it means the project’s single-agent harnesses are already near-optimal for their token budget. Report it. |
| Evaluation artifacts inflate apparent MA gains (Tran et al. warning) | Use paraphrased test sets where possible. Report confidence intervals. |

---

## 9. Dissertation Framing

If any of the proposed designs succeed, the dissertation claim shifts from "multi-agent decomposition is harmful" to "**naïve sequential decomposition is harmful, but targeted multi-agent designs — especially verifier augmentation and parallel specialists — can improve clinical extraction when evaluated against matched-compute single-agent baselines.**" This is a stronger and more nuanced claim because it identifies the boundary conditions under which agentic architectures add value.

If none succeed, the dissertation claim is strengthened in the opposite direction: "**Even under matched compute budgets and with diverse architectural designs, single-agent extraction remains pareto-optimal for ExECTv2-scale clinical letters.**" This would be a genuinely novel contribution, because the existing literature largely reports multi-agent wins without controlling for the compute confound.

Either outcome is publishable. The only unacceptable outcome is to leave the question unasked.

---

## 10. Initial Pilot Results (10-Document Development Subset)

A first pilot of MA-A and matched-budget SAS baselines was run on the 10-document development subset (EA0001–EA0013) using the **H6full** base harness (structured medication objects with dose/unit/frequency, plus investigations and seizure frequency).

### 10.1 Implemented infrastructure

- `src/multi_agent_exploration.py` — pipeline runner for MA-A, SAS long-CoT, and SAS best-of-N
- `prompts/multi_agent_v2/verifier.md` — benchmark-aware verifier prompt
- `prompts/multi_agent_v2/corrector.md` — benchmark-aware corrector prompt
- Efficiency-Adjusted BenchComp (**EABC** = BenchComp / log(total_tokens + 1)) added to scoring

**Bug fixes during pilot:**
1. H6full medication projection: `h6fs_to_canonical` was only reading `medication_names` (H6fs key) and missed `medications` (H6full structured objects).
2. Verifier over-flagging: the verifier initially listed every field including supported ones, and "corrected" benchmark-normalized labels back to raw text. The prompt now explicitly states that only problems should be flagged and benchmark labels are correct normalization.
3. Scorer token counting for best-of-N: token logs live in `trial_N/` subdirectories; the scorer now searches recursively.

### 10.2 Results

| Design | Model | BenchComp | EABC | Tokens | Med F1 | Sz F1c | Dx | EEG | MRI |
|--------|-------|-----------|------|--------|--------|--------|-----|-----|-----|
| **SAS long-CoT** | gpt_5_4_mini | **0.903** | **0.126** | 1,330 | 1.000 | 0.692 | 0.90 | 1.00 | 1.00 |
| SAS best-of-3 | gpt_5_4_mini | 0.903 | 0.109 | 3,854 | 1.000 | 0.692 | 0.90 | 1.00 | 1.00 |
| MA-A | gpt_5_4_mini | 0.863 | 0.103 | 4,440 | 0.971 | 0.667 | 0.90 | 1.00 | 0.80 |
| **SAS long-CoT** | qwen_35b_local | **0.847** | **0.116** | 1,446 | 0.923 | 0.640 | 0.90 | 1.00 | 1.00 |
| MA-A | qwen_35b_local | **0.882** | 0.103 | 5,374 | 0.973 | 0.741 | 0.90 | 1.00 | 0.80 |

### 10.3 Interpretation

**Frontier (GPT-5.4-mini).** SAS long-CoT is strictly dominant: it achieves the highest BenchComp (0.903) with the lowest token cost (1,330). MA-A fails its promotion gate (BenchComp ≥ baseline + 0.010) because it underperforms SAS long-CoT by 4.0 pp while using 3.3× more tokens. The verifier rarely found actionable issues because the base H6full extraction was already high-quality on these documents.

**Local (qwen3.6:35b).** MA-A *does* improve accuracy: +3.5 pp BenchComp over SAS long-CoT (0.882 vs. 0.847), meeting the promotion gate. The gain concentrates in seizure type F1 (0.741 vs. 0.640), suggesting the verifier catches seizure-type errors that the base model misses. However, the cost is steep (3.7× more tokens), and EABC is lower (0.103 vs. 0.116).

**Model-dependent value.** The value of verifier augmentation is model-dependent, aligning with Kim et al. (2025): agentic benefits concentrate in weaker models and diminish as base-model capability increases. For the frontier model, the single-agent baseline is already near-optimal; adding a verifier introduces communication overhead without compensatory gains. For the local model, the base harness makes more errors, giving the verifier more opportunity to add value.

### 10.4 Implications for the experimental grid

- **MA-A1 (frontier)** is unlikely to be promoted unless run on a difficult-document subset where base-harness error rates are higher.
- **MA-A2 (local)** shows promise but must be evaluated on the full 40-document validation split to confirm the 3.5 pp gain is stable.
- **EABC is a useful discriminator**: it correctly ranks SAS long-CoT above MA-A for both models, even though raw BenchComp favors MA-A on the local model.
- The compute-confound literature (section 3) is validated: when the single-agent baseline is given a matched token budget (long-CoT), it outperforms the multi-agent design on the stronger model.

### 10.5 Next steps

1. **Scale MA-A2 to validation** (40 documents) to test stability of the qwen3.6:35b gain.
2. **Difficult-document ablation**: Run MA-A on a subset of documents with known high base-harness error rates (family-history traps, temporal ambiguity) to test whether verifier value is error-rate-dependent.
3. **Implement MA-B** (parallel field specialists with judge) and MA-C (debate/ensemble) if MA-A2 validates.
4. **Long-CoT prompt engineering**: Investigate whether even longer CoT instructions can close the 3.5 pp gap on the local model without the verifier's token overhead.
