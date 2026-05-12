# Future Workstream: Retrieval Augmentation for ExECTv2 — Extending Span-Highlighting Beyond Gan

**Date:** 2026-05-12  
**Status:** Research proposal — extends Limitation #5 from `docs/50_synthesis_report.md`  
**Related:** Phase 5 (`docs/44_phase_5_seizure_frequency.md`, `docs/21_seizure_frequency_workstream.md`), `docs/26_retrieval_verified_experiment_plan.md`, `docs/34_full_experiment_record.md` §G4

---

## 1. What Was Demonstrated on Gan

The Gan seizure-frequency workstream produced the project’s strongest retrieval result: **G4-Fixed** (`gpt_5_5` + `Gan_retrieval_highlight`) achieved **0.840 Pragmatic micro-F1** on 50 documents, 1 pp below the 0.85 clinical-utility target and 13 pp above the non-retrieval GPT-4.1-mini baseline (0.713).

The retrieval mechanism operated as follows:
1. A lightweight retriever (keyword + heuristic span detection) identified candidate seizure-frequency phrases in the letter.
2. These spans were **highlighted** (wrapped in `<<< >>>` markers) and injected into the prompt before the extraction instruction.
3. The model was asked to normalise the highlighted spans into the structured Gan label scheme.

The **retrieval-only ablation** (0.520) confirmed that the mechanism is **salience priming, not direct lookup**. The model does not blindly copy retrieved spans; rather, the highlighted context narrows its attention to relevant regions of the narrative, reducing noise from unrelated sections (medication lists, family history, administrative headers).

**Critical gap:** This approach has never been tested on ExECTv2. The synthesis report explicitly flags this as a limitation: "Retrieval augmentation was only tested on Gan. ExECTv2 medication and seizure-type could benefit from similar span-highlighting approaches."

---

## 2. Why Retrieval Might Help ExECTv2

### 2.1 Medication Extraction

Medication name F1 is already strong (0.852–0.885 across frontier and local best systems), but **medication full-tuple F1** (name + dose + unit + frequency) is lower (0.655–0.769). The gap is caused by:
- **Scattered mentions:** A single letter may list current medications in the opening paragraph, mention dose changes in the body, and repeat the list in the assessment plan.
- **Contextual dose/frequency:** The dose may appear two sentences after the name, or in a separate table.
- **Discontinued vs. current ambiguity:** Historical medications are often mentioned near current ones; the model must infer temporality from surrounding text.

A retriever that highlights **all medication-related spans** (drug names, dosages, frequency phrases) could help the model attend to the full medication narrative without being distracted by seizure descriptions or investigation results.

### 2.2 Seizure Type Extraction

Seizure type collapsed F1 on ExECTv2 peaks at 0.633 (E3 validation) and is structurally capped by the `unknown seizure type` meta-label problem (Finding 5). However, the *remaining* gap — the difference between 0.633 and the Fang benchmark target (≥0.76) — is partly due to:
- **Distributed descriptions:** Seizure semiology is often described across multiple sentences ("She experiences brief episodes of unresponsiveness... sometimes with lip smacking..."). The model must integrate these into a single ILAE label.
- **Normalisation ambiguity:** The same clinical description ("staring spells") maps to multiple benchmark labels depending on context.
- **Family-history contamination:** The `family_history_trap` perturbation shows that models routinely read family seizure history as patient findings.

A retriever that highlights **all seizure-description spans** and optionally provides **canonical ILAE definitions** as external context could improve both recall (fewer missed mentions) and precision (fewer family-history misclassifications).

### 2.3 Investigations and Diagnosis

These fields already score well (EEG 0.90–0.975, MRI 0.825–1.000, diagnosis accuracy 0.725–0.850). Retrieval augmentation is less urgent here, but a targeted retriever for **investigation-result sentences** could reduce the negated-investigation trap (e.g., "MRI was normal" vs. "MRI not performed").

---

## 3. Design Options for ExECTv2 Retrieval

### 3.1 In-Document Span Retrieval (Internal RAG)

