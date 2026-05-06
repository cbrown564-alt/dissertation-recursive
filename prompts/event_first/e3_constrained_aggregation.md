# E3 Constrained Event Aggregation

You are aggregating extracted clinical events into canonical patient-level JSON.

Return only one JSON object matching the canonical extraction schema. Do not
wrap the response in Markdown. Use `pipeline_id: "E3_constrained_event_aggregation"`.

Use only the supplied event list as evidence. Do not use outside clinical
knowledge and do not add facts that are not supported by event evidence.

Final fields must cite supporting event IDs in `evidence_event_ids`. Every
present final field must include exact evidence copied from the supporting
event evidence.

Aggregation rules:

- Select current medications only from current medication events.
- Preserve medication name, dose, dose unit, and frequency where stated.
- Put previous, stopped, declined, planned, increased, and reduced medication
  events in metadata extension logs rather than current medication fields.
- Select current seizure frequency from current or most recent
  seizure-frequency events, preserving temporal scope and seizure-type linkage.
- Do not let historical seizure frequencies override a current seizure-free
  statement.
- Score EEG and MRI from completed investigation result events only.
- Do not treat requested, pending, or unavailable EEG/MRI as completed results.
- Preserve seizure type and diagnosis values conservatively.
- Use `not_stated` when no supporting event exists and `uncertain` when events
  conflict or are insufficient.
