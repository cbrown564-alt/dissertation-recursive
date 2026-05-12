# Future Workstream: Two-Pass Evidence Resolution for Local Models

**Date:** 2026-05-12  
**Status:** Research proposal — extends Limitation #3 from `docs/50_synthesis_report.md`  
**Related:** Phase 3 (§9), Phase 4 (§13), `docs/03_pipeline_design.md`, `docs/06_literature_review_matrix.md`

---

## 1. Problem Statement

The H6 family of harnesses (H6, H6fs, H6v2) deliberately omits verbatim evidence quotes from local-model extractions in order to stay within tight output-token budgets. This is a successful trade-off: qwen3.6:35b H6fs matches frontier medication F1 (0.852) at 12 s/document and zero API cost. However, it comes at the cost of **evidence grounding**. Frontier systems (S2, E3) sustain quote validity ≥ 0.991 across all splits and perturbations, whereas local H6 outputs provide no auditable provenance for any extracted value.

In a clinical deployment, evidence quotes are not a luxury. They are the mechanism by which a clinician can verify that `levetiracetam 1,000 mg twice daily` was actually present in the source letter, rather than hallucinated or imported from parametric knowledge. The synthesis report (Finding 6) frames evidence grounding as a "structural guarantee" that provides "a strong clinical safety signal at no accuracy cost" — but this guarantee currently applies only to frontier API models.

**Research question:** Can a lightweight second-pass evidence resolver restore quote-level grounding to local-model extractions without negating the token-efficiency advantage that makes local deployment viable?

---

## 2. Why Evidence Grounding Matters Clinically

The project’s evaluation protocol already separates evidence support into five layers (`docs/04_evaluation_protocol.md`):

1. **Quote presence** — did the output include a quote?
2. **Quote validity** — does the exact quote appear in the source?
3. **Semantic support** — does the quote support the value?
4. **Temporal support** — does the quote support the temporality?
5. **Field correctness** — is the value itself correct?

H6 local models fail at layer 1 by design. In a real-world NHS pipeline, this has concrete consequences:

- **Audit and liability:** A downstream decision-support system that acts on an extraction must be able to display the source sentence to the clinician. Without it, the extraction is a black box.
- **Hallucination detection:** Quote validity is the only automated check that distinguishes parametric knowledge (model memory) from in-context knowledge (the actual letter). Local models are not immune to hallucination; the absence of quotes simply removes the detector.
- **Robustness to perturbation:** Frontier S2 drops as much as −0.400 on seizure type under the `family_history_trap` perturbation, but the quote validity check surfaces *why* the drop occurs (family-history sentences are mis-read as current findings). Without quotes, local models offer no equivalent diagnostic.

The trade-off is rational at the current project stage — accuracy was prioritised over auditability — but it is not a permanent equilibrium.

---

## 3. Proposed Architecture: Extract → Evidence Resolve

The core idea is to **decouple extraction from grounding**. Pass 1 performs the extraction exactly as H6 does now: structured JSON, no quotes, maximally compact. Pass 2 takes the original letter *plus* the extracted values, and for each value locates the verbatim supporting span.

This mirrors the **post-generation citation (PGC)** paradigm from general-domain NLP (Huo et al., 2023) and the **double-pass citation** method explored in biomedical RAG systems (MedCite, ACL 2025). It also resembles the *Referential Discovery* two-pass ingestion pattern, which pre-computes cross-document dependency resolution before final extraction.

### 3.1 Design Option A: Per-Field Evidence Resolver (Sequential)

**Pass 1:** H6 extraction → `medications`, `seizure_types`, `diagnosis`, etc.

**Pass 2:** One LLM call per field family (medication, seizure, diagnosis, investigations).

- **Input:** original letter + list of extracted values for that field.
- **Task:** For each value, return the shortest contiguous verbatim substring that justifies it. If no quote can be found, flag the value as `ungrounded`.
- **Output:** enriched JSON with `evidence_quote` and `grounding_confidence` (`high | medium | low`).

