# Synthesis Report: Cross-Cutting Findings & Deployment Recommendations

**Date:** 2026-05-12  
**Scope:** All experimental phases: Frontier Selection (1), Recovery (2), Local Direct (3), Local Alternatives (4), Frequency (5), Gold Analysis (6).  
**Purpose:** Integrate findings into coherent dissertation claims, specify authoritative numbers, and recommend deployment configurations.  
**Status:** Final. Supersedes all prior synthesis documents.

---

## 1. How to Read This Document

This synthesis is built on six phase documents, each of which explores a specific experimental path in depth. This document does not repeat those depths; instead, it extracts the findings that cross-cut multiple phases and identifies the coherent story they tell together.

The narrative structure follows the actual project timeline:
1. We built infrastructure and selected frontier models.
2. We discovered our measurements were broken and fixed them.
3. We showed local models could match frontier performance at zero cost.
4. We tested complex alternatives and found simplicity wins.
5. We solved frequency normalization on a purpose-built benchmark.
6. We audited the gold standard and learned that many "errors" were benchmark artifacts.

Each finding below references the phase document(s) that support it.

---

## 2. Finding 1: The Scorer Was Materially Broken for the First Half of the Project

**Sources:** Phase 2 (§5), Phase 1 (§6.1), Phase 3 (§12.1)

The original `final_validation` medication full tuple F1 (0.386/0.343/0.400) understated true performance by **70–85% relative**. Original seizure frequency = 0.000 was a gold-loader bug. Original seizure type F1 = 0.187–0.200 was a taxonomy mismatch.

**Any claim or conclusion drawn before Phase 2+3 corrections must be treated with suspicion.** The scoring repair — particularly the gold-loader null-string fix, the ASM synonym expansion, and the collapsed label approach — is itself a dissertation methods contribution demonstrating that metric design and gold data quality are as important as model selection.

**Authoritative numbers (corrected scorer only):**

| Split | System | Med Name | Med Full | Sz Strict | Sz Collapsed | Freq Loose | EEG | MRI | Dx Acc | Dx Collapsed | Schema | Quote |
|-------|--------|----------|----------|-----------|--------------|------------|-----|-----|--------|--------------|--------|-------|
| val | S2 | 0.852 | 0.655 | 0.431 | **0.610** | 0.075 | 0.950 | 1.000 | 0.725 | 0.700 | 1.000 | 0.991 |
| val | E3 | **0.872** | **0.707** | 0.396 | **0.633** | 0.125 | **0.975** | **0.975** | **0.775** | **0.725** | 1.000 | **0.994** |
| test | S2 | **0.885** | **0.769** | 0.349 | 0.415 | 0.175 | **0.975** | 0.900 | **0.850** | 0.725 | 0.950 | 0.993 |
| test | E3 | 0.847 | 0.724 | 0.362 | 0.469 | 0.125 | 0.900 | 0.825 | 0.750 | 0.700 | 0.975 | 1.000 |

**What changed:** All numbers in the left half of this table (below Med Full) were originally 30–50% lower. The correction reframes the entire project from "models fail" to "models perform reasonably, but measurement was broken."

---

## 3. Finding 2: Benchmark Quality Is Tightly Clustered Across Frontier Models; Cost Is Not

**Sources:** Phase 1 (§3.1, §10), Phase 5 (§7.1)

Stage A (15 dev docs): GPT-4.1-mini (0.784), GPT-5.5 (0.789), GPT-5.4-mini (0.781), Claude Sonnet 4.6 (0.782). This 8pp range is smaller than the noise on 15 documents.

**Cost per quality-point:**
- GPT-4.1-mini: $0.005
- GPT-5.4-mini: $0.014
- Gemini 3.1 Flash: $0.011 (excluded due to quota failures)
- Claude Sonnet 4.6: $0.072
- GPT-5.5: $0.107

GPT-4.1-mini costs **14–21× less** per quality-point than Claude Sonnet or GPT-5.5. **No quality gap justifies frontier premium at ExECTv2 extraction scale.**

**However:** For the Gan frequency task, GPT-5.5 does outperform GPT-4.1-mini by 8–14pp (0.713→0.840 Pragmatic F1). This is a **task-specific finding that reverses the conclusion.** Frequency normalization requires stronger reasoning; medication name extraction does not.

**Deployment implication:** Use GPT-4.1-mini as the default frontier model for standard extraction. Reserve GPT-5.5 for frequency normalization and other reasoning-intensive sub-tasks.

---

## 4. Finding 3: Local Models Match or Exceed Frontier on Primary ExECTv2 Fields at Zero Cost

**Sources:** Phase 3 (§5.1, §7, §11), Phase 4 (§4)

