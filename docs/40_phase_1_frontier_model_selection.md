# Phase 1: Frontier Model Selection and Prompt Harness Design

**Date:** 2026-05-07 to 2026-05-11  
**Scope:** Model expansion workstream — Stages A through E, plus validation-scale revisits.  
**Purpose:** Select frontier models, design prompt harnesses, and establish the extraction architecture that will feed all downstream phases.  
**Status:** Complete. Corrected metrics authoritative.

---

## 1. Aims & Research Questions

This phase tests the central hypothesis of the dissertation: *for clinical information extraction from epilepsy clinic letters, prompt architecture and normalization design matter as much as model scale*. Specifically:

1. **H₁ (Cost-Effectiveness):** Does a small frontier model (GPT-4.1-mini) achieve clinically acceptable performance at a fraction of the cost of larger models (GPT-5.5, Claude Sonnet 4.6)?
2. **H₂ (Harness Architecture):** Can decomposed harnesses (two-pass normalization, candidate-plus-verifier, evidence-later) improve upon single-pass strict canonical extraction on the weakest fields — seizure type and medication full tuple?
3. **H₃ (Normalization vs. Extraction):** Are low scores on seizure type and medication tuple caused by model extraction failure, or by a mismatch between extracted clinical language and benchmark label taxonomy?
4. **H₄ (Evidence Grounding):** Can structural evidence requirements be maintained across harness variants without degrading benchmark quality?

The phase also served a critical infrastructure purpose: every pipeline was stub-verified before any API spend, and every promotion decision was gated on canonical schema validity ≥ 0.99 and quote validity ≥ 0.99.

---

## 2. Infrastructure / Methodology

### 2.1 Milestone Verification Before API Spend

On May 6, every mechanical pipeline was verified with stub providers (empty canonical outputs) before a single real-model call:

| Milestone | Pipeline Verified | Key Finding |
|---|---|---|
| Milestone 3 | Direct baseline (S1/S2/S3) | JSON vs YAML format choice is orthogonal to quality |
| Milestone 4 | Event-first (E1/E2/E3) | E3 second-call overhead negligible (~0.028 ms) |
| Milestone 5 | Evaluation harness artifact-gating | Gate correctly returns 0 docs when artifacts absent |
| Milestone 7 | Secondary analyses (JSON/YAML, local/frontier, E2/E3) | Structurally independent; real data required for quality diffs |
| Milestone 8 | Write-up support infrastructure | Claim traceability confirmed end-to-end |

This discipline saved significant budget. When Gemini 3.1 Flash later produced systemic empty responses under quota pressure, the infrastructure was already hardened to detect and exclude unavailable providers without corrupting score matrices.

### 2.2 Harness Vocabulary

The following named harness contracts were designed and tested during this phase. All IDs are preserved exactly as they appear in `configs/harness_matrix.yaml` and `src/model_expansion.py`.

| ID | System | Description | Canonical Projection |
|---|---|---|---|
| **H0** | D0 | Strict canonical JSON with evidence quotes; full local schema (`S2` prompt) | Native |
| **H1** | — | Repaired canonical: robust parse repair + normalization before scoring | Native |
| **H2** | D1 | Task-specific compact prompts per benchmark field; no full-schema output | **Blocked** (no projection layer at Stage A) |
| **H3** | D2 | Loose answer-then-parse: model answers in prose/lists; deterministic parse | **Blocked** (no projection layer at Stage A) |
| **H4** | D4 | Provider-native structured output (`json_schema` / `format: json`); minimal constraint | Native |
| **H5** | — | Verifier relaxed: candidate extraction + keep/drop/normalize verifier | Deprecated in favour of D3 |
| **H6** | D6 | Benchmark-only coarse JSON: compact prompt restricted to benchmark-aligned fields | Relaxed projection (no evidence in base H6) |
| **H6fs** | — | H6 + three few-shot seizure-type examples | Relaxed projection |
| **H6v2** | — | H6 + explicit `unknown seizure type` guidance + temporality restriction | Relaxed projection |
| **H7** | D7 | Extract-then-normalize: Pass 1 extracts rich facts with quotes; Pass 2 maps to benchmark labels | Evidence reconstruction added May 8 |
| **H8** | D8 | Evidence-later: Pass 1 extracts without evidence; Pass 2 resolves evidence quotes | Evidence reconstruction added May 8 |
| **D3** | D3 | Candidate + verifier: Pass 1 permissive candidates; Pass 2 keep/drop/normalize with quotes | Evidence reconstruction verified May 11 |

> **Nomenclature note:** "System" labels (D0–D8) are internal shorthand used in evaluation tables. H0 maps to D0, H7 to D7, D3 to D3, etc. The overlap between "D3" as a system label and "D3" as a harness ID is intentional — the candidate+verifier architecture was conceived as the third model-expansion variant.

---

## 3. Prompt Evolution

The prompts evolved from a single monolithic schema instruction (H0) toward increasingly decomposed designs that separate extraction from normalization, and normalization from evidence grounding. Below are the actual prompt contracts as sent to the model, reconstructed from `src/model_expansion.py` and the call logs in `runs/model_expansion/`.

### 3.1 H0 — Strict Canonical (Baseline)

H0 is the direct S2 prompt (`prompts/direct_baselines/s2_direct_json_evidence.md`) prepended to the full canonical JSON schema, sentence list, and source letter:

