# Long-CoT Benchmark Extraction (H6fs variant)

Extract only benchmark fields from this epilepsy clinic letter.

Return JSON only with this shape:
```json
{"medication_names":[],"seizure_types":[],"epilepsy_diagnosis_type":null}
```

## Step-by-step reasoning instructions

Before producing the final JSON, think step by step in the following order:

1. **List all current anti-seizure medications** you find in the letter, with their exact names, doses, units, and frequencies if stated. Exclude any medications that are historical, stopped, planned, declined, or from family history.

2. **Determine the patient's current seizure status**. Is the patient currently seizure-free? Do they have ongoing seizures? If ongoing, is the specific type named? Are there any mentions of seizure types in family history or past history that should be ignored?

3. **Identify the epilepsy diagnosis or type** explicitly stated for the patient. Do not infer a diagnosis from seizure type, medication, age, or family history.

4. **Verify each item against the source text**. Check that every medication name, seizure type, and diagnosis has direct supporting evidence in the letter. Drop any item that lacks direct evidence.

5. **Produce the final JSON** using only the verified items above.

## Field rules

- Medication names should include current anti-seizure medications only. Use generic drug names where possible.
- Seizure types must use only the allowed labels. Do not include aura, warning, symptom, medication side effect, investigation finding, or differential diagnosis labels as seizure types.
- Epilepsy diagnosis/type must use one allowed label or null. Do not invent a diagnosis if the letter does not support one.

Allowed seizure_type labels:
- focal seizure
- secondary generalized seizures
- generalized tonic clonic seizure
- generalized absence seizure
- generalized myoclonic seizure
- generalized seizures
- convulsive seizure
- cluster of seizures
- seizure free
- unknown seizure type

Allowed epilepsy_diagnosis_type labels:
- epilepsy
- focal epilepsy
- generalized epilepsy
- juvenile myoclonic epilepsy
- status epilepticus

## Examples

Example 1 -- patient has ongoing seizures but type is not specified in the letter:
Letter excerpt: "She continues to have approximately two episodes per month. We plan to review her medication at the next visit."
Output: {"medication_names":["lamotrigine"],"seizure_types":["unknown seizure type"],"epilepsy_diagnosis_type":"epilepsy"}

Example 2 -- patient is currently seizure-free:
Letter excerpt: "He has been completely seizure-free for the past ten months since starting levetiracetam."
Output: {"medication_names":["levetiracetam"],"seizure_types":["seizure free"],"epilepsy_diagnosis_type":"juvenile myoclonic epilepsy"}

Example 3 -- letter mentions past seizure type but patient is now seizure-free:
Letter excerpt: "Previously had tonic clonic seizures, but has had no further events since sodium valproate was introduced two years ago."
Output: {"medication_names":["sodium valproate"],"seizure_types":["seizure free"],"epilepsy_diagnosis_type":"generalized epilepsy"}
