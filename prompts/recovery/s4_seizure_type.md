# S4 Seizure Type Extraction

Extract patient seizure types from the epilepsy clinic letter.

Return only one JSON object. Do not wrap the response in Markdown.

Output shape:

```json
{
  "task": "seizure_type",
  "candidates": [
    {
      "value": "focal impaired awareness seizures",
      "temporality": "current",
      "evidence": {
        "quote": "focal impaired awareness seizures",
        "sentence_id": null,
        "char_start": null,
        "char_end": null
      },
      "confidence": 0.0
    }
  ]
}
```

Rules:

- Extract seizure types only when the letter states them.
- Do not infer seizure type from medication, investigation result, age, or
  diagnosis unless the type itself is explicitly stated.
- Prefer specific stated terms such as focal impaired awareness seizure,
  generalized tonic-clonic seizure, absence seizure, myoclonic seizure, or
  focal to bilateral tonic-clonic seizure.
- If seizures are mentioned but the type is not stated, use
  `unknown seizure type` with evidence.
- Preserve temporality as `current`, `historical`, or `uncertain` from the
  wording.
- Use exact contiguous evidence quotes copied from the source letter.
