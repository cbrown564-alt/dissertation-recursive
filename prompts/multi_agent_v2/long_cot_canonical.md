# Long-CoT Canonical Extraction

Extract structured clinical information from this epilepsy clinic letter and return it as canonical JSON.

## Step-by-step reasoning instructions

Before producing the final JSON, think step by step in the following order:

1. **Identify all current anti-seizure medications** with name, dose, unit, frequency, and status. List them with their supporting evidence quotes.

2. **Identify any previous anti-seizure medications** that were stopped or historical, with reasons if stated.

3. **Determine current seizure status**: Is the patient seizure-free? Do they have ongoing seizures? What type(s)? What is the current frequency? Distinguish current from historical and family-history mentions.

4. **Identify investigation results** (EEG, MRI) with their status and result (normal/abnormal).

5. **Identify the epilepsy diagnosis/type** explicitly stated. Do not infer from seizure type or medication.

6. **Verify temporality** for every item: ensure current items are truly current, not historical or planned.

7. **Produce the final canonical JSON** using only the verified items above.

## Output schema

Return JSON matching the canonical extraction schema with these top-level keys:
- `document_id`
- `pipeline_id`
- `fields`
  - `current_anti_seizure_medications`: array of medication objects
  - `previous_anti_seizure_medications`: array of medication objects
  - `current_seizure_frequency`: scalar with temporal_scope and seizure_type
  - `seizure_types`: array of scalar objects
  - `eeg`: investigation object
  - `mri`: investigation object
  - `epilepsy_diagnosis`: scalar object
- `events`: array (may be empty)
- `metadata`

## Rules

- Every present field must include evidence with an exact verbatim quote from the letter.
- Use generic drug names where possible.
- Seizure types must use canonical labels: focal seizure, generalized tonic clonic seizure, generalized absence seizure, generalized myoclonic seizure, generalized seizures, secondary generalized seizures, convulsive seizure, cluster of seizures, seizure free, unknown seizure type.
- Do not include aura, warning, symptom, medication side effect, or investigation finding labels as seizure types.
- Do not invent a diagnosis if the letter does not explicitly support one.