**Mechanism:** Use a lightweight retriever to select the most relevant passages from the source letter before the LLM call.

**Retrieval methods to compare:**

| Method | Description | Pros | Cons |
|---|---|---|---|
| **Keyword/Regex** | Match ASM name list, seizure keywords ("seizure", "fit", "episode"), dose patterns | Fast, deterministic, no embeddings | Misses paraphrases, synonyms, implicit mentions |
| **BM25** | Sparse retrieval on letter chunks | Handles synonymy better than regex; clinically proven (PubMed search) | Requires chunking; may miss cross-sentence context |
| **Dense (ClinicalBERT / MedCPT)** | Embedding-based retrieval with a clinical encoder | Captures semantic similarity ("staring spell" ≈ "absence") | Requires embedding model; adds preprocessing latency |
| **Hybrid (BM25 + Dense)** | Reciprocal rank fusion of both lists | Best recall; standard in open-domain RAG | More complex; hyperparameter tuning needed |

**Highlighting strategy:** Wrap top-k retrieved spans in markers (`<<< ... >>>`) and prepend them to the prompt. The model still sees the full letter, but the highlighted spans act as anchor points.

**Token budget impact:** Highlighting adds input tokens. For a letter with 10 medication mentions and 5 seizure descriptions, the highlighted spans might add 500–1,000 tokens. For frontier models, this is negligible. For local models (qwen3.6:35b), the H6 prompt is already near the sweet spot; extra input tokens may slow inference but are unlikely to cause truncation.

### 3.2 External Knowledge Retrieval (External RAG)

**Mechanism:** Retrieve canonical definitions or synonym sets from an external knowledge base and inject them into the prompt.

**Knowledge bases:**
- **UMLS / SNOMED CT:** Retrieve canonical medication names and synonyms. The JMIR scoping review (2024) found that 89 % of studies reported performance improvements after SNOMED CT integration, with gains ranging from 0.87 % to 131 % depending on the task.
- **ILAE Seizure Classification:** Retrieve definitions for "focal impaired awareness," "absence," "tonic-clonic," etc., to help the model map free-text descriptions to benchmark labels.
- **Project-specific synonym tables:** The existing `normalization.py` ASM synonym expansion table is already a miniature knowledge base. It could be reformatted as retrieved context rather than hard-coded in the prompt.

**Why this differs from Gan:** Gan retrieval was purely internal (spans from the same document). ExECTv2 could benefit from *external* retrieval because normalisation is the dominant error mode — and normalisation is a knowledge-gap problem, not just a span-location problem.

### 3.3 Hybrid Design: Internal + External Retrieval

**Pass 1 (Retriever):**
- Identify medication spans and seizure-description spans in the letter (internal).
- Retrieve UMLS synonyms for each identified medication name, and ILAE definitions for each candidate seizure type (external).

**Pass 2 (Extractor):**
- Receive the full letter + highlighted spans + external definitions.
- Extract structured fields with the augmented context.

This is analogous to ClinicalRAG’s two-stage MEE → HKI pipeline: first identify what is in the text, then enrich it with structured knowledge.

---

## 4. Experimental Design

### 4.1 Baselines

| Baseline | Description | Purpose |
|---|---|---|
| **S2** | Direct extraction, no retrieval | Frontier single-agent ceiling |
| **E3** | Event-first extraction, no retrieval | Frontier best system |
| **H6fs** | Local direct extraction, no retrieval | Local deployment ceiling |
| **S2-long** | S2 with matched extra input tokens (e.g., repeated letter, dummy highlights) | Token-budget control: is any gain just from longer context? |

### 4.2 Treatment Conditions