| Model | Best harness | Med Name F1 | Sz F1c | Dx Acc | Lat | Cost |
|-------|--------------|-------------|--------|--------|-----|------|
| qwen3.6:27b | H6 | **0.885** | 0.578 | 0.800 | 34s | $0 |
| qwen3.6:35b | H6fs | 0.852 | 0.593 | 0.800 | 12s | $0 |
| gemma4:e4b | H6 | 0.849 | 0.593 | **0.825** | 28s | $0 |
| GPT-4.1-mini E3 | — | 0.872 | 0.633 | 0.775 | API | ~$0.005 |

- qwen3.6:27b H6: medication name F1 = 0.885 — first local model to exceed both frontier baselines on medication.
- qwen3.6:35b H6fs: matches GPT-4.1-mini S2 exactly on medication (0.852) at 12s/doc.
- gemma4:e4b: achieves the highest diagnosis accuracy of any model tested (0.825 vs frontier best 0.775).

**The local workstream demonstrates that privacy-constrained offline clinical deployment is operationally viable for the primary extraction task.**

**Recommended deployment candidate:** qwen3.6:35b H6fs — matches frontier medication F1 at 12s/doc with no API cost or internet requirement.

---

## 5. Finding 4: Seizure Type Improvement Is a Normalization Problem, Not a Model Problem

**Sources:** Phase 1 (§3.5), Phase 2 (§6.2), Phase 3 (§5.3), Phase 6 (§3.2, §8.2)

H7 (two-pass normalization, GPT-4.1-mini) achieved seizure_type_F1 = 0.698 on development — a **37% relative improvement** over H0's 0.512 from normalization alone, with no prompt changes.

The collapsed label scorer (benchmark_seizure_type_label) reproduced most of this gain in the evaluator without re-running models.

The remaining gap to the Fang benchmark target (≥0.76) is explained by:
1. The `unknown seizure type` meta-label problem (13–15 misses consistently across all models and scales)
2. The 13.3% oracle failure rate from annotation gaps in ExECTv2 itself

**This is the most important single finding about seizure type:** the gap is not model capability. It is benchmark design.

---

## 6. Finding 5: The `unknown seizure type` Meta-Label Is a Structural Ceiling

**Sources:** Phase 3 (§5.3), Phase 6 (§3.2, §8.2)

Across all models (4B to 35B), all harnesses (H6, H6fs, H6v2, H6ev, H6qa), the miss count for `unknown seizure type` is consistently **13–15 out of 26 documents** that have this gold label. Scale does not close this gap.

This label is used when the annotator cannot determine seizure type — a meta-judgment about absence of information. Models consistently attempt to infer a specific type from clinical context rather than producing the meta-label.

**This appears to be a genuine structural difference** between what models do (infer) and what the annotation scheme requires (abstain).

**Dissertation framing:** This is not a failure of clinical extraction. It is a mismatch between probabilistic model behavior and conservative annotation protocol. Claims about seizure type should reference collapsed labels and acknowledge the structural ceiling.

---

## 7. Finding 6: Evidence Grounding Is a Structural Guarantee, Not a Quality Cost

**Sources:** Phase 1 (§9), Phase 2 (§9), Phase 3 (§9)

Quote validity never fell below 0.960 under any perturbation, split, or system. Schema validity is 1.000 for all validation conditions. Label-changing validity (30 contrast documents) confirms evidence integrity holds even when document content changes ground-truth labels.

**The architecture's evidence discipline — requiring every extraction to be grounded in a verbatim quote — provides a strong clinical safety signal at no accuracy cost.**

This holds for frontier models (S2, E3) but is deliberately relaxed for local H6 models, which omit evidence quotes to stay within token budgets. A future deployment could add a lightweight second-pass evidence resolver for local models.

---

## 8. Finding 7: E3 Is the Best ExECTv2 System; S2 Is Surprisingly Strong on Test

**Sources:** Phase 1 (§10), Phase 2 (§8)

