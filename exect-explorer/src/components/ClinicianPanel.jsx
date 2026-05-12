import React, { useMemo } from "react";
import { Pill, Activity, Brain, Stethoscope } from "lucide-react";

const TYPE_COLOURS = {
  Diagnosis: "#c45c3e",
  Prescription: "#2d8a5e",
  SeizureFrequency: "#b85cb8",
  PatientHistory: "#5c7db8",
  Investigations: "#b88a5c",
};

export default function ClinicianPanel({ data, onSelectEntity }) {
  const medications = useMemo(() => {
    if (!data) return [];
    return data.entities
      .filter((e) => e.type === "Prescription")
      .map((e) => ({
        id: e.id,
        name: e.attributes.DrugName || e.text.replace(/-/g, " "),
        dose: e.attributes.DrugDose,
        unit: e.attributes.DoseUnit,
        frequency: e.attributes.Frequency,
        cui: e.attributes.CUI,
        raw: e.text,
      }));
  }, [data]);

  const diagnoses = useMemo(() => {
    if (!data) return [];
    return data.entities
      .filter((e) => e.type === "Diagnosis")
      .map((e) => ({
        id: e.id,
        category: e.attributes.DiagCategory,
        phrase: e.attributes.CUIPhrase || e.text.replace(/-/g, " "),
        certainty: e.attributes.Certainty,
        negated: e.attributes.Negation?.toLowerCase() === "negated",
        raw: e.text,
      }));
  }, [data]);

  const frequencies = useMemo(() => {
    if (!data) return [];
    return data.entities
      .filter((e) => e.type === "SeizureFrequency")
      .map((e) => ({
        id: e.id,
        lower: e.attributes.LowerNumberOfSeizures,
        upper: e.attributes.UpperNumberOfSeizures,
        number: e.attributes.NumberOfSeizures,
        period: e.attributes.TimePeriod,
        numPeriods: e.attributes.NumberOfTimePeriods,
        year: e.attributes.YearDate,
        raw: e.text,
      }));
  }, [data]);

  const investigations = useMemo(() => {
    if (!data) return [];
    return data.entities
      .filter((e) => e.type === "Investigations")
      .map((e) => ({
        id: e.id,
        performed: e.attributes.CT_Performed || e.attributes.MRI_Performed || e.attributes.EEG_Performed,
        results: e.attributes.CT_Results || e.attributes.MRI_Results || e.attributes.EEG_Results,
        raw: e.text,
      }));
  }, [data]);

  if (!data) return null;

  return (
    <div className="side-panel clinician-panel">
      <div className="panel-header">
        <Stethoscope size={15} />
        <span>Clinical View</span>
      </div>

      <div className="panel-section">
        <div className="section-title">
          <Pill size={13} />
          Medications
        </div>
        {medications.length === 0 ? (
          <p className="panel-empty">No medications annotated.</p>
        ) : (
          <div className="med-list">
            {medications.map((med) => (
              <div key={med.id} className="med-card">
                <div className="med-name" onClick={() => onSelectEntity?.(med.id)} style={{cursor:'pointer'}}>{med.name}</div>
                <div className="med-tuple">
                  {med.dose && <span className="tuple-pill dose">{med.dose}</span>}
                  {med.unit && <span className="tuple-pill unit">{med.unit}</span>}
                  {med.frequency && (
                    <span className="tuple-pill freq">
                      {med.frequency === "1"
                        ? "once daily"
                        : med.frequency === "2"
                        ? "twice daily"
                        : med.frequency === "3"
                        ? "three times daily"
                        : med.frequency}
                    </span>
                  )}
                </div>
                {!med.dose || !med.unit || !med.frequency ? (
                  <div className="tuple-warning">Incomplete tuple</div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="panel-section">
        <div className="section-title">
          <Brain size={13} />
          Diagnoses
        </div>
        {diagnoses.length === 0 ? (
          <p className="panel-empty">No diagnoses annotated.</p>
        ) : (
          <div className="dx-list">
            {diagnoses.map((dx) => (
              <div key={dx.id} className={`dx-card ${dx.negated ? "is-negated" : ""}`}>
                <div className="dx-phrase" onClick={() => onSelectEntity?.(dx.id)} style={{cursor:'pointer'}}>{dx.phrase.replace(/-/g, " ")}</div>
                <div className="dx-meta">
                  {dx.category && <span className="dx-cat">{dx.category}</span>}
                  {dx.certainty && <span className="dx-cert">Certainty {dx.certainty}/5</span>}
                  {dx.negated && <span className="dx-neg">Negated</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="panel-section">
        <div className="section-title">
          <Activity size={13} />
          Seizure Frequency
        </div>
        {frequencies.length === 0 ? (
          <p className="panel-empty">No frequency annotated.</p>
        ) : (
          <div className="freq-list">
            {frequencies.map((f) => (
              <div key={f.id} className="freq-card">
                <div className="freq-value">
                  {f.number
                    ? `${f.number} seizure(s)`
                    : f.lower && f.upper
                    ? `${f.lower}–${f.upper} seizures`
                    : f.lower
                    ? `${f.lower}+ seizures`
                    : "Frequency present"}
                </div>
                <div className="freq-context">
                  {f.period && <span>per {f.period.toLowerCase()}</span>}
                  {f.numPeriods && f.period && <span> (×{f.numPeriods})</span>}
                  {f.year && <span> · {f.year}</span>}
                </div>
                {frequencies.length > 1 && (
                  <div className="freq-note">
                    Multi-mention — ExECTv2 captures all spans; Gan would normalize to one
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {investigations.length > 0 && (
        <div className="panel-section">
          <div className="section-title">Investigations</div>
          <div className="inv-list">
            {investigations.map((inv) => (
              <div key={inv.id} className="inv-card">
                <span className="inv-text">{inv.raw.replace(/-/g, " ")}</span>
                {inv.results && (
                  <span className={`inv-result ${inv.results.toLowerCase()}`}>{inv.results}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