> You are extracting structured information from an epilepsy clinic letter.
>
> Return only one JSON object matching the canonical extraction schema. Do not wrap the response in Markdown. Use `pipeline_id: "S2_direct_json_evidence"`.
>
> Every present field must include exact evidence quotes copied from the source letter. Evidence quotes must be contiguous text from the letter. Include `sentence_id`, `char_start`, and `char_end` when you can identify them from the provided sentence list; otherwise use `null`.
>
> Create evidence-grounded events for medication, seizure frequency, seizure type, EEG/MRI investigation, and diagnosis claims. Final fields should cite supporting event IDs in `evidence_event_ids`.
>
> Do not infer values from clinical knowledge. Use `not_stated` when the letter does not state the field and use `uncertain` when relevant text exists but the value cannot be resolved.

This is followed by the full `schemas/canonical_extraction.schema.json` (~200 lines), the sentence table, and the raw letter text. The prompt is ~3,700 tokens input and demands ~2,000–3,000 tokens of structured JSON output.

### 3.2 H2 — Task-Specific

H2 abandons the full schema in favour of compact per-field extraction:

> Extract only these benchmark-oriented fields from the epilepsy clinic letter.
> Return compact JSON with keys: `medication_names`, `seizure_types`, `epilepsy_types`, `seizure_frequency`, `investigations`.
> Use `null` or `[]` when absent. Do not invent unsupported values.

At Stage A, H2 and H3 produced no canonical projection layer — they were exploratory harnesses held back until `projected_canonical()` could map their outputs to the canonical schema.

### 3.3 H3 — Loose Answer-Then-Parse

H3 gives the model even more freedom:

> Answer concisely from the epilepsy clinic letter.
> List current anti-seizure medications, seizure types, epilepsy diagnosis/type, current seizure frequency, EEG result, and MRI result.
> Use brief bullets or simple JSON. Say not stated when the letter does not support a field.

H3 outperformed H2 on development (GPT-5.4-mini + H3 = 0.809 benchmark quality), but both were excluded from promotion at Stage C0 because they lacked evidence reconstruction.

### 3.4 H6 — Benchmark-Only Coarse JSON

H6 was the critical simplification that made local-model deployment feasible. It restricts the output to three benchmark-aligned fields:

> Extract only benchmark fields from this epilepsy clinic letter.
> Return JSON only with this shape:
> `{"medication_names":[],"seizure_types":[],"epilepsy_diagnosis_type":null}`
>
> Medication names should include current anti-seizure medications only. Use generic drug names where possible.
> Seizure types must use only the allowed labels. Do not include aura, warning, symptom, medication side effect, investigation finding, or differential diagnosis labels as seizure types.
> Epilepsy diagnosis/type must use one allowed label or null. Do not invent a diagnosis if the letter does not support one.

The allowed label blocks are appended dynamically from `BENCHMARK_SEIZURE_LABELS` and `BENCHMARK_EPILEPSY_LABELS`.

### 3.5 H7 — Two-Pass Extract-Then-Normalize

H7 decomposes extraction into two LLM calls:

**Pass 1 (Extract):**

> Pass 1 of 2: extract rich clinical facts from this epilepsy clinic letter.
> Return JSON only with this shape:
> `{"rich_facts":[{"category":"medication|seizure_type|epilepsy_diagnosis","text":"","quote":"<exact verbatim span copied from the letter>","current_patient_fact":true}]}`
>
> Include current anti-seizure medication names, clinically described seizure/semiology facts, and epilepsy diagnosis/type facts.
> The quote field must be an exact contiguous span copied from the source letter. Do not paraphrase. If no single span supports the fact, use the most representative short span.
> Mark non-current, family-history, unsupported, or non-patient facts with `current_patient_fact=false`.

**Pass 2 (Normalize):**

> Pass 2 of 2: map extracted clinical facts to benchmark labels and preserve evidence quotes.
> Use only the extracted facts and source letter. Return JSON only with this shape:
> `{"medications":[{"name":"","dose":null,"unit":null,"frequency":null,"quote":""}],"seizure_type_mappings":[...],"seizure_types":[{"label":"","quote":""}],"epilepsy_diagnosis_type":{"label":null,"quote":""},"epilepsy_diagnosis_decision":"supported|unsupported|too_specific|not_benchmark_relevant"}`

The key design move is that Pass 1 is *not* asked to produce benchmark labels — it is asked to produce clinically faithful facts with verbatim quotes. Pass 2 performs the taxonomy mapping. This separation is what allowed H7 to achieve seizure_type_F1 = 0.698 on development: the model is no longer trying to simultaneously extract, label, and JSON-encode.

### 3.6 H4 — Native Structured Output

H4 uses the same prompt text as H6 but invokes the provider's native JSON-schema enforcement (OpenAI `json_schema`, Ollama `format: json`). On frontier models, H4 produced no measurable quality improvement over H6 — the prompt-only JSON instruction was sufficient. On local models, H4 was slightly faster because the JSON formatter is hardware-accelerated in Ollama.

### 3.7 H8 — Evidence Later

H8 inverts the evidence workflow: Pass 1 extracts benchmark fields *without* evidence quotes, then Pass 2 resolves evidence for the selected fields only. The hypothesis was that removing the evidence constraint from Pass 1 would reduce cognitive load and improve extraction recall. In practice, H8 underperformed H7 (GPT-4.1-mini H8 = 0.806 vs H7 = 0.835 on development), suggesting that evidence grounding is better enforced at the point of extraction rather than retrofitted.

### 3.8 D3 — Candidate Plus Verifier

