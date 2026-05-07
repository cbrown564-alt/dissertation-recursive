# Benchmark Crosswalk

Phase 0 of the performance-recovery roadmap reconciles the Fang et al.
benchmark with this project's ExECTv2 schema and scorer. The purpose is not to
make the tasks identical. It is to mark which local fields can fairly be held
against the external benchmark floor, and which local metrics are stricter
extensions.

## Sources Reviewed

- Fang S, Holgate B, Shek A, Winston JS, McWilliam M, Viana PF, Teo JT,
  Richardson MP. "Extracting epilepsy-related information from unstructured
  clinic letters using large language models." Epilepsia. 2025;66:3369-3384.
  DOI: 10.1111/epi.18475. PubMed/PMC record:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC12455391/
- Author code repository:
  https://github.com/scfang6/extracting_information_using_LLMs
- Local schema: `schemas/canonical_extraction.schema.json`
- Local scorer: `src/evaluate.py`
- Local gold tables:
  `data/ExECT 2 (2025)/MarkupOutput_200_SyntheticEpilepsyLetters/`

## Benchmark Task Shape

The benchmark evaluates four extraction tasks from King's College Hospital
epilepsy clinic letters:

| Benchmark task | Benchmark label shape | Local comparability |
| --- | --- | --- |
| Epilepsy type | Multi-label binary categories: generalized, focal, combined generalized/focal, unknown | Partially comparable through local diagnosis/type normalization |
| Seizure type | Multi-label binary categories: generalized, focal, unknown | Partially comparable through collapsed local seizure-type labels |
| Current ASMs | Multi-label medication-name detection over a fixed ASM dictionary | Directly comparable for medication names; local full-tuple scoring is stricter |
| Associated symptoms | Multi-label symptom checklist: anxiety, depression, dizziness, headache, lethargy, nausea, rash | Not currently a primary local field |

The benchmark code confirms that the task prompts ask for task-specific,
compact outputs. Epilepsy type and seizure type are scored as binary columns
parsed from JSON-like True/False answers. Current ASMs are scored by scanning
model output for medication names and brand-name variants. Associated symptoms
are the seven symptoms listed above. The paper reports repeated extraction
runs and micro-aggregated precision/recall/F1 over label instances, not a
single document-level exact-match score.

## Local Schema Mapping

| Benchmark concept | Local field or metric | Mapping status | Notes |
| --- | --- | --- | --- |
| Epilepsy type: generalized | `fields.epilepsy_diagnosis.value` plus diagnosis gold rows with `DiagnosisType=Epilepsy` | Comparable after normalization | Local gold includes fine-grained strings such as `generalised-epilepsy` and syndrome labels. Collapse to `generalized` only for benchmark-aligned reporting. |
| Epilepsy type: focal | `fields.epilepsy_diagnosis.value` plus diagnosis gold rows with `DiagnosisType=Epilepsy` | Comparable after normalization | Local labels include `focal-epilepsy`, `focal-onset-epilepsy`, temporal-lobe epilepsy, and structural focal epilepsy variants. |
| Epilepsy type: combined generalized/focal | `fields.epilepsy_diagnosis.value` | Weakly comparable | Local gold may express both focal and generalized seizure terms without a single combined epilepsy-type assertion. Treat as comparable only when explicitly stated or when the local annotation has an epilepsy diagnosis label that maps to combined. |
| Epilepsy type: unknown | `epilepsy_diagnosis.missingness` and generic diagnosis labels | Limited comparability | Benchmark "unknown" is positive when epilepsy is stated but type is not. Local scorer currently treats diagnosis text accuracy as match against gold strings, so this needs a derived label. |
| Seizure type: generalized | `fields.seizure_types[].value`; local gold from seizure-frequency type and diagnosis rows with seizure labels | Comparable after normalization | Collapse terms such as generalized tonic-clonic, absences, and myoclonic seizures to `generalized` for benchmark-style reporting. |
| Seizure type: focal | `fields.seizure_types[].value`; local gold from seizure-frequency type and diagnosis rows with seizure labels | Comparable after normalization | Collapse focal seizures, focal impaired awareness, complex partial, focal motor, and focal-to-bilateral convulsive variants to `focal`. |
| Seizure type: unknown | `fields.seizure_types` plus generic seizure labels | Limited comparability | Benchmark marks unknown when seizures are mentioned but type is not specified. Local gold often contains generic `seizure(s)` labels in frequency rows; a derived unknown label is needed. |
| Current ASM name | `fields.current_anti_seizure_medications[].name`; `medication_name` metric | Directly comparable | This is the cleanest external comparison. The benchmark uses a fixed ASM dictionary with brand-name normalization. Local scoring should adopt the same style before claiming comparability. |
| Current ASM dose | `fields.current_anti_seizure_medications[].dose` | Stricter local extension | Fang et al. do not score dose as a primary reported benchmark task. |
| Current ASM unit | `fields.current_anti_seizure_medications[].dose_unit` | Stricter local extension | Keep as local recovery metric, not benchmark target. |
| Current ASM frequency | `fields.current_anti_seizure_medications[].frequency` | Stricter local extension | Keep as local recovery metric, not benchmark target. |
| Current ASM full tuple | `medication_full` metric | Stricter local extension | Requires name, dose, unit, and dosing frequency. It should not be compared directly to the benchmark's ASM-name F1. |
| Associated symptoms | No current canonical field | Not comparable | Optional extension only. Adding this field would require schema and gold support or a separate challenge set. |

