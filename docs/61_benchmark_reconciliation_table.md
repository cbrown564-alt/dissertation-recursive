# Benchmark Reconciliation Table

**Date:** 2026-05-13  
**Status:** Initial reconciliation table for final-claim discipline  
**Source agenda:** `docs/58_phase_review_research_agenda.md`, sections 8, 9.10, and 10.7  
**Purpose:** Prevent the dissertation from treating Fang, ExECTv2, and Gan as a single ladder of benchmark difficulty when they operationalize different tasks, label spaces, and scoring rules.

This document is the claim-discipline companion to
[`docs/19_benchmark_crosswalk.md`](19_benchmark_crosswalk.md). The earlier
crosswalk focused on Fang-to-local field mapping during the performance
recovery phase. This table is broader: it reconciles Fang, ExECTv2, and Gan as
separate benchmarks and records what kinds of external claims each one can and
cannot support.

## Reconciliation Table

| Benchmark | Task definition | Unit of prediction | Label taxonomy | Temporal policy | Evidence expectation | Gold source | Scoring rule | Published target | Comparability limits | Valid claim type |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fang et al. 2025 | Multi-task epilepsy-letter extraction covering epilepsy type, seizure type, current ASMs, and associated symptoms. The tasks are short, task-specific extraction prompts rather than full-schema canonical extraction. | Label instances per task. Epilepsy type, seizure type, and symptoms are multi-label category decisions; current ASM is multi-label medication-name detection over a fixed dictionary. | Coarse benchmark taxonomies: epilepsy type `generalized`, `focal`, `combined generalized/focal`, `unknown`; seizure type `generalized`, `focal`, `unknown`; current ASM names from a fixed ASM dictionary; associated symptoms from a 7-item checklist. | Current-state oriented. Current ASM is explicitly current medication, and seizure/epilepsy categories are benchmark labels rather than temporally rich event representations. | No quote-bearing evidence requirement in the reported benchmark tasks. | King's College Hospital epilepsy clinic letters as reported in Fang et al.; benchmark defined by the paper and released code. | Repeated extraction runs with micro-aggregated precision/recall/F1 over label instances. | Reported targets used in this project: epilepsy type F1 about 0.80, seizure type F1 about 0.76, current ASM F1 about 0.90, associated symptoms F1 about 0.63. | Only parts of the local pipeline are comparable. Medication-name extraction is directly comparable after ASM synonym normalization. Epilepsy and seizure type are only comparable through derived collapsed labels. Full medication tuple, diagnosis granularity, temporality, evidence support, and canonical-schema validity are stricter local tasks, not Fang-equivalent tasks. | External benchmark comparison for medication names and collapsed seizure/epilepsy-type views; metrological caveat about coarse label alignment; not a valid umbrella claim for full-schema clinical extraction. |
| Fonferko-Shadrach et al. 2024 / ExECTv2 | Broad epilepsy-letter information extraction with typed annotations, including seizure frequency, diagnosis, investigations, medications, and other clinical entities. The seizure-frequency benchmark measures extraction of all stated frequency mentions, including historical and seizure-free references. | Annotated entity mentions and per-letter presence, depending on the metric. For seizure frequency, multiple mentions per letter are expected. | ExECTv2 typed annotations plus BRAT/CUI mappings. For seizure frequency, labels are mention-level spans with attributes rather than a single normalized frequency class. | Explicitly multi-temporal. The annotation definition includes current, historical, changed, and seizure-free frequency mentions tied to time periods or visits. | Annotation benchmark, not a quote-grounding benchmark. Gold evidence is annotation span based rather than model-emitted quote based. | ExECTv2 annotated epilepsy clinic letters and the accompanying rule-based GATE benchmark. | Seizure frequency reported as per-item F1 = 0.66 and per-letter F1 = 0.68. Human inter-annotator agreement for seizure frequency = 0.47. Other fields use the dataset's typed annotation setup rather than Fang-style coarse labels. | Seizure-frequency-specific published targets: 0.66 per-item F1 and 0.68 per-letter F1 for the rule-based benchmark. Human IAA 0.47 contextualizes task ambiguity. | Local single-value `current_seizure_frequency_*` metrics are not directly comparable because they score one normalized current frequency rather than all mentions. ExECTv2 is the right benchmark for broad corpus continuity, temporality challenge construction, and mention-level extraction difficulty, but not for claiming parity on Gan-style single-label frequency normalization. | Crosswalk and dataset-validity claims; mention-level extraction claims when the scoring view matches the benchmark; not a valid direct comparison for single-label normalized seizure-frequency systems unless the scorer is redesigned to match ExECTv2's unit of prediction. |
| Gan et al. 2026 | Dedicated seizure-frequency normalization benchmark. The task is to read a letter and return one normalized seizure-frequency label that can be converted into Purist 10-bin and Pragmatic 4-class seizure/month categories. | One normalized frequency label per document. | Two derived evaluation taxonomies: Purist 10-bin monthly-frequency categories and Pragmatic 4-class categories (`infrequent`, `frequent`, `UNK`, `NS`). | Collapses the letter into one benchmark target frequency state. Historical and current mentions are resolved into one normalized label, so it is a frequency-normalization task rather than an all-mentions temporal extraction task. | Gan-style harnesses can request evidence spans, but the headline benchmark is label accuracy / category F1 rather than evidence-support scoring. | Gan 2026 synthetic letters for development; published headline results were measured on a clinician double-checked independent real-letter test set, while this repo currently uses the released 1,500-document synthetic subset. | Micro-F1 on Purist and Pragmatic category mappings after normalization; for the single-label task, Pragmatic micro-F1 behaves like accuracy. | Published headline targets: Qwen2.5-14B CoT(15000) Pragmatic micro-F1 0.847 and MedGemma-4B CoT(15000) 0.858 on the independent real-letter test set. Local project target has therefore been Pragmatic micro-F1 >= 0.85, with explicit caveats when measured on the released synthetic subset. | Strongly comparable for seizure-frequency normalization only. It is not comparable to Fang's multi-field benchmark or ExECTv2's all-mentions frequency extraction without caveats. Synthetic-subset results in this repo must not be described as direct replication of Gan's real-letter headline numbers. | Primary benchmark claim for seizure-frequency normalization, provided the claim states whether evaluation used the local synthetic subset or Gan's published real-letter setting; not a valid benchmark for medication, diagnosis, seizure type, or evidence-grounding claims. |