| Condition | Retrieval Type | Target Field | Model |
|---|---|---|---|
| **R-Med-Int** | Internal span highlight (medication mentions) | Medication | GPT-4.1-mini, qwen3.6:35b |
| **R-Med-Ext** | External SNOMED/UMLS synonyms + internal spans | Medication | GPT-4.1-mini, qwen3.6:35b |
| **R-Sz-Int** | Internal span highlight (seizure descriptions) | Seizure type | GPT-4.1-mini, qwen3.6:35b |
| **R-Sz-Ext** | External ILAE definitions + internal spans | Seizure type | GPT-4.1-mini, qwen3.6:35b |
| **R-Full-Hyb** | Hybrid: internal spans for med + sz, external synonyms + definitions for both | All fields | GPT-4.1-mini, qwen3.6:35b |

### 4.3 Ablations

| Ablation | Purpose |
|---|---|
| **Retrieval-only** (no full letter) | Tests whether the model can extract from highlights alone. Expect low score; confirms salience-priming mechanism (as in Gan). |
| **Random-highlight control** | Inject randomly selected spans as highlights. If performance improves, the gain is a token-budget artifact, not retrieval quality. |
| **External-only** (no internal spans) | Tests whether external knowledge alone helps normalisation. |

### 4.4 Metrics

- **Primary:** `medication_name_f1`, `medication_full_f1`, `seizure_type_f1_strict`, `seizure_type_f1_collapsed`
- **Secondary:** `quote_validity` (if quotes are requested), `recall` (are more mentions found?), `precision` (are fewer spurious mentions added?)
- **Process:** `retrieval_precision` (fraction of retrieved spans that are relevant), `retrieval_recall` (fraction of gold mentions covered by retrieved spans), `input_token_count`
- **Cost:** API cost per document, latency per document

### 4.5 Token-Budget Controls

As with the multi-agent workstream, retrieval must be evaluated against a **matched-token single-agent baseline**:
- **Control A:** Add the same number of dummy tokens to the prompt (e.g., lorem ipsum or a generic clinical template) to test for pure context-length effects.
- **Control B:** Use the extra token budget for longer CoT reasoning instead of retrieval.

Only if retrieval-outperforms-both-controls can the gain be attributed to the retrieval mechanism itself.

---

## 5. Hypotheses and Expected Outcomes

| Hypothesis | Expected Direction | Rationale |
|---|---|---|
| **H1** | Internal retrieval improves `medication_name_f1` by +2–4 pp | Surfaces scattered mentions; reduces missed medications in dense sections. |
| **H2** | External retrieval improves `medication_full_f1` by +3–5 pp | SNOMED synonyms resolve dose-unit paraphrases (e.g., "1 g" vs. "1000 mg"). |
| **H3** | Internal retrieval improves `seizure_type_f1_collapsed` by +2–4 pp | Highlights seizure narrative, reducing family-history contamination. |
| **H4** | External retrieval does **not** close the `unknown seizure type` gap | The structural ceiling (Finding 5) is a model-inference vs. annotation-protocol mismatch; no amount of retrieved knowledge changes the model’s tendency to infer rather than abstain. |
| **H5** | Gains are larger for seizure type than medication | Medication baseline is already high (0.85+); seizure type has more headroom and stronger normalisation needs. |
| **H6** | Retrieval gains are smaller on local models than frontier | Local models may struggle to integrate highlighted spans with external definitions in a single context window due to reasoning limitations, not just token limits. |

---

## 6. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| **Retrieval noise:** Highlighted spans distract the model or include irrelevant text | Filter retrieved spans by confidence score; exclude spans from known trap sections (family history) unless explicitly requested. |
| **Token inflation:** Local models slow down or truncate | Cap highlighted spans at top-5 per field; use deterministic string matching for medication names rather than embedding retrieval to minimise preprocessing. |
| **Structural ceiling masks gains:** Seizure type cannot exceed ~0.71 due to oracle failure + unknown meta-label | Report retrieval results alongside the collapsed-label ceiling. Frame gains as "proportion of achievable gap closed" rather than absolute F1. |
| **Diminishing returns:** Medication F1 is already near ceiling; retrieval adds cost with little benefit | Focus retrieval experiments on `medication_full_f1` (lower baseline) rather than `medication_name_f1`. |
| **Gan-specific mechanism fails to generalise:** Gan letters are synthetic and structured; real ExECTv2 letters are noisier | Run a 10-document dev pilot first. If retrieval precision < 0.70, abandon or retune the retriever before scaling. |