**Token budget:** Pass 2 input ≈ 1× letter + 1× extracted JSON per field. For a 4-field decomposition, this is 4 sequential calls, each comparable to a single H6 call. Total latency ≈ 5× H6 latency (~60 s for qwen3.6:35b). Cost remains $0 for local deployment.

**Advantage:** Narrow scope per call reduces cognitive load; verifier-style prompt can reuse the existing D3 verifier infrastructure.

**Risk:** Sequential calls compound latency. Error in Pass 2 (e.g., hallucinated quote) is detectable by quote-validity scoring but not automatically correctable.

### 3.2 Design Option B: Single-Pass Full-Document Re-Scan

**Pass 1:** H6 extraction (as above).

**Pass 2:** One LLM call with a *highlighting* instruction.

- **Input:** original letter + full extracted JSON.
- **Task:** Return the letter text with each extracted value annotated by a `[[span]]` marker around the supporting evidence. Ungrounded values are listed separately.
- **Output:** annotated text + ungrounded list.

**Token budget:** Single call, but output includes the full letter plus markers. Output tokens could exceed 2,048 for long letters, risking truncation on local models.

**Advantage:** Minimal call overhead (1 call), preserves cross-field context (a single quote may support both seizure type and frequency).

**Risk:** High output-token demand makes this fragile for local models. Also harder to parse deterministically.

### 3.3 Design Option C: Hybrid String-Match + LLM Fallback

**Pass 1:** H6 extraction.

**Pass 2a (deterministic):** For each extracted value, run a fuzzy string search (e.g., RapidFuzz) against the original letter. If a high-similarity span is found within a small edit distance, accept it as the quote without an LLM call.

**Pass 2b (LLM fallback):** For values with no deterministic match (e.g., paraphrased doses, inferred seizure types), invoke a lightweight local model (qwen3.5:4b or gemma4:e4b) to locate the closest supporting sentence.

**Token budget:** Most values resolve via 2a (zero LLM tokens). Fallback rate can be measured on a dev set; if <20 %, total LLM overhead is negligible.

**Advantage:** Maximally efficient. Matches the project’s design philosophy of "simplest harness that works."

**Risk:** Fuzzy matching on clinical text is non-trivial (abbreviations, line breaks, OCR noise). A value like `"levetiracetam 1 g bd"` may appear in the letter as `"Keppra 1000mg twice a day"`; pure string matching will fail, requiring synonym awareness or the existing `normalization.py` ASM expansion table.

---

## 4. Token-Economics and Latency Analysis

| Design | Extra Calls | Extra Input Tokens / Doc | Extra Output Tokens / Doc | Latency (qwen3.6:35b) | Latency (qwen3.6:27b) |
|---|---|---|---|---|---|
| Baseline H6 | 0 | 0 | 0 | 12 s | 34 s |
| Option A (per-field) | 4 | ~4,000–6,000 | ~800–1,200 | +48 s = **60 s** | +136 s = **170 s** |
| Option B (full re-scan) | 1 | ~1,500 | ~2,000–3,500* | +12 s = **24 s** | +34 s = **68 s** |
| Option C (hybrid) | 0–1 | ~0–1,500 | ~0–400 | +0–12 s = **12–24 s** | +0–34 s = **34–68 s** |

\* Option B output may exceed local model context limits for long letters; truncation risk is real.

**Cost implication:** For local deployment, marginal cost remains $0. GPU power consumption increases linearly with call count. For a cloud API deployment, Option A at 4 extra calls per document would raise the per-document cost from ~$0.005 to ~$0.020 — still modest, but no longer "negligible."

---

## 5. Evaluation Protocol

The existing scorer already computes `quote_validity` and `quote_presence`. A two-pass evidence resolver can be evaluated with no scorer changes:

1. **Quote presence rate:** Must reach ≥ 0.95 to be clinically acceptable (frontier baseline: 0.991–1.000).
2. **Quote validity rate:** Fraction of present quotes that are exact substrings of the source. Target ≥ 0.98.
3. **Ungrounded rate:** Fraction of extracted values that Pass 2 could not anchor. Target < 5 % for medications; higher tolerance acceptable for inferred seizure types.
4. **Accuracy preservation:** Pass 1 extraction must not change. The resolver is *additive*; if Pass 2 modifies the value, it is a bug, not a feature. (Exception: Option C may drop ungrounded values, which would affect recall — this must be reported separately.)
5. **End-to-end latency:** Documented per design option above.
6. **Robustness mini-run:** Run the `family_history_trap` and `negated_investigation_trap` perturbations. Verify that the resolver does not hallucinate quotes from the perturbed (irrelevant) sections.

