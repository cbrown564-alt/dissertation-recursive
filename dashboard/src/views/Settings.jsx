import React, { useContext, useState } from "react";
import { Copy, Check } from "lucide-react";
import { AppContext } from "../context.js";

function buildReproCommand(meta) {
  if (!meta) return null;
  const parts = ["python src/dashboard_export.py"];
  if (meta.evaluation_dir)   parts.push(`  --evaluation-dir "${meta.evaluation_dir}"`);
  if (meta.robustness_dir)   parts.push(`  --robustness-dir "${meta.robustness_dir}"`);
  if (meta.direct_run_dir)   parts.push(`  --direct-run-dir "${meta.direct_run_dir}"`);
  if (meta.event_run_dir)    parts.push(`  --event-run-dir "${meta.event_run_dir}"`);
  if (meta.secondary_dirs?.length) {
    meta.secondary_dirs.forEach((d) => parts.push(`  --secondary-dir "${d}"`));
  }
  if (meta.split)            parts.push(`  --split "${meta.split}"`);
  parts.push(`  --output dashboard/public/data/dashboard_data.json`);
  return parts.join(" \\\n");
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  };
  return (
    <button className={`repro-copy${copied ? " copied" : ""}`} onClick={copy} title="Copy to clipboard">
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? "copied" : "copy"}
    </button>
  );
}

export default function Settings() {
  const { data } = useContext(AppContext);
  const { meta } = data;

  const reproCmd = buildReproCommand(meta);

  const rows = [
    ["Schema version",   meta?.schema_version],
    ["Exporter version", meta?.exporter_version],
    ["Generated at",     meta?.generated_at ? new Date(meta.generated_at).toLocaleString() : undefined],
    ["Split",            meta?.split],
    ["Evaluation dir",   meta?.evaluation_dir],
    ["Robustness dir",   meta?.robustness_dir],
    ["Secondary dirs",   meta?.secondary_dirs?.join(", ")],
  ];

  return (
    <>
      <h1 className="view-title">Settings & Data</h1>
      <p className="view-sub">Bundle metadata, schema information, and run reproduction</p>

      <div className="panel" style={{ maxWidth: 620 }}>
        <div className="panel-head">
          <span className="panel-title">Bundle Info</span>
        </div>
        {rows.map(([label, value]) => (
          <div key={label} className="settings-row">
            <span className="settings-label">{label}</span>
            <span className="settings-val">{value || "—"}</span>
          </div>
        ))}
      </div>

      {reproCmd && (
        <div className="panel" style={{ maxWidth: 620, marginTop: 12 }}>
          <div className="panel-head" style={{ alignItems: "flex-start" }}>
            <span className="panel-title">Reproduce This Run</span>
            <CopyButton text={reproCmd} />
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.6, marginBottom: 10 }}>
            Re-generate the dashboard bundle from the original evaluation outputs:
          </p>
          <div className="repro-wrap">
            <pre className="repro-block">{reproCmd}</pre>
          </div>
        </div>
      )}

      <div
        className="panel"
        style={{ maxWidth: 620, marginTop: 12, fontFamily: "var(--mono)", fontSize: 12 }}
      >
        <div className="panel-head">
          <span className="panel-title">Validation</span>
        </div>
        <p style={{ color: "var(--muted)", lineHeight: 1.7 }}>
          Validate the current bundle against the schema:
        </p>
        <code
          style={{
            display: "block",
            background: "var(--raised)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "12px 16px",
            color: "var(--green)",
            marginTop: 10,
            fontSize: 12,
            overflowX: "auto",
          }}
        >
          python src/dashboard_export.py validate
        </code>
      </div>
    </>
  );
}
