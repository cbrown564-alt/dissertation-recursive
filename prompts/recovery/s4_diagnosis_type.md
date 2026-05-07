# S4 Epilepsy Diagnosis And Type Extraction

Extract the patient-level epilepsy diagnosis or epilepsy type from the clinic
letter.

Return only one JSON object. Do not wrap the response in Markdown.

Output shape:

```json
{
  "task": "diagnosis_type",
  "candidate": {
    "value": "focal epilepsy",
    "temporality": "current",
    "evidence": {
      "quote": "Diagnosis: focal epilepsy",
      "sentence_id": null,
      "char_start": null,
      "char_end": null
    },
    "confidence": 0.0
  }
}
```

Rules:

- Extract only a stated diagnosis or epilepsy type.
- Do not infer epilepsy type from seizure type, medication, EEG, MRI, age, or
  family history.
- Keep explicit terms such as focal epilepsy, generalized epilepsy, combined
  generalized and focal epilepsy, temporal lobe epilepsy, or epilepsy of
  unknown type.
- Ignore differential, ruled-out, family-history, and hypothetical diagnoses.
- If epilepsy is stated but type is not stated, use `epilepsy`.
- If no patient-level epilepsy diagnosis is stated, use `"candidate": null`.
- Use exact contiguous evidence quotes copied from the source letter.