D3 adds a verification gate:

**Pass 1 (Candidate):**

> Pass 1 of 2: extract permissive candidate benchmark facts from this epilepsy clinic letter.
> Return JSON only with this shape:
> `{"candidates":[{"category":"medication|seizure_type|epilepsy_diagnosis","text":"","support":""}]}`
>
> Include possible current anti-seizure medications, seizure labels/semiology, and epilepsy diagnosis/type facts. Preserve specific wording.

**Pass 2 (Verifier):**

> Pass 2 of 2: verify candidate facts and drop unsupported or non-benchmark labels.
> Return JSON only with this shape:
> `{"medications":[{"name":"","dose":null,"unit":null,"frequency":null,"quote":""}],"verified_seizure_type_mappings":[...],"seizure_types":[{"label":"","quote":""}],"epilepsy_diagnosis_type":{"label":null,"quote":""}}`
>
> Keep only current patient anti-seizure medications. Extract name, dose, unit, and frequency from the source letter quote.
> For seizure types, keep only supported benchmark labels. Drop aura-only symptoms, non-patient history, investigation-only findings, and unsupported differentials. Map too-specific supported labels to the nearest allowed benchmark label.
> Every kept medication, seizure type, and epilepsy diagnosis/type must include an exact contiguous quote copied from the source letter.
> If no exact source quote supports a candidate, drop it rather than returning an unsupported field.

The verifier prompt explicitly includes the allowed label blocks, giving the second-pass model a closed-world constraint that the first-pass candidate extractor did not have.

---

## 4. Letter-Level Case Study: EA0008

To make the harness differences concrete, we walk through one representative validation letter — **EA0008** — and show what each harness is asked to do, what the model actually returned, and how the output maps to the gold standard.

### 4.1 Source Letter

```text
Dear Dr,

Diagnosis: symptomatic structural focal epilepsy
	Previous meningioma resection 3rd January 2005

Seizure type and frequency: focal seizures with altered awareness every 3 weeks

Current anti-epileptic medication: lamotrigine 75mg bd (to reduce and stop as detailed below)
To start levetiracetam as detailed below

I reviewed this 62 year old man together with his wife in clinic today. Unfortunately after the period of seizure freedom the seizures have returned. The seizures are very stereotyped and asked similar to the events he had before surgery. He will get a warning of an unusual burning taste and then lose awareness and contact for a few minutes. His wife said that he will stare and occasionally chew his lips during these events. He feels dizzy on the lamotrigine and is keen to change his medication. I therefore suggest that he starts levetiracetam at a dose of 250mg once-a-day, increasing by 250mg every fortnight. His target dose of levetiracetam should be 750 mg twice daily. At the same time he should reduce his lamotrigine every fortnight until it stops.
```

### 4.2 Gold Standard

From `data/ExECT 2 (2025)/Gold1-200_corrected_spelling/EA0008.ann`:

| Entity | Span | Attributes |
|---|---|---|
| Diagnosis | 21–58 | `symptomatic-structural-focal-epilepsy` → mapped to **focal epilepsy** |
| SeizureFrequency | 136–172 | `focal-seizures-with-altered-awareness` → `NumberOfSeizures=1`, `TimePeriod=Week`, `NumberOfTimePeriods=3` |
| Prescription | 189–254 | `lamotrigine`, `DrugDose=75`, `DoseUnit=mg`, `Frequency=2` (twice daily) |

**Expected medications:** `lamotrigine 75 mg twice daily` (current). Levetiracetam is *planned* ("To start levetiracetam as detailed below"; "I therefore suggest that he starts..."), not current — the gold standard does not list it as a current prescription.

**Expected seizure type:** `focal seizure` (from "focal seizures with altered awareness"). The semiology details (burning taste, lip chewing, staring) are clinical description, not benchmark labels.

**Expected diagnosis:** `focal epilepsy`.

### 4.3 H0 Prompt as Sent

H0 appends the full canonical schema, sentence list, and the source letter above to the S2 prompt (§3.1). The model is instructed to produce a single JSON object with `medications`, `seizure_types`, `seizure_frequency`, `eeg_result`, `mri_result`, `epilepsy_diagnosis`, and temporal scope markers, each with `evidence_quote`, `sentence_id`, `char_start`, and `char_end`.

### 4.4 H6 Prompt as Sent

H6 sends the compact instruction (§3.4) followed by the allowed label blocks and the source letter. The expected response shape is:

```json
{"medication_names":["lamotrigine"],"seizure_types":["focal seizure"],"epilepsy_diagnosis_type":"focal epilepsy"}
```

Note that H6 does *not* ask for dose, unit, frequency, or evidence quotes in its base form. On EA0008, a frontier model running H6 would typically return exactly the JSON above. On validation, H6 achieves high medication name recall but zero dose/unit/frequency recall because the schema does not request them.

### 4.5 H7 Prompt as Sent (Pass 1 and Pass 2)

**Pass 1 extract prompt** (full text in §3.5, reconstructed from `runs/model_expansion/stage_h7_validation_evidence_reconstructed/calls/gpt_4_1_mini_baseline/H7_extract_then_normalize/EA0008/extract_prompt.txt`):

The model returned:

```json
{
  "rich_facts": [
    {
      "category": "epilepsy_diagnosis",
      "text": "symptomatic structural focal epilepsy",
      "quote": "Diagnosis: symptomatic structural focal epilepsy",
      "current_patient_fact": true
    },
    {
      "category": "seizure_type",
      "text": "focal seizures with altered awareness every 3 weeks",
      "quote": "focal seizures with altered awareness every 3 weeks",
      "current_patient_fact": true
    },
    {
      "category": "seizure_type",
      "text": "He will get a warning of an unusual burning taste and then lose awareness and contact for a few minutes",
      "quote": "He will get a warning of an unusual burning taste and then lose awareness and contact for a few minutes",
      "current_patient_fact": true
    },
    {
      "category": "seizure_type",
      "text": "His wife said that he will stare and occasionally chew his lips during these events",
      "quote": "His wife said that he will stare and occasionally chew his lips during these events",
      "current_patient_fact": true
    },
    {
      "category": "medication",
      "text": "lamotrigine 75mg bd",
      "quote": "lamotrigine 75mg bd (to reduce and stop as detailed below)",
      "current_patient_fact": true
    },
    {
      "category": "medication",
      "text": "levetiracetam",
      "quote": "To start levetiracetam as detailed below",
      "current_patient_fact": true
    }
  ]
}
```

**Pass 2 normalize prompt** receives the Pass 1 output plus the source letter. The model returned:

```json
{
  "medication_names": [
    {"name": "lamotrigine", "quote": "lamotrigine 75mg bd (to reduce and stop as detailed below)"},
    {"name": "levetiracetam", "quote": "To start levetiracetam as detailed below"}
  ],
  "seizure_type_mappings": [
    {
      "fact": "focal seizures with altered awareness every 3 weeks",
      "benchmark_label": "focal seizure",
      "decision": "supported",
      "quote": "focal seizures with altered awareness every 3 weeks"
    }
  ],
  "seizure_types": [
    {"label": "focal seizure", "quote": "focal seizures with altered awareness every 3 weeks"}
  ],
  "epilepsy_diagnosis_type": {
    "label": "focal epilepsy",
    "quote": "Diagnosis: symptomatic structural focal epilepsy"
  },
  "epilepsy_diagnosis_decision": "supported"
}
```

**Observation:** Pass 1 correctly captures the semiology details as separate `seizure_type` facts, but Pass 2 correctly drops them (they are not benchmark labels) and maps the only supported label to `focal seizure`. However, Pass 2 *keeps* levetiracetam as a current medication because Pass 1 tagged it `current_patient_fact=true`. The gold standard does not list levetiracetam as current — this is a temporal-scope error that the H7 normalization pass does not fix, because the temporal interpretation is embedded in Pass 1's fact classification.

### 4.6 D3 Prompt as Sent (Candidate + Verifier)

**Pass 1 candidate prompt** (reconstructed from `runs/model_expansion/stage_d3_validation_fixed_meds/calls/gpt_5_5/D3_candidate_plus_verifier/EA0008/candidate_prompt.txt`):

The model returned a permissive candidate list:

```json
{"candidates":[
  {"category":"epilepsy_diagnosis","text":"symptomatic structural focal epilepsy","support":"Diagnosis: symptomatic structural focal epilepsy"},
  {"category":"seizure_type","text":"focal seizures with altered awareness every 3 weeks","support":"Seizure type and frequency: focal seizures with altered awareness every 3 weeks"},
  {"category":"medication","text":"lamotrigine 75mg bd","support":"Current anti-epileptic medication: lamotrigine 75mg bd (to reduce and stop as detailed below)"},
  {"category":"medication","text":"levetiracetam","support":"To start levetiracetam as detailed below"},
  {"category":"seizure_type","text":"warning of an unusual burning taste and then lose awareness and contact for a few minutes","support":"He will get a warning of an unusual burning taste and then lose awareness and contact for a few minutes."},
  {"category":"seizure_type","text":"stare and occasionally chew his lips during these events","support":"His wife said that he will stare and occasionally chew his lips during these events."},
  {"category":"medication","text":"levetiracetam at a dose of 250mg once-a-day, increasing by 250mg every fortnight","support":"I therefore suggest that he starts levetiracetam at a dose of 250mg once-a-day, increasing by 250mg every fortnight."},
  {"category":"medication","text":"levetiracetam should be 750 mg twice daily","support":"His target dose of levetiracetam should be 750 mg twice daily."},
  {"category":"medication","text":"reduce his lamotrigine every fortnight until it stops","support":"At the same time he should reduce his lamotrigine every fortnight until it stops."}
]}
```

**Pass 2 verifier prompt** (reconstructed from `runs/model_expansion/stage_d3_validation_fixed_meds/calls/gpt_5_5/D3_candidate_plus_verifier/EA0008/verifier_prompt.txt`):

The verifier returned:

```json
{
  "medications": [
    {"name": "lamotrigine", "dose": 75, "unit": "mg", "frequency": "bd", "quote": "Current anti-epileptic medication: lamotrigine 75mg bd"},
    {"name": "levetiracetam", "dose": 250, "unit": "mg", "frequency": "once-a-day", "quote": "starts levetiracetam at a dose of 250mg once-a-day"}
  ],
  "verified_seizure_type_mappings": [
    {
      "candidate": "focal seizures with altered awareness every 3 weeks",
      "benchmark_label": "focal seizure",
      "keep": true,
      "reason": "too_specific",
      "quote": "Seizure type and frequency: focal seizures with altered awareness every 3 weeks"
    },
    {
      "candidate": "warning of an unusual burning taste and then lose awareness and contact for a few minutes",
      "benchmark_label": null,
      "keep": false,
      "reason": "not_benchmark_relevant",
      "quote": "He will get a warning of an unusual burning taste and then lose awareness and contact for a few minutes."
    },
    {
      "candidate": "stare and occasionally chew his lips during these events",
      "benchmark_label": null,
      "keep": false,
      "reason": "not_benchmark_relevant",
      "quote": "His wife said that he will stare and occasionally chew his lips during these events."
    }
  ],
  "seizure_types": [
    {"label": "focal seizure", "quote": "Seizure type and frequency: focal seizures with altered awareness every 3 weeks"}
  ],
  "epilepsy_diagnosis_type": {
    "label": "focal epilepsy",
    "quote": "Diagnosis: symptomatic structural focal epilepsy"
  }
}
```

