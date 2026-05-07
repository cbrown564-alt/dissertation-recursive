import React, { useContext } from "react";
import { AppContext } from "../context.js";
import { pct, shortPert } from "../utils.js";

const PERT_CATALOG = {
  bullets_to_prose: {
    label:    "Bullets → Prose",
    category: "format",
    desc:     "Converts bulleted medication and investigation lists to flowing prose sentences. Tests sensitivity to presentation format rather than clinical content.",
  },
  family_history_trap: {
    label:    "Family History Trap",
    category: "clinical",
    desc:     "Inserts family history of the primary condition alongside the patient's own history. Tests whether the system correctly attributes conditions to the patient vs relatives.",
  },
  historical_medication_trap: {
    label:    "Historical Medication Trap",
    category: "temporal",
    desc:     "Adds references to medications the patient previously took but has since stopped. Tests temporal context — current vs historical prescriptions.",
  },
  negated_investigation_trap: {
    label:    "Negated Investigation",
    category: "negation",
    desc:     "Negates investigation findings (e.g., 'MRI showed no abnormality'). Tests whether negation correctly suppresses field extraction.",
  },
  planned_medication_trap: {
    label:    "Planned Medication Trap",
    category: "temporal",
    desc:     "Introduces medications described as planned or recommended but not yet started. Tests current-state extraction against future-intent language.",
  },
  removed_headings: {
    label:    "Removed Headings",
    category: "structure",
    desc:     "Strips all section headings from the document. Tests whether extraction relies on structural cues or pure content semantics.",
  },
  reordered_sections: {
    label:    "Reordered Sections",
    category: "structure",
    desc:     "Reorders document sections (e.g., moves History of Presenting Complaint after Plan). Tests positional robustness of extraction.",
  },
};

const CATEGORY_COLORS = {
  format:   "#1d4ed8",
  clinical: "#047857",
  temporal: "#b45309",
  negation: "#7c3aed",
  structure: "#0f766e",
};

function DeltaCell({ value }) {
  if (value === null || value === undefined || isNaN(Number(value))) {
    return <td className="delta-zero">n/a</td>;
  }
  const v = Number(value);
  const cls = v > 0.005 ? "delta-pos" : v < -0.005 ? "delta-neg" : "delta-zero";
  return <td className={cls}>{pct(v, { signed: true })}</td>;
}

export default function Robustness() {
  const { data, systems } = useContext(AppContext);
  const rows = data.robustness || [];
  const hasData = rows.some((r) =>
    systems.some((s) => r.values?.[s.id] !== null && r.values?.[s.id] !== undefined)
  );

  const allPerts = Object.keys(PERT_CATALOG);
  const catalogRows = allPerts.map((id) => {
    const dataRow = rows.find((r) => r.perturbation === id);
    return { id, dataRow, ...PERT_CATALOG[id] };
  });

  return (
    <>
      <h1 className="view-title">Robustness</h1>
      <p className="view-sub">
        Field accuracy degradation under label-preserving perturbations
      </p>

      {!hasData && (
        <div
          style={{
            padding: "24px 0",
            fontFamily: "var(--mono)",
            fontSize: 12,
            color: "var(--muted)",
            lineHeight: 1.8,
          }}
        >
          <p>no matched clean baselines available</p>
          <p style={{ color: "var(--dim)", marginTop: 6 }}>
            run final matched evaluation to populate degradation deltas — smoke artifacts do not
            contain clean/perturbed baseline pairs
          </p>
          <p style={{ marginTop: 10, color: "var(--dim)" }}>
            missing artifact:{" "}
            <code
              style={{
                background: "var(--raised)",
                padding: "2px 7px",
                borderRadius: 4,
                color: "var(--muted)",
              }}
            >
              robustness/label_preserving_degradation.csv
            </code>
          </p>
        </div>
      )}

      <div className="pert-catalog">
        {catalogRows.map(({ id, label, category, desc, dataRow }) => {
          const catColor = CATEGORY_COLORS[category] || "var(--muted)";
          return (
            <div key={id} className="pert-row">
              <div>
                <div className="pert-meta" style={{ marginBottom: 6 }}>
                  <span className="pert-tag" style={{ background: catColor + "18", color: catColor }}>
                    {category}
                  </span>
                  <span className="pert-name">{label}</span>
                </div>
                <p className="pert-desc">{desc}</p>
              </div>
              <div className="pert-deltas">
                {systems.map((s) => {
                  const v = dataRow?.values?.[s.id];
                  const missing = v === null || v === undefined || isNaN(Number(v));
                  const n = Number(v);
                  const cls = missing ? "delta-zero" : n < -0.005 ? "delta-neg" : n > 0.005 ? "delta-pos" : "delta-zero";
                  return (
                    <div key={s.id} className="pert-delta-row">
                      <span className="pert-delta-sys" style={{ color: s.color, fontSize: 10, fontFamily: "var(--mono)" }}>
                        {s.id}
                      </span>
                      <span className={`pert-delta-val ${cls}`} style={{ fontFamily: "var(--mono)", fontSize: 11 }}>
                        {missing ? "—" : pct(n, { signed: true })}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {rows.length > 0 && (
        <div className="panel" style={{ marginTop: 20 }}>
          <div className="panel-head">
            <span className="panel-title">Degradation by Perturbation Type</span>
            <span className="panel-note">delta vs clean baseline</span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table className="robust-table">
              <thead>
                <tr>
                  <th>Perturbation</th>
                  {systems.map((s) => (
                    <th key={s.id} style={{ color: s.color }}>
                      {s.id}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.perturbation}>
                    <td>{shortPert(row.perturbation)}</td>
                    {systems.map((s) => (
                      <DeltaCell key={s.id} value={row.values?.[s.id]} />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