## Metric Crosswalk

| Roadmap target | Local metric now | Needed Phase 1-3 work |
| --- | --- | --- |
| Epilepsy type F1 >= .80 | `epilepsy_diagnosis_accuracy` | Add benchmark-collapsed per-label PRF for generalized/focal/combined/unknown. Current accuracy is partial string matching and is not the same aggregation style. |
| Seizure type F1 >= .76 | `seizure_type_f1` | Add collapsed benchmark labels and per-label support. Current metric uses exact normalized strings from local labels. |
| Current ASM F1 >= .90 | `medication_name_f1` | Add ASM dictionary/brand normalization before scoring. This metric is benchmark-aligned once normalized. |
| Full medication tuple F1 >= .80 | `medication_full_f1` | Local-only stricter target. Split error reporting into name, dose, unit, frequency, and full tuple. |
| Associated symptoms F1 >= .63 | None | Explicitly out of primary recovery scope unless schema/gold are extended. |
| Schema validity >= .99 | `schema_valid_rate` | Already directly measured. |
| Quote validity >= .99 | `quote_validity_rate` | Already directly measured. |
| Temporal accuracy >= .95 | `temporal_accuracy` | Local-only reliability gate. Not directly benchmarked by Fang et al. |
| Current seizure-frequency extraction | `current_seizure_frequency_accuracy` | Not benchmarked by Fang et al.; must be audited against ExECTv2/Gan frequency definitions. |
| Seizure-frequency type linkage | `seizure_frequency_type_linkage_accuracy` | Not benchmarked by Fang et al.; local-only event-first claim. |

## Prompt And Label Implications

The benchmark is a strong reason to add short, task-specific direct prompts in
Phase 4. The released code uses separate prompts for epilepsy type, seizure
type, ASM names, and symptoms rather than one broad canonical schema prompt.
For recovery, S4 should produce benchmark-aligned candidate fields first, then
merge into canonical JSON with evidence.

The benchmark label set is coarser than ExECTv2. Local fine-grained labels
should therefore be retained for dissertation-specific claims, but benchmark
claims must be reported through a derived collapsed view:

- `generalized`
- `focal`
- `combined_generalized_focal`
- `unknown`

For ASMs, name-only comparison should be dictionary-normalized before any
benchmark statement. Dose, unit, frequency, and full tuple are valuable but
strictly harder than the benchmark task.

## Phase 0 Decision

The directly benchmarkable local field is current ASM name detection. Epilepsy
type and seizure type are benchmarkable only through a derived collapsed label
view. Medication full tuple, seizure frequency, temporal support, evidence
support, EEG/MRI result, and event aggregation are local extensions. Associated
symptoms are not comparable in the current schema.

Phase 1 should therefore prioritize:

- failure localization for `medication_name`, `medication_full`,
  `seizure_type`, `current_seizure_frequency`,
  `seizure_frequency_type_linkage`, and `epilepsy_diagnosis`;
- a derived benchmark-label view for epilepsy type and seizure type;
- an ASM brand/synonym normalizer before interpreting medication-name F1
  against the external benchmark.