## Benchmark-Specific Guidance

### Fang 2025

- Use Fang for externally recognizable comparisons on current ASM name
  extraction and collapsed epilepsy/seizure-type label views.
- Do not use Fang as the comparator for medication tuples, evidence support,
  quote validity, schema validity, or temporality-sensitive extraction.
- When reporting against Fang, say explicitly that the local system is being
  viewed through a derived coarse benchmark slice rather than evaluated on an
  identical task.

### ExECTv2

- Use ExECTv2 as the core dataset continuity benchmark for the dissertation's
  broader extraction pipeline.
- Use ExECTv2 challenge slices for temporality, abstention, diagnosis
  granularity, medication tuple behavior, and projection-policy audits.
- Do not compare the current local single-value seizure-frequency metric
  directly to ExECTv2's 0.66 or 0.68 figures unless the scorer is aligned to
  the benchmark's unit of prediction.

### Gan 2026

- Use Gan as the primary benchmark for seizure-frequency normalization.
- Distinguish carefully between results on the released synthetic subset and
  Gan's published clinician double-checked real-letter test set.
- Treat Gan-style retrieval, reasoning, and normalization results as
  seizure-frequency-specific findings, not evidence that the same architecture
  transfers automatically to ExECTv2 full-field extraction.

## Claim Discipline Rules

1. Medication name claims may be benchmarked externally against Fang once ASM
   synonym and brand normalization are aligned.
2. Seizure-type and epilepsy-type claims should be split into benchmark-
   collapsed label claims for Fang comparability and fine-grained clinical
   label claims for dissertation-specific analysis.
3. Seizure-frequency claims should be split into ExECTv2 mention-level
   continuity claims when scored on ExECTv2 terms and Gan normalization claims
   when scored on Gan's single-label category terms.
4. Evidence-support, quote validity, projection delta, schema validity,
   medication tuple completeness, and deployment-profile conclusions are local
   extensions. They should not be written as if Fang or Gan benchmark them.

## Immediate Consequences For Final Writeup

- The dissertation should not present Fang, ExECTv2, and Gan as a simple
  sequence from easier to harder benchmarks. They test different objects.
- A strong overall claim can still be made, but it must be field-specific:
  Fang-aligned current ASM names, ExECTv2-aligned broad corpus extraction and
  temporality slices, and Gan-aligned seizure-frequency normalization.
- Any headline statement about "benchmark parity" must name the benchmark, the
  exact task view, and the evaluation setting.
