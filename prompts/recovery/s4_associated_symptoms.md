# S4 Associated Symptoms Extraction

Extract benchmark-style associated symptoms from the epilepsy clinic letter.

Return only one JSON object. Do not wrap the response in Markdown.

Output shape:

```json
{
  "task": "associated_symptoms",
  "candidates": [
    {
      "value": "headache",
      "evidence": {
        "quote": "She reports headaches after seizures",
        "sentence_id": null,
        "char_start": null,
        "char_end": null
      },
      "confidence": 0.0
    }
  ]
}
```

Allowed symptom values:

- anxiety
- depression
- dizziness
- headache
- lethargy
- nausea
- rash

Rules:

- Extract symptoms only when stated for the patient.
- Do not infer symptoms from medication side-effect lists, counselling, or
  family history.
- Use exact contiguous evidence quotes copied from the source letter.
- If none of the allowed symptoms are stated, return an empty `candidates`
  array.
