import React, { useContext } from "react";
import { AppContext } from "../context.js";

function fmtSize(bytes) {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(2)} MB`;
}

const STAGES = [
  {
    id: "evaluation",
    label: "Evaluation",
    match: (a) =>
      a.kind === "evaluation" ||
      ["s2_eval", "e2_eval", "e3_eval", "evaluation"].some((t) => a.id?.includes(t)),
  },
  {
    id: "robustness",
    label: "Robustness",
    match: (a) =>
      a.kind === "robustness" || a.id?.includes("robust"),
  },
  {
    id: "direct",
    label: "Direct Baselines",
    match: (a) => a.id?.startsWith("direct") || a.kind === "direct",
  },
  {
    id: "event",
    label: "Event-first",
    match: (a) => a.id?.startsWith("event") || a.kind === "event",
  },
  {
    id: "secondary",
    label: "Secondary Analysis",
    match: (a) => a.id?.startsWith("secondary") || a.kind === "secondary",
  },
  {
    id: "other",
    label: "Other",
    match: () => true,
  },
];

function groupByStage(artifacts) {
  const assigned = new Set();
  const groups = [];

  for (const stage of STAGES) {
    const items = artifacts.filter((a) => !assigned.has(a.id) && stage.match(a));
    items.forEach((a) => assigned.add(a.id));
    if (items.length > 0) {
      groups.push({ ...stage, items });
    }
  }
  return groups;
}

function CompletenessChip({ present, total }) {
  const pct = total > 0 ? present / total : 0;
  const cls = pct === 1 ? "chip-full" : pct === 0 ? "chip-empty" : "chip-partial";
  return (
    <span className={`completeness-chip ${cls}`}>
      {present}/{total}
    </span>
  );
}

export default function Artifacts() {
  const { data } = useContext(AppContext);
  const artifacts = data.meta?.artifacts || [];
  const present = artifacts.filter((a) => a.exists).length;
  const groups = groupByStage(artifacts);

  return (
    <>
      <h1 className="view-title">Artifacts</h1>
      <p className="view-sub">
        Run artifact manifest — {present}/{artifacts.length} present
      </p>

      {artifacts.length === 0 && (
        <p style={{ color: "var(--dim)", fontFamily: "var(--mono)", fontSize: 12 }}>
          no artifacts in bundle
        </p>
      )}

      {groups.map((group) => {
        const groupPresent = group.items.filter((a) => a.exists).length;
        return (
          <div key={group.id} className="artifact-stage">
            <div className="artifact-stage-header">
              <span className="artifact-stage-label">{group.label}</span>
              <CompletenessChip present={groupPresent} total={group.items.length} />
            </div>
            <div className="artifact-list">
              {group.items.map((a) => (
                <div key={a.id} className="artifact-row">
                  <div
                    className="artifact-dot"
                    style={{ background: a.exists ? "#047857" : "#b91c1c" }}
                  />
                  <div style={{ minWidth: 0 }}>
                    <div className="artifact-id">{a.id.replaceAll("_", " ")}</div>
                    <div className="artifact-path">{a.path}</div>
                  </div>
                  <span className="artifact-kind">{a.kind}</span>
                  <span className="artifact-size">
                    {fmtSize(a.size_bytes)}
                    {a.row_count != null ? ` · ${a.row_count}r` : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </>
  );
}