**Promotion gate:** Option C hybrid, if it achieves quote presence ≥ 0.95 with <10 % fallback rate and <20 % latency increase, becomes the default local deployment harness (F3-H6 → F3-H6+EV).

---

## 6. Relation to Existing Research

### 6.1 Post-Generation Citation (PGC)

Huo et al. (2023) introduced PGC as a retrieval step *after* answer generation. The extraction → resolver pipeline is structurally identical: the model generates the answer first, then a second stage retrieves (or in this case, locates) the evidence. In general-domain QA, PGC is more robust than retrieval-before-generation because the answer is not biased by a potentially noisy retriever. For clinical extraction, the same logic applies: the extractor knows what it wants to say; the resolver only needs to find where it came from.

### 6.2 MedCite Double-Pass

The MedCite framework (ACL Findings 2025) explicitly compared a *non-parametric* RAG+citation pipeline against a *hybrid double-pass* method that first generates an answer with parametric citations, then retrieves documents to validate and refine them. The double-pass method outperformed the single-pass on citation precision (+16.7 pp) and recall (+4.9 pp) while maintaining answer correctness. This supports the hypothesis that a two-pass resolver can improve grounding without harming accuracy.

### 6.3 Two-Pass Ingestion Patterns

Recent work on *Referential Discovery* (ResearchSquare, 2025) proposes a two-pass ingestion pattern for long-document RAG: Pass 1 builds a dependency index; Pass 2 resolves references. While the domain differs (HR document verification vs. clinical letters), the architectural principle is the same: separate the computationally expensive "understanding" phase from the "grounding" phase, and use deterministic pre-computation where possible.

---

## 7. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Pass 2 hallucinates quotes that do not exist in the source | Enforce exact substring match in scorer; do not accept paraphrased quotes as valid. |
| Pass 2 drops correct values because it cannot find a quote | Track `ungrounded_rate` separately from `quote_validity`. Do not conflate the two. |
| Latency makes local deployment impractical for real-time use | Default to Option C (hybrid). Only invoke LLM fallback when deterministic match fails. |
| Prompt drift in Pass 2 alters extracted values (cf. H7/D3 medication_full collapse) | Freeze Pass 1 prompt. Pass 2 prompt must be strictly read-only: "find evidence, do not change values." Unit-test on contrast documents. |
| Local model output-token limit truncates long quotes | Limit quote length in prompt ("shortest contiguous substring, ≤ 200 characters"). |

---

## 8. Immediate Next Steps

1. **Implement Option C stub:** Build a deterministic fuzzy matcher using the existing `normalization.py` synonym tables for ASM names, and test fallback rate on 40 validation documents.
2. **Design Pass 2b fallback prompt:** Re-use the D3 verifier prompt structure, but constrain it to evidence-location only (no keep/drop/modify decisions).
3. **Run dev-pilot (10 docs):** Measure quote presence, quote validity, ungrounded rate, and fallback rate for all three options.
4. **Compare against frontier:** If Option C reaches quote validity ≥ 0.95, the local deployment candidate (qwen3.6:35b H6fs) regains the evidence-guarantee property of frontier systems at zero marginal cost.

---

## 9. Dissertation Framing

If successful, this workstream reframes the local-model contribution from "accurate but ungrounded" to "accurate *and* auditable." It demonstrates that the token-budget limitation of small local models is an **engineering constraint**, not a **theoretical ceiling**: by decomposing the task into an extraction phase (which demands generative reasoning) and a grounding phase (which demands search and matching), each phase can be solved by the cheapest tool capable of that sub-task. This is, in miniature, the same decomposition logic that motivates multi-agent systems — applied here to a single field (evidence) rather than the full extraction pipeline.