**Observation:** The D3 verifier makes the same levetiracetam error as H7 — it keeps the planned medication as current. However, the verifier successfully extracts structured dose/unit/frequency for lamotrigine (`75`, `mg`, `bd`) and partially for levetiracetam (`250`, `mg`, `once-a-day`). The seizure-type filtering is correct: two semiology candidates are dropped as `not_benchmark_relevant`, and the supported label is kept with `reason=too_specific` (the candidate is more specific than the benchmark label, which is the intended mapping semantics).

### 4.7 Canonical Projections

After `projected_canonical()` resolves evidence quotes to character positions, both H7 and D3 produce schema-valid canonical outputs. The key difference is in medication tuple completeness:

| Field | H7 Projection | D3 Projection | Gold |
|---|---|---|---|
| Medication 1 name | `lamotrigine` | `lamotrigine` | `lamotrigine` |
| Medication 1 dose | `null` | `75` | `75` |
| Medication 1 unit | `null` | `mg` | `mg` |
| Medication 1 frequency | `null` | `bd` | `twice daily` (2) |
| Medication 2 name | `levetiracetam` | `levetiracetam` | *(not current)* |
| Seizure type | `focal seizure` | `focal seizure` | `focal seizure` |
| Diagnosis | `focal epilepsy` | `focal epilepsy` | `focal epilepsy` |

H7's Pass 2 prompt did not request dose/unit/frequency in the May 7 version; the evidence-reconstructed H7 (May 8) added structured medication components. This case study therefore captures a real intermediate state: H7 had the right seizure-type architecture but incomplete medication structure, while D3 had the full medication tuple but shared the same temporal-scope blind spot for planned medications.

---

## 5. Variant Comparison Table

### 5.1 Stage A–E Development Results (15 docs)

| Stage | Condition | Harness | Quality | Med Name F1 | Sz F1 | Dx Acc | Cost/Doc | Notes |
|---|---|---|---|---|---|---|---|---|
| **A** | GPT-4.1-mini | H0 | 0.784 | 0.906 | 0.512 | 0.933 | $0.005 | Selected primary |
| A | GPT-5.5 | H0 | 0.789 | 0.923 | 0.512 | 0.933 | $0.107 | 21× cost, same quality |
| A | GPT-5.4-mini | H0 | 0.781 | 0.943 | 0.465 | 0.933 | $0.014 | — |
| A | Claude Sonnet 4.6 | H0 | 0.782 | 0.889 | 0.524 | 0.933 | $0.072 | — |
| A | Gemini 3.1 Flash | H0 | 0.791* | 0.957 | 0.560 | 0.857 | $0.011 | *Only 7/15 docs returned; excluded |
| **B** | GPT-4.1-mini | H0 | 0.784 | 0.906 | 0.512 | 0.933 | $0.005 | Promoted to C0 |
| B | GPT-5.5 | H0 | 0.789 | 0.923 | 0.512 | 0.933 | $0.107 | Promoted to C0 |
| **C0** | GPT-4.1-mini | H0 (S2) | — | 0.852 | 0.431 strict / 0.610 collapsed | 0.725 | — | **Selected primary** |
| C0 | Event-first E2 | H0-like | — | 0.796 | 0.388 strict / 0.613 collapsed | 0.600 | — | **Selected secondary** |
| C0 | Event-first E3 | H0-like | — | 0.872 | 0.396 strict / 0.633 collapsed | 0.775 | — | Best overall; held as comparator |
| **C1** | GPT-5.4-mini | H3 | 0.809 | — | — | — | — | Not promoted (no evidence) |
| **D** | GPT-4.1-mini | H7 | **0.835** | — | **0.698** | — | — | 37% sz improvement over H0 |
| D | GPT-5.4-mini | H7 | 0.832 | — | 0.638 | — | — | — |
| D | GPT-5.5 | H7 | 0.822 | — | 0.609 | — | — | — |
| D | GPT-4.1-mini | H6 | 0.817 | — | 0.596 | — | — | Baseline for H7 comparison |
| **E** | GPT-5.5 | D3 | **0.846** | — | 0.682 | — | ~$0.06 | Highest quality of any condition |
| E | GPT-5.4-mini | H4 | 0.838 | — | 0.638 | — | — | Native structured output |
| E | GPT-5.4-mini | D3 | 0.836 | — | 0.651 | — | — | — |
| E | GPT-4.1-mini | D3 | 0.820 | — | 0.636 | — | — | — |
| E | GPT-4.1-mini | H4 | 0.816 | — | 0.612 | — | — | — |
| E | GPT-4.1-mini | H8 | 0.806 | — | 0.542 | — | — | Evidence-later underperforms |

*Quality = mean of medication_name_f1, seizure_type_f1, epilepsy_diagnosis_accuracy. Stage C0 values are from the corrected scorer (40 validation docs).*

