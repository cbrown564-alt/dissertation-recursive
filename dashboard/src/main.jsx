import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  Clock3,
  FileText,
  Filter,
  Gauge,
  GitCompareArrows,
  LayoutDashboard,
  Menu,
  Quote,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Table2,
  Wrench
} from "lucide-react";
import "./styles.css";

const SYSTEM_LABELS = {
  S2: "Direct JSON",
  E2: "Event-first aggregate",
  E3: "Constrained aggregate"
};

const ICONS = {
  field_accuracy: BarChart3,
  temporal_correctness: Clock3,
  evidence_validity: Quote,
  schema_validity: ShieldCheck,
  parse_repair: Wrench,
  robustness_degradation: Activity
};

function pct(value, options = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  const number = Number(value);
  const signed = options.signed && number > 0 ? "+" : "";
  const decimals = options.decimals ?? 1;
  return `${signed}${(number * 100).toFixed(decimals)}%`;
}

function shortPerturbation(value) {
  return String(value)
    .replace("reordered_sections", "reordered")
    .replace("removed_headings", "headings")
    .replace("bullets_to_prose", "bullets")
    .replace("historical_medication_trap", "historical med")
    .replace("planned_medication_trap", "planned med")
    .replace("family_history_trap", "family hx")
    .replace("negated_investigation_trap", "negated MRI")
    .replaceAll("_", " ");
}

function ms(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  return `${Number(value).toFixed(2)} ms`;
}

function clamp(value, min = 0, max = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 0;
  return Math.max(min, Math.min(max, Number(value)));
}

function useDashboardData() {
  const [state, setState] = useState({ status: "loading", data: null, error: null });

  useEffect(() => {
    fetch("/data/dashboard_data.json")
      .then((response) => {
        if (!response.ok) throw new Error(`Dashboard data failed to load: ${response.status}`);
        return response.json();
      })
      .then((data) => setState({ status: "ready", data, error: null }))
      .catch((error) => setState({ status: "error", data: null, error }));
  }, []);

  return state;
}

