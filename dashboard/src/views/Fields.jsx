import React, { useContext } from "react";
import { AppContext } from "../context.js";
import { pct, clamp } from "../utils.js";

function getTier(value) {
  if (value === null || value === undefined || isNaN(Number(value))) return "na";
  const v = Number(value);
  if (v >= 0.9)  return "strong";
  if (v >= 0.7)  return "partial";
  return "failing";
}

const TIER_LABELS = { strong: "strong", partial: "partial", failing: "failing", na: "n/a" };

function FieldCard({ row, systems, activeSystem, onDrillDown }) {
  const tier = getTier(row.values?.[activeSystem]);
  return (
    <div className="field-card" onClick={() => onDrillDown(row.field)}>
      <div className="field-name-row">
        <span className="field-name">{row.field}</span>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span className={`tier-pill tier-${tier}`}>{TIER_LABELS[tier]}</span>
          <span className="field-drill-hint">filter docs →</span>
        </div>
      </div>
      <div className="field-bars">
        {systems.map((s) => {
          const v = clamp(row.values?.[s.id]);
          return (
            <div key={s.id} className="field-bar-row">
              <span className="field-bar-sys" style={{ color: s.color }}>{s.id}</span>
              <div className="field-bar-track">
                <div
                  className="field-bar-fill"
                  style={{ width: `${v * 100}%`, background: s.color, opacity: 0.85 }}
                />
              </div>
              <span className="field-bar-val">{pct(row.values?.[s.id])}</span>
            </div>
          );
        })}
      </div>
      {row.missingness_reason && (
        <p style={{ fontSize: 10, color: "var(--dim)", fontFamily: "var(--mono)", marginTop: 10 }}>
          ⚠ {row.missingness_reason}
        </p>
      )}
    </div>
  );
}

export default function Fields() {
  const { data, systems, dispatch, state } = useContext(AppContext);
  const { activeSystem } = state;
  const rows = data.field_accuracy || [];

  const sorted = [...rows].sort((a, b) => {
    const va = a.values?.[activeSystem] ?? 1;
    const vb = b.values?.[activeSystem] ?? 1;
    return Number(va) - Number(vb);
  });

  const drillDown = (field) => {
    dispatch({ type: "SET_FIELD_FILTER", payload: field });
    window.location.hash = "#documents";
  };

  return (
    <>
      <h1 className="view-title">Field Accuracy</h1>
      <p className="view-sub">
        Per-field extraction accuracy — sorted worst→best for {activeSystem} · click any card to filter Documents
      </p>

      <div className="legend" style={{ marginBottom: 20 }}>
        {systems.map((s) => (
          <div key={s.id} className="legend-item">
            <div className="legend-dot" style={{ background: s.color }} />
            <span className="legend-sys" style={{ color: s.color }}>{s.id}</span>
            <span>{s.label}</span>
          </div>
        ))}
        <span className="filter-sep" />
        {["strong", "partial", "failing"].map((t) => (
          <div key={t} className="legend-item">
            <span className={`tier-pill tier-${t}`}>{t}</span>
            <span style={{ fontSize: 11, color: "var(--muted)" }}>
              {t === "strong" ? "≥90%" : t === "partial" ? "70–90%" : "<70%"}
            </span>
          </div>
        ))}
      </div>

      {rows.length === 0 ? (
        <p style={{ color: "var(--muted)", fontFamily: "var(--mono)", fontSize: 12 }}>
          no field data in current bundle
        </p>
      ) : (
        <div className="fields-grid">
          {sorted.map((row) => (
            <FieldCard
              key={row.field}
              row={row}
              systems={systems}
              activeSystem={activeSystem}
              onDrillDown={drillDown}
            />
          ))}
        </div>
      )}
    </>
  );
}
