# Literature Review Matrix

This review supports implementation decisions for the dissertation rather than providing a broad history of clinical NLP. The guiding rule is synthesis first: sources are grouped by the design question they answer, then individual papers are used as evidence for schema, pipeline, and evaluation choices.

## Literature Review Practice Used

Before drafting the review, I used three practical literature-review principles:

- Organize by themes and decision questions, not by one-paper-at-a-time summaries. Purdue OWL frames a literature review as sources "in conversation" and emphasizes synthesis, analysis, interpretation, and critical evaluation rather than paraphrase alone.
- Use a synthesis matrix to compare sources against shared themes. Johns Hopkins' library guidance treats the matrix as a way to record each source's main points and how sources relate to each other.
- Preserve critique. A dissertation review should state what a paper makes possible, where its evidence is weaker, and how that affects the current project's design.

Best-practice sources consulted:

- Purdue OWL, [Writing a Literature Review](https://owl.purdue.edu/owl/research_and_citation/conducting_research/writing_a_literature_review.html)
- Purdue OWL, [Synthesizing Sources](https://owl.purdue.edu/owl/research_and_citation/conducting_research/research_overview/synthesizing_sources.html)
- Johns Hopkins Libraries, [Synthesize: Write a Literature Review](https://guides.library.jhu.edu/lit-review/synthesize)

## Review Scope

The literature was reviewed against five strands:

1. Epilepsy information extraction from clinic letters and electronic health records.
2. Clinical NLP for temporality, negation, uncertainty, and assertion status.
3. LLM-based clinical information extraction and structured output reliability.
4. Evidence-grounded, citation-grounded, or span-supported extraction.
5. Open/local versus closed/frontier models in clinical or privacy-sensitive settings.

The review is intentionally bounded. It does not attempt to survey all epilepsy AI, EEG seizure detection, clinical summarization, or general LLM benchmarking. Those areas matter clinically, but they do not directly answer whether event-first, evidence-grounded extraction improves structured extraction from epilepsy clinic letters.

## Synthesis

### 1. Epilepsy NLP Already Supports The Target Field Set

The strongest epilepsy-specific precedent is ExECT, a GATE-based system developed to extract structured epilepsy information from unstructured clinic letters. ExECT extracted epilepsy diagnosis, epilepsy type, focal and generalized seizure types, seizure frequency, medication, CT, MRI, EEG, clinic date, and date of birth from 200 de-identified Welsh clinic letters, reporting overall per-item precision 91.4%, recall 81.4%, and F1 86.1%. Its best epilepsy-specific results were for medication, diagnosis, epilepsy type, and focal seizure type, while seizure frequency and investigations were harder.

ExECTv2 and the 2024 synthetic annotated epilepsy-letter corpus are especially important for this dissertation because they provide a public benchmark aligned with the planned dataset. The synthetic corpus includes 200 UK outpatient epilepsy clinic letters, double annotation, consensus gold labels, and guidelines. It covers diagnosis, epilepsy type/syndrome, seizure type, investigations, current antiseizure medications with dose/unit/frequency, seizure frequency including seizure freedom, and timing-related entities. The reported human inter-annotator agreement was F1 0.73 per item; ExECTv2 achieved F1 0.87 per item and 0.90 per letter against the consensus standard. Seizure frequency remained one of the weakest categories, with per-item F1 0.66 and per-letter F1 0.68.

These results justify the primary target field set in this dissertation. Current medication with dose/unit/frequency, seizure frequency, seizure type, EEG/MRI result, and epilepsy diagnosis/type are not arbitrary fields: they are core information types repeatedly targeted in epilepsy NLP and natively present in the ExECTv2 synthetic annotation guidelines. Broader medication-status and investigation-status distinctions remain clinically important, but should be treated as extension analyses unless manually adjudicated. The review also shows why the dissertation should not treat all fields as equally difficult. Medication is comparatively structured; seizure frequency and investigations are more variable and should be primary fields for event-first benefit.

### 2. Seizure Frequency Requires Event-Level Representation

Seizure frequency is both clinically important and linguistically awkward. The 2024 synthetic epilepsy-letter corpus notes that seizure frequency is recorded in varied formats, can refer to several event types in one letter, and often reads as patient narrative rather than a tidy measurement. ExECT's weaker seizure-frequency performance reinforces this.

Xie et al. framed seizure-frequency extraction from epilepsy clinic notes as machine reading rather than simple entity recognition. Their pipeline asked whether the patient had recent seizures, how often seizures occurred, and when the most recent seizure happened. This is conceptually close to the present dissertation's event-first design: a frequency statement is not just a number, but a claim with recency, event type, and temporal context.

Abeysinghe et al. further decomposed seizure-frequency extraction into phrase extraction and attribute extraction from epilepsy monitoring-unit evaluation reports. Their structured output combined seizure event, quantity, duration, and temporal unit. GPT-4 performed best among the evaluated BERT-based and generative models, with F1 85.82% for final structured seizure frequency. The paper also explicitly categorized text that lacks extractable frequency, including vague phrases, inability to determine frequency, and long-term remission.

For this dissertation, seizure frequency should therefore be represented as an event with:

- a normalized value, such as `seizure_free`, `weekly`, `monthly`, or `count_per_period`;
- a temporal scope, such as `since_last_visit`, `past_6_months`, or `last_year`;
- an optional seizure type linkage;
- temporality, especially `current`, `historical`, and `uncertain`;
- evidence quote.

The final current seizure-frequency field should be derived conservatively. A current seizure-free statement should override older "previously weekly" history, but a vague "better recently" should not be normalized into a frequency unless the letter states enough detail.

### 3. Temporality And Assertion Status Are Core Clinical NLP Problems

Clinical NLP has long treated negation, uncertainty, temporality, and experiencer as modifiers of extracted concepts rather than as optional metadata. NegEx showed that detecting negated findings in clinical reports can often be handled with lexical triggers and scoped rules. ConText extended this idea to negation, temporality, and experiencer, labelling whether conditions are negated, hypothetical, historical, or experienced by someone other than the patient. Harkema et al. also noted an important limit: distinguishing historical from recent conditions sometimes requires knowledge beyond local surface clues.

This maps directly onto epilepsy clinic letters. "No seizures since lamotrigine was increased", "mother had epilepsy", "will arrange an EEG", "previously had weekly focal seizures", and "possible temporal lobe epilepsy" must not all become present patient-level facts. The canonical schema's event temporality labels are therefore justified by prior clinical NLP:

- `current`: affirmed patient-level present or most recent status.
- `historical`: prior status, previous treatment, previous seizure frequency, or past investigation.
- `planned`: future management, such as medication change.
- `requested`: investigation ordered but not completed.
- `completed`: investigation performed, with result if stated.
- `family_history`: condition belongs to someone other than the patient.
- `hypothetical`: conditional, rule-out, or proposed possibility.
- `uncertain`: hedged or insufficiently resolvable statement.

The schema should keep missingness separate from temporality. `not_stated` means there is no relevant evidence; `uncertain` means there is relevant text but the value cannot be resolved; `conflicting` means incompatible evidence is present. This distinction is important because LLMs may otherwise fill blanks with plausible clinical defaults.

### 4. Medication Extraction Needs Events, But Primary Scoring Should Stay Current

Medication extraction is a relatively strong category in ExECT and ExECTv2, partly because antiseizure medication entries often follow recognizable dose and frequency patterns. The primary ExECTv2-native task should therefore score current ASM name, dose, dose unit, and frequency. Broader status distinctions such as previous, stopped, declined, planned, increased, and reduced medication are useful event labels, but should be evaluated as extension outputs unless a manually adjudicated gold set is created.

Medication change work in clinical NLP supports treating medication as an event with status and temporality. A medication event can describe a current prescription, a historical adverse reaction, a planned titration, a patient declining treatment, or a stopped drug. These should not collapse into a single medication list.

Implementation decision for event extraction:

- Current medication requires evidence of current use, continuation, prescription, or plan-in-effect.
- Previous medication is supported by prior trial, stopped/discontinued wording, adverse-effect history, or "previously on".
- Planned medication change should not update current medication unless the letter states it has already happened.
- Dose increases and reductions should be represented as medication-change events with `status: increased` or `reduced`, while the final current dose should be `uncertain` if the resulting dose cannot be resolved.
- Declined medication should be a medication event with `status: declined`, not a current or previous medication.

### 5. Investigation Extraction Must Distinguish Order Status From Result

ExECT extracted CT, MRI, and EEG categories and classified investigation results as normal or abnormal, but performance for MRI and EEG was lower than medication. The 2024 annotation guidelines include EEG, CT, and MRI results annotated as normal, abnormal, or unknown when a result is stated. For the primary ExECTv2-native evaluation, EEG and MRI scoring should focus on annotated results. The event schema can still separate order/completion status from result because clinic letters often mention requested, pending, completed, unavailable, normal, or abnormal investigations, but requested/pending/unavailable statuses should be reported as extension outputs unless manually adjudicated.

Implementation decision:

- "EEG requested" or "MRI to be arranged" supports `status: requested` and `result: not_stated`.
- "Awaiting MRI" supports `status: pending` or `requested`, depending on the schema vocabulary, and no result.
- "MRI normal" supports `status: completed`, `result: normal`.
- "EEG showed temporal sharp waves" supports `status: completed`, `result: abnormal`.
- "No MRI available" supports `status: unavailable`, if added, or `uncertain/not_stated` with evidence; it should not be scored as normal.

The schema should keep investigation `status` and `result` separate:

- `status`: `requested`, `pending`, `completed`, `unavailable`, `not_stated`, `uncertain`
- `result`: `normal`, `abnormal`, `not_stated`, `uncertain`

If the schema must stay narrower for the first implementation, use `requested`, `completed`, and `uncertain` for status, with result handled separately.

### 6. Evidence Spans Should Be Scored In Two Layers

Evidence-grounded extraction is necessary because valid structured output is not the same as supported clinical output. LLM extraction work shows that models can produce structured answers in zero-shot and few-shot settings, but the clinical risk lies in unsupported values, wrong temporal attribution, and overconfident inference.

The evidence requirement should therefore be stricter than "the model wrote a quote." The evaluation protocol should separate:

- quote presence: did the output include an evidence quote?
- quote validity: does the exact quote appear in the source text?
- semantic support: does the quote support the extracted value?
- temporal support: does the quote support the extracted temporality/status?
- field correctness: does the final normalized field match the gold label?

Exact quote matching is useful as a mechanical check, but it is not enough. A quote can appear in the letter and still support the wrong field if it refers to historical seizures, a family member, a planned investigation, or an uncertainty statement. Semantic evidence support should be judged against the combination of value plus temporality.

For initial implementation, exact quote matching should be automatic. Semantic and temporal support can be scored manually on a validation subset, or by rule-assisted adjudication where gold evidence spans are available. The dissertation should report unsupported extraction rate separately from field accuracy.

### 7. LLMs Are Plausible Extractors, But Reliability Must Be Measured

Agrawal et al. showed that general-purpose LLMs can perform zero-shot and few-shot clinical information extraction, including span identification, sequence classification, and relation extraction, despite not being trained specifically for clinical text. This supports a training-free or minimal-training dissertation design.

More recent clinical IE comparisons complicate the picture. A 2026 JAMIA study comparing instruction-tuned LLaMA models with BERT across named entity recognition and relation extraction found LLaMA models could outperform BERT, especially under limited-data or unseen-dataset conditions, but with much higher computational cost and slower throughput. This supports reporting cost and latency alongside accuracy rather than treating model performance as a leaderboard.

For this dissertation, the model-family comparison should be small and controlled:

- one strong closed/frontier model;
- one smaller closed or cost-efficient model, if budget allows;
- one or two open/local models selected for practical deployability;
- identical prompts, schemas, decoding settings where possible, and scoring.

The research question is not "which model is best?" It is whether the event-first design improves reliability under realistic model choices, and whether open/local models remain viable when evidence checking and schema validation are strict.

### 8. Structured Output Format Affects Parseability, But Not Clinical Truth

Structured output research supports using a canonical JSON representation for validation and scoring. Grammar-constrained decoding can improve well-formedness for structured prediction, and clinical structured-output robustness work has found JSON more parseable than YAML and XML for small language models, with parseability affected by model size, prompt specificity, document length, and note type.

However, structured output validity does not guarantee semantic correctness. Materials-science LLM extraction work shows that exact-match scoring can understate semantically equivalent extraction, while structured-output benchmarks and clinical parseability studies show the reverse risk: a valid object may still contain wrong values. The dissertation should therefore treat JSON/YAML/XML questions as secondary engineering questions:

- canonical internal format: JSON;
- model-facing comparison: JSON versus YAML-to-JSON only if implementation time allows;
- parse metrics: raw parse success, repair rate, schema validity, type correctness;
- clinical metrics: field accuracy, temporal accuracy, evidence support.

Repair loops should be limited and logged. A repair step may fix syntax or convert YAML to JSON, but it must never add unsupported clinical content.

## Decision Outputs For Implementation

### Field-Definition Notes

| Field | Literature-supported definition | Implementation rule |
| --- | --- | --- |
| Current antiseizure medication | Current ASM with dose/unit/frequency is explicitly annotated in ExECTv2. | Include only medications supported as currently taken, prescribed, or continued. |
| Previous antiseizure medication | Prior treatment history matters clinically but is not a primary ExECTv2-native gold field. | Extract as extension medication events only unless manually adjudicated. |
| Medication dose/status | Current ASM dose/unit/frequency is ExECTv2-native; broader changes require event status. | Score current dose/unit/frequency primarily. Extract status on events for extension analysis. |
| Seizure frequency | ExECT, Xie et al., and Abeysinghe et al. all show frequency requires temporal and event context. | Extract frequency events with scope, seizure type if stated, current/historical/uncertain temporality, and evidence. |
| Seizure type | ExECT and ExECTv2 annotate seizure type and map to focal/generalized categories. | Extract as stated; normalize only to conservative categories unless specific type is explicit. |
| EEG/MRI result | ExECT extracts investigations; ExECTv2 annotates EEG/MRI results. | Score annotated normal/abnormal/unknown results primarily. Log requested/pending/unavailable status as extension events. |
| Diagnosis/type | ExECT requires explicit diagnosis/type and certainty. | Use explicit diagnosis/type only. Possible epilepsy should be `uncertain`, not invented. |

### Temporal-Label Justification

| Label | Justification | Example handling |
| --- | --- | --- |
| `current` | Needed for patient-level current fields and aligns with clinical assertion status. | "She remains seizure-free" becomes current seizure-frequency event. |
| `historical` | ConText and epilepsy letters require separating past facts from current facts. | "Previously weekly seizures" does not override current seizure-free. |
| `planned` | Management plans are common in clinic letters. | "We will increase lamotrigine" is planned, not current dose. |
| `requested` | Investigation orders are not results. | "MRI requested" supports request only. |
| `completed` | Investigation result requires completed study. | "EEG was normal" supports completed plus normal result. |
| `family_history` | ConText experiencer distinction prevents family facts becoming patient facts. | "Mother has epilepsy" is not patient diagnosis. |
| `hypothetical` | Clinical text often contains rule-out or conditional statements. | "If further seizures occur..." does not state an event occurred. |
| `uncertain` | Epilepsy diagnosis and frequency can be hedged or unresolved. | "Possible focal epilepsy" is uncertain diagnosis/type. |

### Evidence-Support Scoring Criteria

| Criterion | Automatic? | Pass condition |
| --- | --- | --- |
| Quote present | Yes | Non-empty evidence quote for each present event/final field. |
| Quote valid | Yes | Exact quote appears in the source letter after agreed whitespace normalization. |
| Value supported | Manual or rule-assisted | Quote entails the extracted value without relying on unsupported inference. |
| Temporality supported | Manual or rule-assisted | Quote supports current/historical/planned/requested/family/hypothetical/uncertain status. |
| Field correct | Yes, against gold | Normalized value matches gold label under exact or relaxed matching as specified. |
| Unsupported extraction | Derived | Present output has no valid quote or the quote does not support value plus temporality. |

### Normalization Examples

#### Seizure Frequency

| Letter phrase | Event value | Temporal scope | Final-field behavior |
| --- | --- | --- | --- |
| "seizure-free since the last clinic" | `seizure_free` | `since_last_visit` | Current frequency is seizure-free if no newer contradictory evidence. |
| "weekly focal seizures" | `weekly` | `not_stated` or stated period | Current if no historical cue; link to focal seizure type. |
| "two seizures in the last year" | `2_per_year` | `last_year` | Current/recent frequency. |
| "previously monthly but none since starting levetiracetam" | historical `monthly`; current `seizure_free` | medication-change anchored | Final current is seizure-free; historical event retained. |
| "frequency variable" | `uncertain` | `not_stated` | Final current frequency uncertain, not normalized to a rate. |

#### Medication Status

| Letter phrase | Event status | Final-field behavior |
| --- | --- | --- |
| "continues lamotrigine 100 mg twice daily" | `current` | Current medication with dose. |
| "levetiracetam stopped due to mood changes" | `stopped`, historical | Previous medication with reason stopped. |
| "previously tried carbamazepine" | `previous` | Previous medication. |
| "will increase lamotrigine to 150 mg bd" | `planned_increase` | Planned event; current dose unchanged unless stated elsewhere. |
| "declined sodium valproate" | `declined` | Do not list as current or previous taken medication. |

#### EEG/MRI

| Letter phrase | Status | Result | Scoring note |
| --- | --- | --- | --- |
| "EEG requested" | `requested` | `not_stated` | Correct request, no result. |
| "awaiting MRI" | `pending` | `not_stated` | Not normal/abnormal. |
| "MRI brain was normal" | `completed` | `normal` | Completed normal MRI. |
| "EEG showed left temporal sharp waves" | `completed` | `abnormal` | Completed abnormal EEG. |
| "MRI report unavailable" | `unavailable` or `uncertain` | `not_stated` | Avoid inferring result. |

#### Diagnosis/Type

| Letter phrase | Diagnosis/type output | Note |
| --- | --- | --- |
| "focal epilepsy" | `focal epilepsy`, present | Explicit diagnosis/type. |
| "possible temporal lobe epilepsy" | uncertain diagnosis/type | Keep uncertainty. |
| "non-epileptic attack disorder" | not epilepsy diagnosis; record if schema supports differential | Do not infer epilepsy. |
| "family history of epilepsy" | family-history event | Not patient diagnosis. |

## Suggested Literature Table

| Citation | Domain | Data | Fields | Method | Temporality/assertion | Evidence spans | Metrics | Relevance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fonferko-Shadrach et al. 2019, ExECT | Epilepsy clinic letters | 200 de-identified/pseudonymised Welsh clinic letters | diagnosis, epilepsy type, seizure type, seizure frequency, medication, CT/MRI/EEG, dates | GATE rule/statistical IE pipeline | Certainty used for diagnosis/type; limited temporal focus | Extracted text items, not LLM-style evidence scoring | Overall precision 91.4%, recall 81.4%, F1 86.1%; weaker seizure frequency and investigation performance | Establishes field set and difficulty profile. |
| Fonferko-Shadrach et al. 2024, synthetic annotations/ExECTv2 | Epilepsy clinic letters | 200 synthetic UK outpatient letters, double annotated with consensus gold | diagnosis, seizure type, investigations, current ASM, seizure frequency, onset, history | Annotation guidelines plus ExECTv2 validation | Certainty for diagnosis/history; time/onset attributes | Gold annotation spans available | Human IAA F1 0.73; ExECTv2 F1 0.87 per item, 0.90 per letter; seizure frequency lowest | Primary dataset precedent and gold-standard rationale. |
| Yew et al. 2023 | Epilepsy NLP review | 26 original NLP studies in epilepsy | classification, information retrieval, patient identification, outcomes | Systematic review | Discusses NLP deriving context from free narrative | Not an evidence-span study | 58% used NLP to classify records | Supports narrow dissertation positioning within epilepsy NLP. |
| Xie et al. 2022 | Epilepsy clinic notes | Nearly 79,000 progress notes filtered to epilepsy-specialist notes | recent seizures, seizure frequency, most recent seizure | Machine reading / extractive QA using fine-tuned models | Recency and timing are central questions | Extractive answer spans | Reported near-human performance on several tasks | Supports event/QA framing for seizure frequency. |
| Abeysinghe et al. 2025 | Epilepsy monitoring-unit reports | 2,242 free-text seizure-frequency segments from 6 institutions; 800 annotated instances | seizure frequency phrase, event, quantity, duration/unit | Fine-tuned BERT-based and generative models; structured combination | Handles missing/vague/remission text | Phrase spans and attributes | GPT-4 final structured output F1 85.82% | Supports decomposing frequency into phrase plus attributes. |
| Chapman et al. 2001, NegEx | Clinical reports | Discharge summaries and radiology-style clinical text | negated clinical findings | Trigger/scope rules | Negation | Not evidence scoring | Precision/recall reported for negation detection | Justifies explicit negation/assertion handling. |
| Harkema et al. 2009, ConText | Clinical reports | Multiple clinical report types | clinical conditions plus modifiers | Lexical trigger and scope algorithm | negation, hypothetical, historical, experiencer | Not evidence scoring | Reasonable/good performance; historical vs recent sometimes needs deeper knowledge | Justifies temporality and family-history labels. |
| Eyre et al. 2021/2022, medspaCy | Clinical NLP tooling | Toolkit paper, clinical examples | entities, sections, context, modifiers | Python toolkit implementing ConText-style components | negation, temporality, certainty, experiencer | Span-based NLP pipeline support | Tooling and qualitative use cases | Practical precedent for event/span/context pipeline components. |
| Agrawal et al. 2022 | Clinical IE | Reannotated clinical datasets for few-shot IE | spans, sequence labels, relations | GPT-3/InstructGPT zero-/few-shot prompting | Task-dependent | Span identification included | LLMs outperform zero-/few-shot baselines | Supports training-free clinical IE feasibility. |
| Weng et al. 2026, JAMIA | Clinical IE | 1,588 notes from UTP, MTSamples, MIMIC-III, i2b2 | problems, tests, medications, treatments, 16 modifiers | Instruction-tuned LLaMA-2/3 vs BERT | modifiers include negation and certainty | NER/RE annotations | LLaMA gains under limited/unseen data, but up to 28x slower | Supports bounded model-family comparison with cost reporting. |
| Neveditsin et al. 2025 | Clinical structured output | EHRCon, 105 clinical documents | open attribute-value extraction | Small language models emitting JSON/YAML/XML | Not primary focus | Not semantic evidence scoring | JSON significantly more parseable; semantic correctness not evaluated | Supports JSON canonical format and parseability metrics. |
| Schmidt and Cimiano 2024/2025 | Structured IE | Clinical trial abstracts | structured trial information | Grammar-constrained decoding for generative models | Not clinical assertion focus | Not evidence scoring | Constrained decoding benefits some encoder-decoder models | Supports constrained/validated structured output as engineering layer. |
| Dagdelen et al. 2024 | Scientific structured extraction | Materials-science papers | entities and relations in JSON-like schemas | Fine-tuned GPT/Llama structured extraction | Not clinical | Extraction from source text | Manual semantic scoring can differ from exact match | Supports separating exact match from semantic equivalence. |

## Minimum Literature Review Output

Implementation may begin once the following decisions are reflected in schema, prompts, and scoring code:

- Primary field definitions should follow ExECTv2-native target categories: current medication name/dose/unit/frequency, current seizure frequency, seizure type, EEG/MRI result where stated, and diagnosis/type.
- Event objects should be required for medication, seizure frequency, seizure type, investigation, and diagnosis claims in the event-first pipeline.
- Temporality labels should include `current`, `historical`, `planned`, `requested`, `completed`, `family_history`, `hypothetical`, and `uncertain`.
- Missingness labels should stay separate from temporality: `not_stated`, `uncertain`, `conflicting`, and `not_applicable` answer different scoring questions.
- Evidence support should be scored at quote-presence, quote-validity, semantic-support, temporal-support, and field-correctness levels.
- Exact quote matching is necessary but not sufficient for evidence support.
- Seizure frequency normalization should retain temporal scope and seizure type linkage where stated.
- Medication status labels beyond current ASM should be extension outputs unless manually adjudicated.
- Investigation status labels beyond annotated completed results should be extension outputs unless manually adjudicated.
- JSON should be the canonical scoring format. YAML-to-JSON can be a secondary model-facing comparison, with parseability, repair, and schema-validity metrics reported separately from clinical accuracy.
- Model comparisons should be small and controlled, emphasizing whether event-first extraction changes reliability rather than ranking every available model.

## References

- Abeysinghe, R., Tao, S., Lhatoo, S. D., Zhang, G.-Q., Cui, L., et al. (2025). [Leveraging pretrained language models for seizure frequency extraction from epilepsy evaluation reports](https://www.nature.com/articles/s41746-025-01592-4). `npj Digital Medicine`, 8, 208.
- Agrawal, M., Hegselmann, S., Lang, H., Kim, Y., & Sontag, D. (2022). [Large Language Models are Few-Shot Clinical Information Extractors](https://arxiv.org/abs/2205.12689). EMNLP.
- Chapman, W. W., Bridewell, W., Hanbury, P., Cooper, G. F., & Buchanan, B. G. (2001). [Evaluation of negation phrases in narrative clinical reports](https://pubmed.ncbi.nlm.nih.gov/11825163/). `AMIA Annual Symposium Proceedings`.
- Eyre, H., Chapman, A. B., Peterson, K. S., Shi, J., Alba, P. R., Jones, M. M., Box, T. L., DuVall, S. L., & Patterson, O. V. (2021/2022). [Launching into clinical space with medspaCy: a new clinical text processing toolkit in Python](https://pmc.ncbi.nlm.nih.gov/articles/PMC8861690/). `AMIA Annual Symposium Proceedings`.
- Fonferko-Shadrach, B., Lacey, A. S., Roberts, A., Akbari, A., Thompson, S., Ford, D. V., et al. (2019). [Using natural language processing to extract structured epilepsy data from unstructured clinic letters: development and validation of the ExECT system](https://bmjopen.bmj.com/content/9/4/e023232). `BMJ Open`, 9(4), e023232.
- Fonferko-Shadrach, B., Strafford, H., Jones, C., Khan, R. A., Brown, S., Edwards, J., et al. (2024). [Annotation of epilepsy clinic letters for natural language processing](https://link.springer.com/article/10.1186/s13326-024-00316-z). `Journal of Biomedical Semantics`, 15, 17.
- Dagdelen, J., Dunn, A., Lee, S., Walker, N., Rosen, A. S., Ceder, G., Persson, K. A., et al. (2024). [Structured information extraction from scientific text with large language models](https://www.nature.com/articles/s41467-024-45563-x). `Nature Communications`, 15, 1418.
- Harkema, H., Dowling, J. N., Thornblade, T., & Chapman, W. W. (2009). [ConText: An algorithm for determining negation, experiencer, and temporal status from clinical reports](https://doi.org/10.1016/j.jbi.2009.05.002). `Journal of Biomedical Informatics`, 42(5), 839-851.
- Neveditsin, N., Lingras, P., & Mago, V. (2025). [Evaluating Structured Output Robustness of Small Language Models for Open Attribute-Value Extraction from Clinical Notes](https://aclanthology.org/2025.acl-srw.19.pdf). ACL Student Research Workshop.
- Schmidt, D. M., & Cimiano, P. (2024/2025). [Grammar-constrained decoding for structured information extraction with fine-tuned generative models applied to clinical trial abstracts](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2024.1406857/full). `Frontiers in Artificial Intelligence`, 7.
- Weng, R.-L., Shyr, C., Chen, Q., Jiang, X., Roberts, K. E., & Xu, H. (2026). [Information extraction from clinical notes: are we ready to switch to large language models?](https://academic.oup.com/jamia/article/33/3/553/8425815). `Journal of the American Medical Informatics Association`, 33(3), 553-562.
- Xie, K., Gallagher, R. S., Shinohara, R. T., Xie, S. X., Hill, C. E., Conrad, E. C., et al. (2022). [Extracting seizure frequency from epilepsy clinic notes: a machine reading approach to natural language processing](https://academic.oup.com/jamia/article/29/5/873/6534112). `Journal of the American Medical Informatics Association`, 29(5), 873-881.
- Yew, A. N. J., Schraagen, M., Otte, W. M., & van Diessen, E. (2023). [Transforming epilepsy research: A systematic review on natural language processing applications](https://doi.org/10.1111/epi.17474). `Epilepsia`, 64(2), 292-305.