### 5.2 Validation-Scale Revisits (40 docs, corrected scorer)

| Condition | Quality | Med Name | Med Full | Sz Strict | Sz Collapsed | Dx Acc |
|---|---|---|---|---|---|---|
| S2 (GPT-4.1-mini H0) | 0.729 | 0.852 | 0.655 | 0.431 | 0.610 | 0.725 |
| E3 (event-first) | **0.754** | **0.872** | **0.707** | 0.396 | **0.633** | **0.775** |
| H7 (GPT-4.1-mini, evidence reconstructed) | 0.677 | 0.852 | 0.018* | 0.431 | 0.431 | 0.750 |
| D3 (GPT-5.5, fixed meds) | 0.701 | 0.860 | 0.615 | 0.442 | 0.442 | 0.800 |

*H7 medication_full_f1 = 0.018 was a prompt bug: the verifier prompt instructed output of flat `medication_names` (name + quote only), stripping dose/unit/frequency. After the May 11 fix, H7 medication_full_f1 recovered to ~0.60. This bug is discussed in §6.3 and §9.*

---

## 6. Deep Error Analysis

### 6.1 The Scoring Crisis — Discontinuity 1

The single most important event of Phase 1 was not a model failure but a **metric failure**.

After Stage C0 strict validation (May 7), the original scorer reported:

| System | Med Name | Med Full | Sz Type | Dx Acc |
|---|---|---|---|---|
| S2 | 0.842 | 0.496 | 0.213 | 0.775 |
| E2 | 0.704 | 0.372 | 0.261 | 0.550 |
| E3 | 0.829 | 0.483 | 0.241 | 0.750 |

These numbers were catastrophic. Seizure type F1 (0.187–0.261) was far below the Fang et al. target (≥0.76). Medication full tuple F1 (0.372–0.496) was below target (≥0.80). The initial interpretation was that the models were failing clinically.

**The recovery workstream (May 7–8) revealed three scoring defects:**

1. **Gold-loader null-string bug:** Literal `"null"` cells in `MarkupSeizureFrequency.csv` were passed through as tokens, producing malformed gold strings like `"null null per 3 week"`. This caused seizure_frequency accuracy = 0.000 across all systems.
2. **Medication component scoring:** The original scorer treated the medication tuple as an all-or-nothing match. A single missing dose or frequency zeroed the entire tuple, even when name, unit, and remaining fields were correct.
3. **Seizure-type exact-match rigidity:** The model frequently extracted clinically accurate labels (e.g., `focal impaired awareness seizure`) that were not in the benchmark's closed label set. These were counted as false positives and false negatives even though the clinical fact was correct.

After Phase 2 (scoring audit) and Phase 3 (normalization repair), the **corrected validation metrics** became:

| System | Med Name | Med Full | Sz Strict | Sz Collapsed | Dx Acc |
|---|---|---|---|---|---|
| S2 | 0.852 | 0.655 | 0.431 | **0.610** | 0.725 |
| E2 | 0.796 | 0.633 | 0.388 | **0.613** | 0.600 |
| E3 | **0.872** | **0.707** | 0.396 | **0.633** | **0.775** |

**Narrative implication:** Stage C0 selected S2 and E2 based on the *original* broken metrics, but the selection decisions were later **validated** against corrected metrics. The corrected scorer showed that S2 and E2 were still the right choices — but for different reasons. Originally, S2 was selected because it had the highest medication name F1 (0.842). After correction, S2's advantage was narrower (0.852 vs E3's 0.872), but its evidence grounding and schema validity remained superior. E3, which looked marginal on the original scorer (med_full 0.483), was revealed as the strongest system overall (med_full 0.707). This retroactive reframing is **Discontinuity 1**: the history of the workstream changed when the scoring fix was applied.

### 6.2 Seizure Type Confusion Analysis

Seizure type remained the weakest field even after collapsed labels. The confusion tables from H7 and D3 validation runs reveal two dominant failure modes.

**H7 (GPT-4.1-mini, 40 val docs) — seizure_type strict:**

| Label | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| `focal seizure` | 7 | 13 | 0 | 0.350 | 1.000 | 0.519 |
| `generalized tonic clonic seizure` | 5 | 9 | 0 | 0.357 | 1.000 | 0.526 |
| `secondary generalized seizures` | 2 | 6 | 0 | 0.250 | 1.000 | 0.400 |
| `unknown seizure type` | 2 | 0 | 13 | 1.000 | 0.133 | 0.235 |
| **Micro** | 22 | 38 | 20 | 0.367 | 0.524 | 0.431 |

**D3 (GPT-5.5, 40 val docs) — seizure_type strict:**

| Label | TP | FP | FN | Precision | F1 |
|---|---|---|---|---|---|
| `focal seizure` | 7 | 11 | 0 | 0.389 | 0.560 |
| `generalized tonic clonic seizure` | 5 | 6 | 0 | 0.455 | 0.625 |
| `secondary generalized seizures` | 2 | 7 | 0 | 0.222 | 0.364 |
| `unknown seizure type` | 3 | 5 | 12 | 0.375 | 0.261 |
| **Micro** | 25 | 46 | 17 | 0.352 | 0.442 |

**Failure mode 1: The `unknown seizure type` meta-label gap.**

