import React, { useState } from "react";
import { X, BookOpen, AlertTriangle, CheckCircle2 } from "lucide-react";

const SECTIONS = [
  {
    id: "general",
    title: "General Rules",
    icon: BookOpen,
    content: [
      "Select terms from the UMLS dictionary when possible. If a term doesn't appear, search for a similar term.",
      "Certainty levels (1–5) apply to Diagnosis, Birth History, Epilepsy Cause, Onset, When Diagnosed, and Patient History.",
      "Negation (Polarity) should be assigned to all concepts EXCEPT Seizure Frequency, Investigations, and Prescription.",
      "Dates use DayDate, MonthDate, and YearDate attributes.",
      "Hypothetical statements should NOT be annotated (e.g., 'should her seizures continue...').",
      "Past and present tense are accepted for Diagnosis.",
    ],
  },
  {
    id: "diagnosis",
    title: "Diagnosis",
    icon: CheckCircle2,
    content: [
      "Includes Epilepsy, Epilepsy type/syndrome, and specific seizure types.",
      "NO generic 'seizure / absence / myoclonic jerk' — those belong in Patient History.",
      "Combined phrases: 'partial seizures with secondary generalisation' → annotate separately as partial seizures AND secondary generalisation.",
      "But 'focal to bilaterally convulsive seizure' is ONE concept (same CUI as secondary generalised).",
      "Combined epilepsy: 'refractory focal epilepsy' → annotate refractory epilepsy AND focal epilepsy separately.",
      "Symptomatic focal epilepsy has its own CUI → annotate as ONE.",
      "Even negated history of seizures is Affirmed for Diagnosis if it confirms the patient had that seizure type.",
    ],
  },
  {
    id: "prescription",
    title: "Prescription",
    icon: CheckCircle2,
    content: [
      "Only CURRENT anti-seizure medications (ASMs).",
      "Required: Drug name, Dose, Dose Unit, Frequency. Drugs without dose should NOT be annotated (except rescue meds like midazolam/diazepam).",
      "If frequency is not stated, default to 'once daily' or 'As Required' for clobazam/rescue drugs.",
      "Match generic names precisely. Do not substitute brand for generic in the annotation.",
    ],
  },
  {
    id: "frequency",
    title: "Seizure Frequency",
    icon: CheckCircle2,
    content: [
      "Annotate seizures, specific seizures, absences, and myoclonic jerks. NOT 'events', 'episodes', or slang.",
      "Capture number of seizures + time period. Multiple time periods → annotate both.",
      "'Seizure free for 2 months' → NumberOfSeizures = 0, TimePeriod = Month, NumberOfTimePeriods = 2.",
      "'No seizure since' = 0 seizures Since. 'Last seizure in [time]' = 0 seizures Since [time].",
      "'Since starting Lamotrigine his seizure frequency has improved' → FrequencyChange = Decreased, PointInTime = DrugChange.",
      "Do NOT annotate past seizure control without a statement of frequency.",
    ],
  },
  {
    id: "patienthistory",
    title: "Patient History",
    icon: CheckCircle2,
    content: [
      "Other diagnoses, comorbidities, accidents, non-specific seizures, neuroimaging abnormalities.",
      "Generic seizures (absences, myoclonic jerks) go here, NOT in Diagnosis.",
      "Febrile seizures: extract BOTH Affirmed and Negated statements. Negated febrile seizures get Certainty = 1, Negation = Negated.",
      "When age is given as a range (e.g., 'from 3 to 5 years'), use AgeLower and AgeUpper.",
    ],
  },
  {
    id: "investigations",
    title: "Investigations",
    icon: CheckCircle2,
    content: [
      "EEG / CT / MRI followed by Normal / Abnormal result.",
      "Investigations without any mention of result should be IGNORED.",
      "For EEG, annotate the type if stated; do NOT assume.",
      "When results are unknown, search for 'EEG unknown', 'MRI unknown', or 'CT unknown' in UMLS.",
    ],
  },
  {
    id: "certainty",
    title: "Certainty Levels",
    icon: AlertTriangle,
    content: [
      "5 = Definite / Certain (e.g., 'has been diagnosed with').",
      "4 = Probable / Likely (e.g., 'probably in 2010').",
      "3 = Possible / Uncertain (e.g., 'possible complex partial seizures').",
      "2 = Unlikely / Doubtful.",
      "1 = Ruled out / Negated (use with Negation = Negated).",
    ],
  },
];

export default function GuidelinesPanel({ onClose }) {
  const [open, setOpen] = useState(new Set(["general"]));

  const toggle = (id) => {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="side-panel guidelines-panel">
      <div className="panel-header">
        <BookOpen size={15} />
        <span>Annotation Guidelines</span>
        <button className="panel-close" onClick={onClose}>
          <X size={14} />
        </button>
      </div>
      <div className="guidelines-body">
        {SECTIONS.map((section) => {
          const isOpen = open.has(section.id);
          const Icon = section.icon;
          return (
            <div key={section.id} className={`guideline-section ${isOpen ? "is-open" : ""}`}>
              <button className="guideline-header" onClick={() => toggle(section.id)}>
                <Icon size={13} />
                <span>{section.title}</span>
              </button>
              {isOpen && (
                <ul className="guideline-list">
                  {section.content.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
