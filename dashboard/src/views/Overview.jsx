import React, { useCallback, useContext, useState } from "react";
import { createPortal } from "react-dom";
import {
  Activity, BarChart3, CheckCircle2, Clock3, Quote, ShieldCheck, Wrench
} from "lucide-react";
import { AppContext } from "../context.js";
import { SYSTEM_COLORS, pct, ms, clamp, heat, shortPert } from "../utils.js";

// ── Metric definitions ────────────────────────────────────────────────────────

const KPI_ICONS = {
  field_accuracy: BarChart3,
  temporal_correctness: Clock3,
  evidence_validity: Quote,
  schema_validity: ShieldCheck,
  parse_repair: Wrench,
  robustness_degradation: Activity,
};

const KPI_DEFS = {
  field_accuracy:         "Mean accuracy across 6 clinical extraction fields",
  temporal_correctness:   "Temporal context accuracy (current vs historical)",
  evidence_validity:      "Quote validity — sourced from document text",
  schema_validity:        "Output passes schema without repair",
  parse_repair:           "Successful parse rate including LLM repair",
  robustness_degradation: "Accuracy drop under label-preserving perturbations",
};

// ── Run Health Banner ─────────────────────────────────────────────────────────

function RunHealthBanner({ kpis, systems, summaryBySys }) {
  if (!kpis?.length) return null;

  const signals = [];

  const fieldKpi   = kpis.find((k) => k.id === "field_accuracy");
  const schemaKpi  = kpis.find((k) => k.id === "schema_validity");
  const parseKpi   = kpis.find((k) => k.id === "parse_repair");
  const robustKpi  = kpis.find((k) => k.id === "robustness_degradation");

  const missingCount = kpis.filter((k) =>
    systems.some((s) => k.missingness?.[s.id])
  ).length;

  const allSysFieldAcc = systems
    .map((s) => fieldKpi?.values?.[s.id])
    .filter((v) => v != null && !isNaN(Number(v)));
  const avgFieldAcc = allSysFieldAcc.length
    ? allSysFieldAcc.reduce((a, b) => a + b, 0) / allSysFieldAcc.length
    : null;

  let status = "ok";

  if (missingCount > 0) {
    signals.push({ cls: "health-warn", icon: "⚠", text: `${missingCount} metric${missingCount > 1 ? "s" : ""} awaiting final run` });
    status = "attention";
  }

  if (avgFieldAcc !== null) {
    if (avgFieldAcc >= 0.85) {
      signals.push({ cls: "health-pass", icon: "✓", text: `Field accuracy ${pct(avgFieldAcc, { decimals: 0 })} avg — above 85% threshold` });
    } else {
      signals.push({ cls: "health-warn", icon: "⚠", text: `Field accuracy ${pct(avgFieldAcc, { decimals: 0 })} avg — below 85% threshold` });
      status = "attention";
    }
  }

  if (schemaKpi) {
    const anyFail = systems.some((s) => (schemaKpi.values?.[s.id] ?? 1) < 0.95);
    if (anyFail) {
      signals.push({ cls: "health-warn", icon: "⚠", text: "Schema failures detected — outputs require repair" });
      status = "attention";
    } else if (!schemaKpi.missingness || systems.every((s) => !schemaKpi.missingness?.[s.id])) {
      signals.push({ cls: "health-pass", icon: "✓", text: "All outputs schema-valid" });
    }
  }

  if (parseKpi) {
    const anyParseFail = systems.some(
      (s) => !parseKpi.missingness?.[s.id] && (parseKpi.values?.[s.id] ?? 1) < 0.9
    );
    if (anyParseFail) {
      signals.push({ cls: "health-warn", icon: "⚠", text: "Parse repair rate below 90% — check extraction prompts" });
      status = "attention";
    }
  }

  if (robustKpi && systems.every((s) => robustKpi.missingness?.[s.id])) {
    signals.push({ cls: "health-miss", icon: "–", text: "Robustness baseline unavailable — smoke run" });
  }

  const isSmoke = systems.every((s) => {
    const n = summaryBySys?.[s.id]?.documents_available;
    return n != null && Number(n) < 5;
  });

  let summary;
  if (isSmoke) {
    summary = "Smoke run — aggregate metrics not representative of full corpus";
  } else if (status === "ok") {
    summary = `${systems.length} systems evaluated · extraction pipeline nominal`;
  } else if (missingCount === kpis.length) {
    summary = "Awaiting final evaluation artifacts";
    status = "missing";
  } else {
    summary = "Review flagged signals — attention required before reporting";
  }

  const statusLabel = status === "ok" ? "NOMINAL" : status === "attention" ? "ATTENTION" : "PENDING";
  const statusColor = status === "ok" ? "var(--green-text)" : status === "attention" ? "var(--amber-text)" : "var(--muted)";

  return (
    <div className={`health-banner health-${status}`}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: signals.length ? 10 : 0 }}>
        <span style={{ fontFamily: "var(--mono)", fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: statusColor }}>
          {statusLabel}
        </span>
        <span style={{ fontSize: 12, color: "var(--text)" }}>{summary}</span>
      </div>
      {signals.length > 0 && (
        <div className="health-signals">
          {signals.map((sig, i) => (
            <div key={i} className={`health-row ${sig.cls}`}>
              <span className="health-icon">{sig.icon}</span>
              <span className="health-text">{sig.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tooltip ───────────────────────────────────────────────────────────────────

function useTooltip() {
  const [tip, setTip] = useState(null);
  const show = useCallback((e, content) => {
    setTip({ x: e.clientX, y: e.clientY, content });
  }, []);
  const move = useCallback((e) => {
    setTip((t) => (t ? { ...t, x: e.clientX, y: e.clientY } : t));
  }, []);
  const hide = useCallback(() => setTip(null), []);
  return { tip, show, move, hide };
}

function Tooltip({ tip }) {
  if (!tip) return null;
  return createPortal(
    <div
      className="chart-tooltip"
      style={{ left: tip.x + 14, top: tip.y - 10 }}
    >
      {tip.content}
    </div>,
    document.body
  );
}

// ── KPI Card ──────────────────────────────────────────────────────────────────

function KpiCard({ card, systems, summaryBySys }) {
  const Icon = KPI_ICONS[card.id] || CheckCircle2;
  const isDelta = card.id === "robustness_degradation";
  return (
    <div className="kpi-card">
      <div className="kpi-label">
        <Icon size={13} />
        {card.label}
      </div>
      <p className="kpi-def">{KPI_DEFS[card.id]}</p>
      <div className="kpi-values">
        {systems.map((s) => {
          const missing = card.missingness?.[s.id];
          const n = summaryBySys?.[s.id]?.documents_available;
          return (
            <div key={s.id} className="kpi-val">
              <span className="kpi-val-sys" style={{ color: s.color }}>{s.id}</span>
              <span className="kpi-val-num" style={{ color: missing ? "var(--dim)" : s.color }}>
                {missing ? "n/a" : pct(card.values?.[s.id], { signed: isDelta, decimals: 0 })}
              </span>
              {n != null && <span className="kpi-denom">n={n}</span>}
              {missing && <span className="kpi-missing">{missing}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Bar Chart ─────────────────────────────────────────────────────────────────

function BarChart({ rows, systems, onBarHover, onBarLeave, onMouseMove }) {
  const w = 580, h = 210;
  const m = { t: 12, r: 8, b: 46, l: 42 };
  const pw = w - m.l - m.r;
  const ph = h - m.t - m.b;
  const grp = pw / Math.max(rows.length, 1);
  const bw = Math.min(15, grp / (systems.length + 2));

  return (
    <svg
      className="chart"
      viewBox={`0 0 ${w} ${h}`}
      onMouseMove={onMouseMove}
      style={{ overflow: "visible" }}
    >
      {[0.6, 0.7, 0.8, 0.9, 1].map((tick) => {
        const y = m.t + (1 - tick) * ph;
        return (
          <g key={tick}>
            <line x1={m.l} x2={w - m.r} y1={y} y2={y} className="gridline" />
            <text x={m.l - 5} y={y + 3} textAnchor="end" className="axis-label">
              {pct(tick, { decimals: 0 })}
            </text>
          </g>
        );
      })}
      {rows.map((row, ri) => {
        const xBase = m.l + ri * grp + grp / 2 - (systems.length * (bw + 4)) / 2;
        return (
          <g key={row.field}>
            {systems.map((s, si) => {
              const v = clamp(row.values?.[s.id]);
              const bh = Math.max(v * ph, 2);
              return (
                <rect
                  key={s.id}
                  x={xBase + si * (bw + 4)}
                  y={m.t + ph - bh}
                  width={bw}
                  height={bh}
                  rx="2"
                  fill={s.color}
                  opacity="0.88"
                  style={{ cursor: "crosshair" }}
                  onMouseEnter={(e) => onBarHover(e, row, s)}
                  onMouseLeave={onBarLeave}
                />
              );
            })}
            <text
              x={m.l + ri * grp + grp / 2}
              y={h - 12}
              textAnchor="middle"
              className="x-label"
            >
              {row.field}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Donut ─────────────────────────────────────────────────────────────────────

function Donut({ data, activeSystem, systems }) {
  const active = data.find((r) => r.system === activeSystem) || data[0] || { valid: 0, minor: 0, major: 0 };
  const sysColor = systems.find((s) => s.id === (active.system || activeSystem))?.color || SYSTEM_COLORS.E2;
  const values = [
    { label: "Valid",  value: active.valid, color: sysColor },
    { label: "Minor",  value: active.minor, color: "#d97706" },
    { label: "Major",  value: active.major, color: "#dc2626" },
  ];
  const r = 52;
  const circ = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 150 150" className="donut">
        <circle cx="75" cy="75" r={r} fill="none" stroke="#e5e7eb" strokeWidth="16" />
        {values.map((item) => {
          const dash = clamp(item.value) * circ;
          const el = (
            <circle
              key={item.label}
              cx="75" cy="75" r={r}
              fill="none"
              stroke={item.color}
              strokeWidth="16"
              strokeDasharray={`${dash} ${circ - dash}`}
              strokeDashoffset={-offset}
              transform="rotate(-90 75 75)"
              opacity="0.9"
            />
          );
          offset += dash;
          return el;
        })}
        <text x="75" y="70" textAnchor="middle" className="donut-label-sm">valid</text>
        <text x="75" y="90" textAnchor="middle" className="donut-label-val">
          {pct(active.valid)}
        </text>
      </svg>
      <div className="donut-legend">
        {values.map((item) => (
          <div key={item.label} className="donut-legend-row">
            <div className="donut-dot" style={{ background: item.color }} />
            <span>{item.label}</span>
            <span className="donut-legend-val">{pct(item.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Line Chart ────────────────────────────────────────────────────────────────

function LineChart({ rows, systems, onPointHover, onPointLeave, onMouseMove }) {
  const w = 500, h = 190;
  const m = { t: 12, r: 8, b: 44, l: 42 };
  const pw = w - m.l - m.r;
  const ph = h - m.t - m.b;

  const pointsFor = (sysId) =>
    rows
      .map((row, i) => {
        const raw = row.values?.[sysId];
        if (raw === null || raw === undefined || isNaN(Number(raw))) return null;
        const v = Number(raw);
        const y = m.t + clamp((0 - v) / 0.2) * ph;
        const x = m.l + (i / Math.max(rows.length - 1, 1)) * pw;
        return { x, y, v, perturbation: row.perturbation };
      })
      .filter(Boolean);

  const hasData = systems.some((s) => pointsFor(s.id).some((p) => p.v !== 0));

  return (
    <svg
      className="chart"
      viewBox={`0 0 ${w} ${h}`}
      onMouseMove={onMouseMove}
      style={{ overflow: "visible" }}
    >
      {[0, -0.05, -0.1, -0.15, -0.2].map((tick) => {
        const y = m.t + ((0 - tick) / 0.2) * ph;
        return (
          <g key={tick}>
            <line x1={m.l} x2={w - m.r} y1={y} y2={y} className="gridline" />
            <text x={m.l - 5} y={y + 3} textAnchor="end" className="axis-label">
              {pct(tick, { signed: true, decimals: 0 })}
            </text>
          </g>
        );
      })}
      {!hasData && (
        <text x={w / 2} y={h / 2} textAnchor="middle" className="empty-chart-text">
          no clean baseline — final matched evaluation required
        </text>
      )}
      {systems.map((s) => {
        const pts = pointsFor(s.id);
        if (!pts.length) return null;
        const path = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
        return (
          <g key={s.id}>
            <path d={path} fill="none" stroke={s.color} strokeWidth="2.5" />
            {pts.map((p) => (
              <circle
                key={`${s.id}-${p.perturbation}`}
                cx={p.x} cy={p.y} r="5"
                fill={s.color}
                style={{ cursor: "crosshair" }}
                onMouseEnter={(e) => onPointHover(e, p, s)}
                onMouseLeave={onPointLeave}
              />
            ))}
          </g>
        );
      })}
      {rows.map((row, i) => (
        <text
          key={row.perturbation}
          x={m.l + (i / Math.max(rows.length - 1, 1)) * pw}
          y={h - 10}
          textAnchor="middle"
          className="x-label"
        >
          {shortPert(row.perturbation)}
        </text>
      ))}
    </svg>
  );
}

// ── Evidence Panel ────────────────────────────────────────────────────────────

function EvidencePanel({ examples, activeSystem }) {
  const rows = examples.filter((e) => e.system === activeSystem).slice(0, 4);
  const items = rows.length ? rows : examples.slice(0, 4);

  return (
    <div className="ev-list">
      {items.length === 0 && (
        <p className="ev-empty">
          no evidence examples in bundle{"\n"}final validation artifacts needed
        </p>
      )}
      {items.map((item, i) => (
        <div key={`${item.system}-${item.document_id}-${i}`} className="ev-row">
          <Quote
            size={13}
            style={{ color: SYSTEM_COLORS[item.system] || "#047857", marginTop: 2 }}
          />
          <p className="ev-text">{item.quote || "—"}</p>
          <div className="ev-meta">
            <span className="ev-sys" style={{ color: SYSTEM_COLORS[item.system] || "#6b7280" }}>
              {item.system}
            </span>
            <span className="ev-field">{item.field || "—"}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Format Comparison ─────────────────────────────────────────────────────────

function FormatComparison({ data }) {
  const jsonColor = "#1d4ed8";
  const yamlColor = "#b45309";
  return (
    <div className="fmt-grid">
      <div className="fmt-bars">
        {(data.metrics || []).map((m) => (
          <div key={m.metric} className="fmt-col">
            <div className="fmt-col-bars">
              <div className="fmt-bar" style={{ height: `${clamp(m.json) * 100}%`, background: jsonColor }} />
              <div className="fmt-bar" style={{ height: `${clamp(m.yaml) * 100}%`, background: yamlColor, opacity: 0.75 }} />
            </div>
            <span className="fmt-col-label">{m.metric}</span>
          </div>
        ))}
      </div>
      <div className="fmt-mean">
        <span className="fmt-mean-label">JSON</span>
        <span className="fmt-mean-val" style={{ color: jsonColor }}>{pct(data.mean?.json)}</span>
        <span className="fmt-mean-label">YAML</span>
        <span className="fmt-mean-val" style={{ color: yamlColor }}>{pct(data.mean?.yaml)}</span>
        <span className="fmt-delta">
          {pct((data.mean?.json || 0) - (data.mean?.yaml || 0), { signed: true })}
        </span>
      </div>
    </div>
  );
}

// ── Model Matrix ──────────────────────────────────────────────────────────────

function ModelMatrix({ rows }) {
  const metrics = [
    ["field_accuracy", "Field"],
    ["temporal_correctness", "Temporal"],
    ["evidence_validity", "Evidence"],
    ["schema_validity", "Schema"],
    ["parse_repair", "Parse"],
  ];
  const cols = rows.slice(0, 6);
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="matrix">
        <thead>
          <tr>
            <th>Metric</th>
            {cols.map((r) => <th key={r.condition}>{r.condition || r.system}</th>)}
          </tr>
        </thead>
        <tbody>
          {metrics.map(([key, label]) => (
            <tr key={key}>
              <td>{label}</td>
              {cols.map((r) => (
                <td key={`${r.condition}-${key}`} style={{ background: heat(r[key]) }}>
                  {pct(r[key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Mini Doc Table ────────────────────────────────────────────────────────────

function MiniDocTable({ rows, activeSystem }) {
  const visible = rows.filter((r) => r.system === activeSystem).slice(0, 6);
  const items = visible.length ? visible : rows.slice(0, 6);
  return (
    <div className="doc-table-wrap">
      <table className="doc-table">
        <thead>
          <tr>
            <th>Document</th><th>Sys</th><th>Schema</th>
            <th>Evidence</th><th>Temporal</th><th>Issues</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={`${row.system}-${row.document_id}`}>
              <td style={{ color: "var(--blue)", fontWeight: 600 }}>{row.document_id}</td>
              <td>
                <span style={{ color: SYSTEM_COLORS[row.system] || "var(--muted)", fontWeight: 700 }}>
                  {row.system}
                </span>
              </td>
              <td>
                <span className={`tag ${row.schema_valid ? "tag-ok" : "tag-err"}`}>
                  {row.schema_valid ? "valid" : "fail"}
                </span>
              </td>
              <td>{pct(row.quote_validity)}</td>
              <td>{pct(row.temporal_accuracy)}</td>
              <td style={{ color: "var(--muted)", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis" }}>
                {row.issues?.length ? row.issues.slice(0, 2).join(", ") : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Overview View ─────────────────────────────────────────────────────────────

export default function Overview() {
  const { data, systems, state } = useContext(AppContext);
  const { activeSystem } = state;
  const activeSummary = data.summary_by_system?.[activeSystem] || {};

  const barTip  = useTooltip();
  const lineTip = useTooltip();

  return (
    <>
      <Tooltip tip={barTip.tip} />
      <Tooltip tip={lineTip.tip} />

      <h1 className="view-title">Overview</h1>
      <p className="view-sub">
        S2 · E2 · E3 reliability — {data.meta?.split} split · {data.meta?.schema_version}
      </p>

      <RunHealthBanner
        kpis={data.kpis || []}
        systems={systems}
        summaryBySys={data.summary_by_system}
      />

      <div className="legend">
        {systems.map((s) => (
          <div key={s.id} className="legend-item">
            <div className="legend-dot" style={{ background: s.color }} />
            <span className="legend-sys" style={{ color: s.color }}>{s.id}</span>
            <span>{s.label}</span>
          </div>
        ))}
      </div>

      <div className="kpi-grid">
        {(data.kpis || []).map((card) => (
          <KpiCard
            key={card.id}
            card={card}
            systems={systems}
            summaryBySys={data.summary_by_system}
          />
        ))}
      </div>

      <div className="overview-grid">
        <div className="panel">
          <div className="panel-head">
            <span className="panel-title">Field Accuracy</span>
            <span className="panel-note">{ms(activeSummary.mean_latency_ms)} avg latency</span>
          </div>
          <BarChart
            rows={data.field_accuracy || []}
            systems={systems}
            onMouseMove={barTip.move}
            onBarLeave={barTip.hide}
            onBarHover={(e, row, s) =>
              barTip.show(e, (
                <div>
                  <div className="tip-field">{row.field}</div>
                  <div className="tip-row">
                    <span className="tip-sys" style={{ color: s.color }}>{s.id}</span>
                    <span className="tip-val">{pct(row.values?.[s.id])}</span>
                  </div>
                  <div className="tip-sub">
                    n={activeSummary.documents_available ?? "—"} documents
                  </div>
                </div>
              ))
            }
          />
        </div>

        <div className="panel">
          <div className="panel-head">
            <span className="panel-title">Evidence Validity</span>
            <span className="panel-note">{activeSystem}</span>
          </div>
          <EvidencePanel examples={data.evidence_examples || []} activeSystem={activeSystem} />
        </div>

        <div className="panel">
          <div className="panel-head">
            <span className="panel-title">Schema Validity</span>
            <span className="panel-note">{activeSystem}</span>
          </div>
          <Donut data={data.schema_breakdown || []} activeSystem={activeSystem} systems={systems} />
        </div>

        <div className="panel">
          <div className="panel-head">
            <span className="panel-title">Robustness Degradation</span>
          </div>
          <LineChart
            rows={data.robustness || []}
            systems={systems}
            onMouseMove={lineTip.move}
            onPointLeave={lineTip.hide}
            onPointHover={(e, p, s) =>
              lineTip.show(e, (
                <div>
                  <div className="tip-field">{p.perturbation.replaceAll("_", " ")}</div>
                  <div className="tip-row">
                    <span className="tip-sys" style={{ color: s.color }}>{s.id}</span>
                    <span className="tip-val">{pct(p.v, { signed: true })}</span>
                  </div>
                  <div className="tip-sub">delta vs clean baseline</div>
                </div>
              ))
            }
          />
        </div>

        <div className="panel">
          <div className="panel-head"><span className="panel-title">JSON vs YAML</span></div>
          <FormatComparison data={data.format_comparison || {}} />
        </div>

        <div className="panel">
          <div className="panel-head"><span className="panel-title">Model Families</span></div>
          <ModelMatrix rows={data.model_family || []} />
        </div>

        <div className="panel span-full">
          <div className="panel-head">
            <span className="panel-title">Documents Needing Review</span>
            <a href="#documents" className="panel-link">view all →</a>
          </div>
          <MiniDocTable rows={data.documents || []} activeSystem={activeSystem} />
        </div>
      </div>
    </>
  );
}