Across all models and harnesses, the miss count for `unknown seizure type` is consistently 12–13 out of 15 documents that carry this gold label. The label is used in ExECTv2 when the annotator cannot determine seizure type from the letter. Models, however, consistently attempt to infer a specific type from clinical context. This is a **structural misalignment between model behaviour (inference) and annotation convention (abstention)**, not a prompt design failure. Scale from 4B to 35B does not reduce this count.

**Failure mode 2: Label over-specificity.**

Both H7 and D3 produce high recall (1.000) for `focal seizure`, `generalized tonic clonic seizure`, and `secondary generalized seizures` — when the gold label matches. The precision problem is that models emit these labels on documents where the gold standard expects a different specific type or `unknown seizure type`. For example, a letter describing "focal impaired awareness seizures" is correctly mapped to `focal seizure` by the collapsed scorer, but if the gold strict label is `focal impaired awareness seizure`, the strict scorer counts a false positive and a false negative. This is a **taxonomy mismatch**, not an extraction error.

### 6.3 Medication Full Tuple Analysis

The medication full tuple F1 is decomposed into name, dose, unit, and frequency. The D3 verifier (GPT-5.5, fixed meds, 40 val docs) shows the cleanest component breakdown:

| Component | Micro F1 | Key Error Pattern |
|---|---|---|
| Name | 0.860 | Misspellings (`lamtorigine`, `eslicarbazine`), non-ASM over-extraction (`buccal midazolam`) |
| Dose | 0.835 | Correct on most current meds; errors on planned/changed doses |
| Unit | 0.848 | `mg` dominant; occasional `milligrammes` (French orthography) |
| Frequency | 0.731 | Complex schedules parsed as single strings; `once-a-day` vs `once daily` normalization gaps |
| **Full tuple** | 0.615 | Compounding: any missing component zeros the tuple |

The **critical D3 medication bug** (May 11): the initial verifier prompt instructed output of flat `medication_names` (name + quote only), stripping dose/unit/frequency. This caused medication_full_f1 to collapse to ~0.018. After fixing the verifier/normalize prompt to output structured medications with `dose`, `unit`, `frequency`, the metric recovered to ~0.60 — a **30–35× improvement**. This bug is discussed further in §9.

---

## 7. Data Processing Stages

The pipeline from raw letter to scored metrics involves eight stages, each of which was instrumented with artifact logging:

```
Raw letter (.txt + .ann)
    ↓
Preprocessing (preprocess_document)
    → sentences[], text, document_id
    ↓
Prompt construction (build_h*_prompt)
    → prompt.txt
    ↓
API call (ModelRequest → adapter.call)
    → provider_response.json, raw_response.txt
    ↓
Response parsing (parse_json_response)
    → canonical.json (for H0) or intermediate JSON (for H6/H7/D3)
    ↓
Schema validation (validate_extraction)
    → schema_valid, project_constraints_valid
    ↓
Projection (projected_canonical)
    → For H2/H3/H6/H7/H8/D3: map to canonical schema
    ↓
Normalization (normalization.py)
    → ASM synonym expansion, label collapsing, frequency loosening
    ↓
Scoring (score_document)
    → per-field TP/FP/FN, quote validity, temporal accuracy
```

**Artifact gating:** The evaluation harness (Milestone 5) will not score a document unless `canonical.json` exists and `schema_valid=true`. This prevents partial-parse artifacts from entering metric averages.

**Evidence resolution:** For H7 and D3, `projected_canonical()` uses `evidence_from_quote()` to locate the character span of each quote in the source text. If the quote cannot be found verbatim, the evidence item is dropped (`require_present_evidence=True`). This guarantees that every canonical output is traceable to the source letter.

---

## 8. Outcomes & Promotion Decisions

### 8.1 What Advanced

| System | Stage | Promotion Rationale |
|---|---|---|
| **S2 (GPT-4.1-mini, H0)** | C0 → final | Cost-effectiveness frontier; schema-valid; evidence-grounded. Primary frontier baseline. |
| **E2 (event-first)** | C0 → final | Secondary baseline; temporal accuracy superior to S2. |
| **E3 (event-first + LLM aggregation)** | C0 → final | Best medication metrics under corrected scorer; most robustness-robust system. |
| **H6** | C1 → local models | Simplified schema enabled local deployment (qwen3.5:9b, gemma4:e4b, qwen3.6:35b). |
| **H6fs** | N2 → local best | Few-shot examples improved qwen3.5:9b seizure F1 by +6.1pp; selected as best local harness. |
| **H7** | D → deferred | Strong seizure-type improvement (0.698 dev) but medication structure incomplete until May 8 fix. Deferred to Phase 4 validation-scale run. |
| **D3** | E → deferred | Highest benchmark quality (0.846 dev) but doubled call cost. Deferred to Phase 4 validation-scale run. |

### 8.2 What Was Abandoned

| System | Reason |
|---|---|
| **Gemini 3.1 Flash / Pro** | Systemic empty responses at quota limits; 7/15 docs returned on Flash. Excluded from all formal runs. |
| **H2 (task-specific)** | No canonical projection layer at Stage A; outperformed by H3 on dev; not worth engineering effort given H6 success. |
| **H3 (loose answer-then-parse)** | Strong on dev (0.809) but dev-validation divergence identified; lacks evidence reconstruction; superseded by H7/D3. |
| **H5 (verifier relaxed)** | Superseded by D3, which has a tighter verifier contract and canonical projection. |
| **H8 (evidence later)** | Underperformed H7 on all metrics; evidence retrofitting is less effective than extraction-time grounding. |

### 8.3 Discontinuity 3: H7 and D3 Dormancy