function Sidebar() {
  const items = [
    { icon: Gauge, label: "Overview", active: true },
    { icon: LayoutDashboard, label: "Panels" },
    { icon: Table2, label: "Documents" },
    { icon: FileText, label: "Artifacts" },
    { icon: ShieldCheck, label: "Validation" },
    { icon: Settings, label: "Settings" }
  ];

  return (
    <aside className="sidebar" aria-label="Dashboard navigation">
      <div className="brand-mark"><Gauge size={24} /></div>
      <nav>
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.label} className={`nav-button ${item.active ? "is-active" : ""}`} title={item.label}>
              <Icon size={22} />
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

function Header({ meta, activeSystem, setActiveSystem, systems }) {
  return (
    <header className="app-header">
      <div>
        <h1>Reliability Dashboard</h1>
        <p>{meta?.split || "development"} split · generated {meta?.generated_at ? new Date(meta.generated_at).toLocaleString() : "from run artifacts"}</p>
      </div>
      <div className="header-controls">
        <label className="control search-control">
          <Search size={16} />
          <input defaultValue="EA0001" aria-label="Search documents" />
        </label>
        <button className="control">
          <CalendarDays size={16} />
          <span>Current run</span>
        </button>
        <button className="control">
          <Filter size={16} />
          <span>All letters</span>
        </button>
        <div className="segmented" aria-label="Selected system">
          {systems.map((system) => (
            <button
              key={system.id}
              className={activeSystem === system.id ? "is-selected" : ""}
              onClick={() => setActiveSystem(system.id)}
            >
              {system.id}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}

function Legend({ systems }) {
  return (
    <div className="legend">
      {systems.map((system) => (
        <span key={system.id}>
          <i style={{ background: system.color }} />
          <strong>{system.id}</strong>
          {system.label}
        </span>
      ))}
    </div>
  );
}

function KpiCard({ card, systems }) {
  const Icon = ICONS[card.id] || CheckCircle2;
  const isDelta = card.id === "robustness_degradation";
  return (
    <section className="kpi-card">
      <div className="kpi-title">
        <span><Icon size={20} /></span>
        <h2>{card.label}</h2>
      </div>
      <div className="kpi-values">
        {systems.map((system) => (
          <div key={system.id}>
            <span style={{ color: system.color }}>{system.id}</span>
            <strong>{pct(card.values?.[system.id], { signed: isDelta, decimals: 0 })}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function Panel({ title, children, action }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function BarChart({ rows, systems }) {
  const width = 620;
  const height = 250;
  const margin = { top: 18, right: 18, bottom: 54, left: 58 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const group = plotWidth / Math.max(rows.length, 1);
  const barWidth = Math.min(18, group / (systems.length + 2));

  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Field accuracy bar chart">
      {[0.6, 0.7, 0.8, 0.9, 1].map((tick) => {
        const y = margin.top + (1 - tick) * plotHeight;
        return (
          <g key={tick}>
            <line x1={margin.left} x2={width - margin.right} y1={y} y2={y} className="gridline" />
            <text x={margin.left - 10} y={y + 4} textAnchor="end" className="axis-label">{pct(tick, { compact: true })}</text>
          </g>
        );
      })}
      {rows.map((row, rowIndex) => {
        const xBase = margin.left + rowIndex * group + group / 2 - (systems.length * barWidth) / 2;
        return (
          <g key={row.field}>
            {systems.map((system, systemIndex) => {
              const value = clamp(row.values?.[system.id]);
              const barHeight = value * plotHeight;
              return (
                <rect
                  key={system.id}
                  x={xBase + systemIndex * (barWidth + 5)}
                  y={margin.top + plotHeight - barHeight}
                  width={barWidth}
                  height={barHeight}
                  rx="2"
                  fill={system.color}
                />
              );
            })}
            <text x={margin.left + rowIndex * group + group / 2} y={height - 28} textAnchor="middle" className="x-label">
              {row.field}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function Donut({ data, activeSystem, systems }) {
  const active = data.find((row) => row.system === activeSystem) || data[0] || { valid: 0, minor: 0, major: 0 };
  const values = [
    { label: "Valid", value: active.valid, color: systems.find((system) => system.id === active.system)?.color || "#2878d8" },
    { label: "Minor violations", value: active.minor, color: "#45b8b1" },
    { label: "Major violations", value: active.major, color: "#f26d2b" }
  ];
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 210 210" className="donut" role="img" aria-label="Schema validity donut">
        <circle cx="105" cy="105" r={radius} fill="none" stroke="#edf2f4" strokeWidth="24" />
        {values.map((item) => {
          const dash = clamp(item.value) * circumference;
          const element = (
            <circle
              key={item.label}
              cx="105"
              cy="105"
              r={radius}
              fill="none"
              stroke={item.color}
              strokeWidth="24"
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
              strokeLinecap="butt"
              transform="rotate(-90 105 105)"
            />
          );
          offset += dash;
          return element;
        })}
        <text x="105" y="96" textAnchor="middle" className="donut-small">Overall</text>
        <text x="105" y="123" textAnchor="middle" className="donut-value">{pct(active.valid)}</text>
      </svg>
      <div className="donut-legend">
        {values.map((item) => (
          <span key={item.label}><i style={{ background: item.color }} />{item.label}<strong>{pct(item.value)}</strong></span>
        ))}
      </div>
    </div>
  );
}

function LineChart({ rows, systems }) {
  const width = 560;
  const height = 240;
  const margin = { top: 18, right: 18, bottom: 52, left: 48 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const pointsFor = (systemId) =>
    rows.map((row, index) => {
      const raw = row.values?.[systemId];
      if (raw === null || raw === undefined || Number.isNaN(Number(raw))) return null;
      const value = Number(raw);
      const yValue = value;
      const y = margin.top + clamp((0 - yValue) / 0.2) * plotHeight;
      const x = margin.left + (index / Math.max(rows.length - 1, 1)) * plotWidth;
      return { x, y, value: yValue, label: row.perturbation };
    }).filter(Boolean);

  const hasPoints = systems.some((system) => pointsFor(system.id).length > 0);

  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Robustness degradation line chart">
      {[0, -0.05, -0.1, -0.15, -0.2].map((tick) => {
        const y = margin.top + ((0 - tick) / 0.2) * plotHeight;
        return (
          <g key={tick}>
            <line x1={margin.left} x2={width - margin.right} y1={y} y2={y} className="gridline" />
            <text x={margin.left - 10} y={y + 4} textAnchor="end" className="axis-label">{pct(tick, { signed: true })}</text>
          </g>
        );
      })}
      {!hasPoints && (
        <text x={width / 2} y={height / 2} textAnchor="middle" className="empty-chart-text">
          clean baseline required for degradation deltas
        </text>
      )}
      {systems.map((system) => {
        const points = pointsFor(system.id);
        if (!points.length) return null;
        const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
        return (
          <g key={system.id}>
            <path d={path} fill="none" stroke={system.color} strokeWidth="3" />
            {points.map((point) => (
              <circle key={`${system.id}-${point.label}`} cx={point.x} cy={point.y} r="4" fill="#fff" stroke={system.color} strokeWidth="2" />
            ))}
          </g>
        );
      })}
      {rows.map((row, index) => (
        <text key={row.perturbation} x={margin.left + (index / Math.max(rows.length - 1, 1)) * plotWidth} y={height - 28} textAnchor="middle" className="x-label">
          {shortPerturbation(row.perturbation)}
        </text>
      ))}
    </svg>
  );
}

function EvidencePanel({ examples, activeSystem }) {
  const visible = examples.filter((example) => example.system === activeSystem).slice(0, 3);
  const fallback = examples.slice(0, 3);
  const rows = visible.length ? visible : fallback;
  return (
    <div className="evidence-list">
      {rows.map((item, index) => (
        <article key={`${item.system}-${item.document_id}-${index}`} className="evidence-row">
          <Quote size={18} />
          <p>{item.quote}</p>
          <strong>{item.system}</strong>
          <div className="span-bars" aria-hidden="true">
            <i style={{ width: `${70 - index * 8}%` }} />
            <b style={{ width: `${42 + index * 12}%` }} />
          </div>
        </article>
      ))}
    </div>
  );
}

function FormatComparison({ data }) {
  return (
    <div className="format-grid">
      <div className="mini-bars">
        {data.metrics?.map((metric) => (
          <div key={metric.metric} className="mini-row">
            <span>{metric.metric}</span>
            <div><i style={{ height: `${clamp(metric.json) * 100}%` }} /></div>
            <div><b style={{ height: `${clamp(metric.yaml) * 100}%` }} /></div>
          </div>
        ))}
      </div>
      <aside className="mean-box">
        <span>JSON mean</span>
        <strong>{pct(data.mean?.json)}</strong>
        <span>YAML mean</span>
        <strong className="is-muted">{pct(data.mean?.yaml)}</strong>
        <em>{pct((data.mean?.json || 0) - (data.mean?.yaml || 0), { signed: true })}</em>
      </aside>
    </div>
  );
}

function ModelMatrix({ rows }) {
  const metrics = [
    ["field_accuracy", "Field accuracy"],
    ["temporal_correctness", "Temporal correctness"],
    ["evidence_validity", "Evidence validity"],
    ["schema_validity", "Schema validity"],
    ["parse_repair", "Parse / repair"]
  ];
  const columns = rows.slice(0, 6);
  return (
    <table className="matrix">
      <thead>
        <tr>
          <th>Metric</th>
          {columns.map((row) => <th key={row.condition}>{row.condition || row.system}</th>)}
        </tr>
      </thead>
      <tbody>
        {metrics.map(([key, label]) => (
          <tr key={key}>
            <td>{label}</td>
            {columns.map((row) => {
              const value = row[key];
              return <td key={`${row.condition}-${key}`} style={{ background: heat(value) }}>{pct(value)}</td>;
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function heat(value) {
  if (value === null || value === undefined) return "transparent";
  const v = clamp(value);
  if (v >= 0.95) return "#dff2e8";
  if (v >= 0.85) return "#eaf4fb";
  if (v >= 0.75) return "#fff3cf";
  return "#fde5dd";
}

function DocumentTable({ rows, activeSystem }) {
  const visible = rows.filter((row) => row.system === activeSystem).slice(0, 5);
  return (
    <table className="document-table">
      <thead>
        <tr>
          <th>Document</th>
          <th>System</th>
          <th>Schema</th>
          <th>Evidence</th>
          <th>Temporal</th>
          <th>Issues</th>
        </tr>
      </thead>
      <tbody>
        {(visible.length ? visible : rows.slice(0, 5)).map((row) => (
          <tr key={`${row.system}-${row.document_id}`}>
            <td>{row.document_id}</td>
            <td>{row.system}</td>
            <td>{row.schema_valid ? "valid" : "check"}</td>
            <td>{pct(row.quote_validity)}</td>
            <td>{pct(row.temporal_accuracy)}</td>
            <td>{row.issues?.length ? row.issues.slice(0, 3).join(", ") : "none"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function LoadingScreen({ error }) {
  return (
    <main className="loading-screen">
      <RefreshCw size={28} />
      <h1>{error ? "Dashboard data unavailable" : "Loading dashboard"}</h1>
      <p>{error ? error.message : "Reading reproducible run outputs."}</p>
    </main>
  );
}

function App() {
  const { status, data, error } = useDashboardData();
  const [activeSystem, setActiveSystem] = useState("E2");

  const systems = data?.systems || [];
  const activeSummary = data?.summary_by_system?.[activeSystem] || {};
  const activeLatency = ms(activeSummary.mean_latency_ms);

  const chartRows = useMemo(() => data?.field_accuracy || [], [data]);

  if (status !== "ready") return <LoadingScreen error={error} />;

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="dashboard">
        <Header meta={data.meta} activeSystem={activeSystem} setActiveSystem={setActiveSystem} systems={systems} />
        <section className="kpi-grid">
          {data.kpis.map((card) => <KpiCard key={card.id} card={card} systems={systems} />)}
        </section>
        <Legend systems={systems} />
        <section className="main-grid">
          <Panel title="Field accuracy" action={<span className="panel-note">{activeLatency}</span>}>
            <BarChart rows={chartRows} systems={systems} />
          </Panel>
          <Panel title="Evidence validity" action={<button className="icon-action"><SlidersHorizontal size={16} /></button>}>
            <EvidencePanel examples={data.evidence_examples} activeSystem={activeSystem} />
          </Panel>
          <Panel title="Schema validity">
            <Donut data={data.schema_breakdown} activeSystem={activeSystem} systems={systems} />
          </Panel>
          <Panel title="Robustness degradation">
            <LineChart rows={data.robustness} systems={systems} />
          </Panel>
          <Panel title="JSON vs YAML">
            <FormatComparison data={data.format_comparison} />
          </Panel>
          <Panel title="Model families">
            <ModelMatrix rows={data.model_family} />
          </Panel>
          <Panel title="Documents needing review" action={<button className="control compact"><Menu size={15} />Export</button>}>
            <DocumentTable rows={data.documents} activeSystem={activeSystem} />
          </Panel>
        </section>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