E3 leads every medication metric on both splits, ties or leads on investigations, and has the best validation diagnosis accuracy. It is also the most robustness-robust system (worst perturbation drop half of S2's).

However, on the test split, S2 achieves the highest diagnosis accuracy (0.850 vs E3's 0.750) — suggesting that for holistic diagnosis on diverse documents, the full-letter context of a direct extraction approach can outperform event-first aggregation. This may reflect that S2 sees the full diagnostic narrative, whereas E3 aggregates from individually extracted events that may lose global coherence.

**Recommendation:** E3 for medication-heavy workloads; S2 for diagnosis-heavy workloads.

---

## 9. Finding 8: Few-Shot Examples Have Model-Specific Effects

**Sources:** Phase 3 (§4.4, §6.1), Phase 5 (§5)

Variant A (H6fs) improved qwen3.5:9b by +6.1pp seizure F1 but harmed gemma4:e4b by −3.2pp. At 27B scale, H6fs harmed qwen3.6:27b by −4.7pp on medication. qwen3.6:35b (MoE architecture) uniquely tolerated H6fs without regression.

For the Gan workstream, hard-case examples harmed GPT-5.5 cot_label performance.

The same pattern appears repeatedly: **guidance that helps the model that needs it harms the model that doesn't.**

**Implication:** Capability-appropriate prompt design is required. A single universal harness is not the right abstraction for a multi-model dissertation claim.

---

## 10. Finding 9: Seizure Frequency Extraction Remains an Open Problem on ExECTv2

**Sources:** Phase 2 (§7), Phase 5 (§1), Phase 6 (§3.3, §8.1)

After all scoring fixes, ExECTv2 seizure frequency loose accuracy is 0.075–0.175. The 29.2% oracle failure rate means even perfect extraction cannot score above ~0.71 on this dataset.

The Gan workstream is the right venue for frequency claims. The ExECTv2 frequency field should be reported as a secondary crosswalk only, not as the primary frequency result.

---

## 11. Finding 10: GPT-5.5 Retrieval Augmentation Is the Most Promising Gan Approach

**Sources:** Phase 5 (§7.1)

G4-Fixed: `gpt_5_5` + `Gan_retrieval_highlight` = 0.840 Pragmatic F1 on 50 docs — 1pp below the 0.85 target, within sampling noise.

The retrieval-only ablation (0.520) confirms the mechanism: **salience priming, not direct lookup.**

G4-Full at 1,500 docs will give a reliable estimate and may cross 0.85.

---

## 12. Finding 11: Event-First Does Not Help Local Models; H6/H6fs Dominates

**Sources:** Phase 4 (§2.6, §4)

The local event-first investigation (EL0/EL1/EL2, May 10–11) produced a clean negative result. Three harness designs were tested; none improved seizure type F1 at 40-doc validation scale. Three apparent gains in the 10-doc dev pilot (+0.176, +0.099, +0.094) were all sampling noise that reversed sign or vanished at 40 docs.

The structural reason: the two-step extract-then-aggregate design forces the model to describe mentions in free text before mapping to closed benchmark labels, reintroducing exactly the normalization problem that H6's `Allowed labels:` block solves in a single pass.

**Definitive conclusion:** H6/H6fs remains the correct harness for all local models on this task.

---

## 13. Finding 12: MA_v1 Multi-Agent Pipeline Cleared MA1 Dev Pilot but Failed MA2 Promotion Gates

**Sources:** Phase 4 (§3)

The four-stage MA_v1 design achieves strong development BenchComp with GPT-5.4-mini (0.898 on 10 docs) but does not exceed the planned MA2 promotion thresholds on 40 validation documents for either GPT-5.4-mini or qwen_35b_local (BenchComp 0.757 / 0.772 vs gate 0.810; seizure collapsed 0.610 / 0.603 vs gate 0.660).

A follow-on GPT-5.5 MA3 run regressed further (BenchComp 0.650, seizure collapsed 0.379), indicating pipeline fragility rather than a simple "use a bigger model" fix.

**Conclusion:** Multi-agent decomposition introduces error propagation that outweighs cognitive-load benefits at clinical-document scale.

---

## 14. Finding 13: H7 and D3 Validation-Scale Medication Full Collapse Was a Prompt Bug

**Sources:** Phase 1 (§8.3), Phase 2 (§12.3)

Initial H7/D3 validation runs (May 11) showed medication_full_f1 ≈ 0.018 — effectively zero. Investigation revealed the verifier prompt instructed output of flat `medication_names` (name + quote only), stripping dose/unit/frequency. After fixing the prompt to output structured medications, medication_full_f1 recovered to ~0.60 (30–35× improvement).

This is a cautionary tale: multi-pass architectures are powerful but brittle to prompt drift.

---

## 15. Final Candidate Registry

| ID | Model | Harness | Purpose | Status |
|----|-------|---------|---------|--------|
| F1 | GPT-4.1-mini | S2 | Strong direct frontier baseline | Existing run |
| F2 | GPT-4.1-mini | E3 | Strong event-first frontier baseline | Existing run |
| F3 | qwen3.6:35b | H6fs | Primary local deployment candidate | Existing run |
| F3-H6 | qwen3.6:35b | H6 | Local ablation (plain harness) | Existing run |
| F4 | qwen3.6:27b | H6 | Best local medication F1 | Existing run |
| F4-fs | qwen3.6:27b | H6fs | Best medication with few-shot | Existing run |
| F5 | gemma4:e4b | H6 | Best local diagnosis accuracy | Existing run |
| F5-fs | gemma4:e4b | H6fs | Gemma4 few-shot ablation | Existing run |
| 9b-ref | qwen3.5:9b | H6fs | Reference: best 9B system | Existing run |

**Cancelled:** gemma4:26b (F5b), gemma4:31b (F5c) — inference too slow; qwen3.6:35b superior.

---

## 16. Deployment Recommendations

### Scenario A: Cloud-enabled clinical pipeline (budget-conscious)
- **Default:** GPT-4.1-mini S2 or E3
- **Frequency sub-task:** GPT-5.5 + Gan_retrieval_highlight
- **Cost:** ~$0.003–$0.005 per standard document; ~$0.62 per 50 frequency documents
- **Rationale:** Best cost-quality frontier. No local infrastructure needed.

### Scenario B: Privacy-constrained offline deployment
- **Default:** qwen3.6:35b H6fs
- **Hardware:** ~23 GB VRAM, consumer GPU
- **Latency:** 12s/document
- **Cost:** $0 marginal
- **Rationale:** Matches frontier medication F1. No internet required. HIPAA/GDPR-compliant by default.

### Scenario C: Ultra-low-resource edge deployment
- **Default:** qwen3.5:4b H6
- **Hardware:** ~4 GB VRAM
- **Latency:** 8s/document
- **Performance:** 0.814 med F1, 0.535 sz F1c
- **Rationale:** Clinically useful on primary fields at minimal hardware cost.

---

## 17. Limitations & Future Work

1. **ExECTv2 is synthetic.** All claims generalize to real NHS letters only to the extent that synthetic data captures real clinical language patterns.
2. **Gan frequency G4-Full is pending.** The 0.840 Pragmatic F1 on 50 docs is promising but needs confirmation at 1,500 docs.
3. **Local models omit evidence quotes.** H6 trades evidence grounding for token efficiency. A future two-pass local architecture (extract → evidence resolve) could restore this.
4. **Multi-agent was under-explored.** MA_v1 failed promotion gates, but different stage designs or segmentation strategies might succeed.
5. **Retrieval augmentation was only tested on Gan.** ExECTv2 medication and seizure-type could benefit from similar span-highlighting approaches.

---

## 18. Authoritative Number Reference

Numbers to use in the dissertation. All from corrected scorer unless noted.

### ExECTv2 Baseline (GPT-4.1-mini, corrected scorer)

| Split | System | Med Name | Med Full | Sz Collapsed | Freq Loose | Dx Acc | Schema | Quote |
|-------|--------|----------|----------|--------------|------------|--------|--------|-------|
| val | S2 | 0.852 | 0.655 | 0.610 | 0.075 | 0.725 | 1.000 | 0.991 |
| val | E3 | **0.872** | **0.707** | **0.633** | 0.125 | **0.775** | 1.000 | **0.994** |
| test | S2 | **0.885** | **0.769** | 0.415 | 0.175 | **0.850** | 0.950 | 0.993 |
| test | E3 | 0.847 | 0.724 | 0.469 | 0.125 | 0.750 | 0.975 | 1.000 |

### Local Models (validation, corrected scorer)

| Model | Best harness | Med Name | Sz Collapsed | Dx Acc |
|-------|--------------|----------|--------------|--------|
| qwen3.5:9b | H6fs | 0.839 | 0.602 | 0.825 |
| gemma4:e4b | H6 | 0.849 | 0.593 | 0.825 |
| qwen3.6:27b | H6 | **0.885** | 0.578 | 0.800 |
| qwen3.6:35b | H6fs | 0.852 | 0.593 | 0.800 |

### Gan Frequency (synthetic subset)

| System | Docs | Prag F1 | Pur F1 | Exact | Status |
|--------|------|---------|--------|-------|--------|
| GPT-5.5 + Gan_cot_label (G2/G3 best) | 50 | 0.800 | 0.760 | 0.540 | Superseded by G4-Fixed |
| GPT-5.5 + Gan_retrieval_highlight (G4-Fixed) | 50 | **0.840** | 0.820 | **0.820** | Best; promoted to G4-Full |
| GPT-4.1-mini + Gan_direct_label | 50 | 0.713 | 0.673 | 0.480 | Cost baseline |
| qwen_35b_local + Gan_g3_qwen | 150 | 0.693 | 0.667 | — | Local baseline |
| G4-Full (pending) | 1,500 | TBD | TBD | TBD | Main frequency result |

---

*This synthesis builds on: `docs/40_phase_1_frontier_model_selection.md`, `docs/41_phase_2_measurement_recovery.md`, `docs/42_phase_3_local_direct_models.md`, `docs/43_phase_4_local_architectural_alternatives.md`, `docs/44_phase_5_seizure_frequency.md`, `docs/45_phase_6_gold_standard_analysis.md`, and `docs/34_full_experiment_record.md`.*