---

## 7. Relation to Broader Research

### 7.1 ClinicalRAG and Multi-Agent Retrieval

ClinicalRAG (ACL KnowLLM, 2024) demonstrates that retrieval is most effective when it is **heterogeneous** (spanning textbooks, guidelines, and ontologies) and **agent-mediated** (different agents handle entity extraction, knowledge retrieval, and synthesis). The ExECTv2 hybrid design (§3.3) is a simplified version of this: one retriever, one extractor, no explicit multi-agent orchestration. If the single-retriever design underperforms, the next logical step is to adopt ClinicalRAG’s multi-agent retrieval pattern, where a dedicated MEE agent identifies candidates and a second agent queries UMLS/SNOMED CT for each candidate.

### 7.2 SNOMED CT Integration

The JMIR scoping review (2024) found that 76 % of SNOMED-LLM integration studies incorporate the ontology into model *inputs* (e.g., concept descriptions appended to prompts). Only 14 % use SNOMED as an external retriever during inference. The proposed external-retrieval condition (R-Med-Ext) falls into the latter, under-explored category. If it succeeds, it would be a methodological contribution: demonstrating that lightweight retrieval from SNOMED CT synonyms at inference time improves structured medication extraction without model fine-tuning.

### 7.3 Salience Priming vs. Direct Lookup

The Gan workstream’s key methodological finding — that retrieval helps because of **salience priming**, not direct lookup — should be treated as a transferable principle. For ExECTv2, this implies that the retriever does not need perfect precision. Even a noisy set of candidate spans can improve extraction if the noise is random (and therefore averaged out by the model’s attention) rather than systematic (and therefore biased). The random-highlight control ablation is designed to test the boundary of this principle.

---

## 8. Implementation Roadmap

| Step | Task | Deliverable | Gate |
|---|---|---|---|
| 1 | Build medication span retriever (regex + ASM list) | `src/retrieval_med.py` | Precision ≥ 0.80 on 10 dev docs |
| 2 | Build seizure span retriever (regex + keyword list) | `src/retrieval_sz.py` | Precision ≥ 0.70 on 10 dev docs |
| 3 | Integrate SNOMED/UMLS synonym lookup | `src/retrieval_kb.py` | Coverage ≥ 0.90 for top 20 ASMs |
| 4 | Implement highlight injection in existing harnesses | `src/harness_r_med.py`, `src/harness_r_sz.py` | Prompt renders correctly; no truncation |
| 5 | Run 10-document dev pilot for all conditions | `runs/retrieval_exect/dev_pilot/` | Identify parse or retriever failures |
| 6 | Run 40-document validation sweep | `runs/retrieval_exect/validation/` | Compare against S2/E3/H6fs baselines |
| 7 | Run matched-token controls (dummy highlights, long CoT) | `runs/retrieval_exect/controls/` | Confirm mechanism attribution |
| 8 | Error audit: classify retrieval-induced errors | `docs/retrieval_exect_error_audit.md` | Inform retriever tuning |

---

## 9. Dissertation Framing

If retrieval augmentation improves ExECTv2 medication or seizure-type extraction, the dissertation gains a cross-workstream claim: **"Retrieval-augmented salience priming, first validated on Gan frequency normalisation, generalises to structured field extraction from NHS clinic letters."** This connects the Gan and ExECTv2 threads into a single methodological contribution.

If retrieval does *not* help, the dissertation claim is equally valuable: **"The gains observed on Gan frequency are task-specific; medication and seizure-type extraction on ExECTv2 are not retrieval-limited but normalisation-limited (seizure type) or already near-ceiling (medication name)."** This would direct future work toward normalisation-centric solutions (e.g., H7-style two-pass normalisation) rather than retrieval-centric ones.

Either outcome closes a gap in the current evidence base and justifies the experimental effort.