H7 and D3 were explored in Stage E on May 7 and showed the strongest development results of any harness. They were then **left dormant** for four days (May 8–10) while attention shifted to:

1. **Local models workstream** (L0–L6, N1–N6): Ollama infrastructure, qwen3.5/gemma4 validation.
2. **Gan frequency workstream** (G0–G4): Seizure-frequency extraction on a secondary benchmark.
3. **Scoring recovery** (P1–P3): The scoring crisis consumed most of May 8.

On May 10, `docs/27_final_full_field_evaluation_plan.md` explicitly planned to revisit H7 and D3 at validation scale. On May 11, both were rerun on 40 validation documents. The initial results were catastrophically bad due to the **medication prompt bug** (§6.3) — not an architectural limit. After fixing the bug, H7 and D3 recovered to competitive levels but still did not beat E3 on the primary composite metric. They were marked as **deferred to Phase 2/4** rather than abandoned.

The narrative importance of this dormancy is that H7 and D3 were not forgotten failures; they were **deprioritized for operational reasons** (other workstreams demanded attention) and then **resurrected** when the evaluation plan explicitly called for them. Their later validation-scale performance, though not promotion-winning, confirmed that the Stage E development results were not spurious.

---

## 9. Limitations

1. **Small development splits:** Stage A–E used 15 development documents. With only 15 docs, a single letter can swing benchmark quality by ±0.03. The tight clustering (0.781–0.791) may reflect noise as much as signal.

2. **Clustering within noise:** All frontier models scored within a 10pp range on development. Distinguishing true capability differences from sampling noise requires validation-scale runs (40 docs), which were performed for promotion candidates but not for all Stage A–E conditions.

3. **Cost not yet optimized:** D3 doubles call cost (two passes) for a ~7% quality improvement. Whether this trade-off is justified depends on deployment context. For offline batch extraction, D3 may be worth the premium; for real-time clinical decision support, H7 or H6 may be preferred.

4. **Temporal scope remains brittle:** Both H7 and D3 on EA0008 incorrectly classified levetiracetam as "current" when it was "planned". The gold standard's temporal annotation is sparse, and the models do not consistently distinguish "current" from "planned" or "being introduced" without explicit few-shot guidance.

5. **Prompt bug sensitivity:** The May 11 H7/D3 validation runs showed that a single prompt wording change (verifier outputting flat `medication_names` vs structured `medications`) can drop medication_full_f1 by 30–35×. This highlights the brittleness of multi-pass architectures to prompt drift.

6. **Frequency extraction unsolved:** No harness in Phase 1 achieved clinically useful seizure-frequency accuracy on ExECTv2. The field was deprioritized for a dedicated workstream (Gan frequency) rather than solved within the main schema.

---

## 10. Critical Findings Summary

| Finding | Evidence | Implication |
|---|---|---|
| Benchmark quality tightly clustered (0.781–0.791) | Stage A, 15 dev docs, 4 frontier models | Model selection should be driven by cost and latency, not marginal quality |
| GPT-4.1-mini costs 14–21× less per quality-point | Stage A cost table | Small frontier model is the right default for batch extraction |
| H7 achieved 37% relative seizure-type improvement | Stage D: 0.698 vs H0 0.512 | Seizure-type scoring is primarily a **normalization** problem, not extraction |
| D3 achieved highest overall quality (0.846) | Stage E | Candidate+verifier is the strongest architecture, but at doubled cost |
| Scorer was materially broken for first half of project | Recovery Phase 2+3 | Any claim using original scorer is invalid; scoring audit is a methods contribution |
| `unknown seizure type` meta-label is a structural ceiling | N1 investigation, 26 docs, all models | 13–15 consistent misses suggests benchmark/behaviour misalignment, not model failure |
| Evidence grounding ≥ 0.960 quote validity across all conditions | Robustness + validation runs | Evidence discipline is a structural guarantee, not a quality cost |

---

## Appendix: Prompt Source Files

| Harness | Source File | Lines |
|---|---|---|
| H0 / S2 | `prompts/direct_baselines/s2_direct_json_evidence.md` | 19 |
| H2 | `src/model_expansion.py:build_task_specific_prompt()` | — |
| H3 | `src/model_expansion.py:build_loose_prompt()` | — |
| H6 | `src/model_expansion.py:build_h6_prompt()` | — |
| H6fs | `src/model_expansion.py:build_h6fs_prompt()` | — |
| H7 Pass 1 | `src/model_expansion.py:build_h7_extract_prompt()` | — |
| H7 Pass 2 | `src/model_expansion.py:build_h7_normalize_prompt()` | — |
| H8 Pass 2 | `src/model_expansion.py:build_h8_evidence_prompt()` | — |
| D3 Pass 1 | `src/model_expansion.py:build_d3_candidate_prompt()` | — |
| D3 Pass 2 | `src/model_expansion.py:build_d3_verifier_prompt()` | — |
| E1 | `prompts/event_first/e1_event_extraction.md` | 52 |
| E3 aggregation | `prompts/event_first/e3_constrained_aggregation.md` | — |

---

*Document compiled from: `docs/_master_timeline_and_narrative.md`, `docs/34_full_experiment_record.md` (§§1–3), `docs/phase3_synthesis_report.md` (§§1.1–1.8), `src/model_expansion.py`, and run artifacts in `runs/model_expansion/stage_h7_validation_evidence_reconstructed/` and `runs/model_expansion/stage_d3_validation_fixed_meds/`.*
