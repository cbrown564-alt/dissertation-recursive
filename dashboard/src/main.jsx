import React, { useEffect, useReducer, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, BarChart3, Clock3, FileText, Gauge,
  Quote, Search, Settings, ShieldCheck, Table2, X
} from "lucide-react";
import "./styles.css";
import { AppContext } from "./context.js";
import { SYSTEM_COLORS } from "./utils.js";
import Overview from "./views/Overview.jsx";
import Fields from "./views/Fields.jsx";
import Evidence from "./views/Evidence.jsx";
import Robustness from "./views/Robustness.jsx";
import Documents from "./views/Documents.jsx";
import Artifacts from "./views/Artifacts.jsx";
import SettingsView from "./views/Settings.jsx";

// ── State ─────────────────────────────────────────────────────────────────────

const initialState = { activeSystem: "E2", searchQuery: "", fieldFilter: null };

function reducer(state, action) {
  switch (action.type) {
    case "SET_SYSTEM":       return { ...state, activeSystem: action.payload };
    case "SET_SEARCH":       return { ...state, searchQuery: action.payload };
    case "SET_FIELD_FILTER": return { ...state, fieldFilter: action.payload };
    default: return state;
  }
}

// ── Routing ───────────────────────────────────────────────────────────────────

function useHashRoute() {
  const get = () => window.location.hash.slice(1) || "overview";
  const [route, setRoute] = useState(get);
  useEffect(() => {
    const handler = () => setRoute(get());
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  return route;
}

// ── Data ──────────────────────────────────────────────────────────────────────

function useDashboardData() {
  const [s, set] = useState({ status: "loading", data: null, error: null });
  useEffect(() => {
    fetch("/data/dashboard_data.json")
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((data) => set({ status: "ready", data, error: null }))
      .catch((error) => set({ status: "error", data: null, error }));
  }, []);
  return s;
}

// ── Navigation ────────────────────────────────────────────────────────────────

const NAV = [
  { id: "overview",   icon: Gauge,      label: "Overview"    },
  { id: "fields",     icon: BarChart3,  label: "Fields"      },
  { id: "evidence",   icon: Quote,      label: "Evidence"    },
  { id: "robustness", icon: Activity,   label: "Robustness"  },
  { id: "documents",  icon: Table2,     label: "Documents"   },
  { id: "artifacts",  icon: FileText,   label: "Artifacts"   },
  { id: "settings",   icon: Settings,   label: "Settings"    },
];

const VIEWS = {
  overview:   Overview,
  fields:     Fields,
  evidence:   Evidence,
  robustness: Robustness,
  documents:  Documents,
  artifacts:  Artifacts,
  settings:   SettingsView,
};

// ── Components ────────────────────────────────────────────────────────────────

function Sidebar({ route, meta }) {
  return (
    <aside className="sidebar" aria-label="Navigation">
      <div className="brand">
        <Gauge size={18} />
        <span>rdash</span>
        <span className="brand-cursor" aria-hidden="true" />
      </div>
      <nav>
        {NAV.map(({ id, icon: Icon, label }) => (
          <a
            key={id}
            href={`#${id}`}
            className={`nav-item ${route === id ? "is-active" : ""}`}
          >
            <Icon size={15} />
            <span>{label}</span>
          </a>
        ))}
      </nav>
      <div className="sidebar-foot">
        <span>{meta?.split || "dev"} split</span>
        <span style={{ color: "var(--dim)" }}>schema {meta?.schema_version || "—"}</span>
      </div>
    </aside>
  );
}

function Header({ meta, systems, state, dispatch }) {
  return (
    <header className="app-header">
      <div className="header-meta">
        <span className="header-badge">{meta?.split || "dev"}</span>
        <span className="header-sep">·</span>
        <span>
          {meta?.generated_at
            ? new Date(meta.generated_at).toLocaleString()
            : "smoke run"}
        </span>
      </div>
      <div className="header-controls">
        <label className="search-wrap">
          <Search size={13} />
          <input
            value={state.searchQuery}
            onChange={(e) => dispatch({ type: "SET_SEARCH", payload: e.target.value })}
            placeholder="Search docs…"
            aria-label="Search documents and evidence"
          />
          {state.searchQuery && (
            <button
              onClick={() => dispatch({ type: "SET_SEARCH", payload: "" })}
              className="search-clear"
              aria-label="Clear search"
            >
              <X size={11} />
            </button>
          )}
        </label>
        <div className="seg" aria-label="Active system">
          {systems.map((s) => (
            <button
              key={s.id}
              className={state.activeSystem === s.id ? "is-active" : ""}
              onClick={() => dispatch({ type: "SET_SYSTEM", payload: s.id })}
              style={
                state.activeSystem === s.id
                  ? { color: s.color, borderColor: s.color }
                  : {}
              }
            >
              {s.id}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}

function LoadingScreen({ error }) {
  return (
    <div className="loading-screen">
      <span className={`load-icon ${error ? "err" : ""}`}>{error ? "✗" : "⟳"}</span>
      <p className="load-title">
        {error ? "Dashboard data unavailable" : "Loading dashboard"}
      </p>
      <p className="load-sub">
        {error ? error.message : "Reading run artifacts…"}
      </p>
    </div>
  );
}

// ── App ───────────────────────────────────────────────────────────────────────

function App() {
  const { status, data, error } = useDashboardData();
  const [state, dispatch] = useReducer(reducer, initialState);
  const route = useHashRoute();

  if (status !== "ready") return <LoadingScreen error={error} />;

  const systems = (data.systems || []).map((s) => ({
    ...s,
    color: SYSTEM_COLORS[s.id] || s.color,
  }));

  const View = VIEWS[route] || Overview;

  return (
    <AppContext.Provider value={{ state, dispatch, data, systems }}>
      <div className="shell">
        <Sidebar route={route} meta={data.meta} />
        <div className="content">
          <Header meta={data.meta} systems={systems} state={state} dispatch={dispatch} />
          <main className="view">
            <View />
          </main>
        </div>
      </div>
    </AppContext.Provider>
  );
}

createRoot(document.getElementById("root")).render(<App />);
