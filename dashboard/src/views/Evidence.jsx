import React, { useContext, useState } from "react";
import { ChevronDown, ChevronRight, Quote } from "lucide-react";
import { AppContext } from "../context.js";
import { SYSTEM_COLORS } from "../utils.js";

const SYS_FILTERS = ["All", "S2", "E2", "E3"];

function EvidenceRow({ item, isExpanded, onToggle, index }) {
  const sysColor = SYSTEM_COLORS[item.system] || "#5d7898";
  const hasChars = item.char_start != null && item.char_end != null;

  return (
    <div
      className={`ev-row ${isExpanded ? "is-expanded" : ""}`}
      onClick={onToggle}
      style={{ "--sys-color": sysColor, animationDelay: `${index * 25}ms` }}
    >
      <div className="ev-row-main">
        <span className="ev-chevron">
          {isExpanded
            ? <ChevronDown size={12} />
            : <ChevronRight size={12} />}
        </span>

        <p className="ev-text">{item.quote || "—"}</p>

        <div className="ev-meta">
          <span
            className="ev-sys-pill"
            style={{
              color: sysColor,
              background: `${sysColor}18`,
              borderColor: `${sysColor}50`,
            }}
          >
            {item.system}
          </span>
          {item.field && (
            <span className="ev-field">{item.field}</span>
          )}
          {item.support_status && (
            <span
              className={`tag ${
                item.support_status === "supported"
                  ? "tag-ok"
                  : item.support_status === "unsupported"
                  ? "tag-err"
                  : "tag-warn"
              }`}
            >
              {item.support_status}
            </span>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="ev-expanded" onClick={(e) => e.stopPropagation()}>
          <div className="ev-quote-block">
            <Quote size={16} style={{ color: sysColor, opacity: 0.7, flexShrink: 0, marginTop: 2 }} />
            <div style={{ flex: 1 }}>
              <span className="ev-quote-label">extracted quote</span>
              <p className="ev-quote-text">{item.quote || "—"}</p>
            </div>
          </div>

          <div className="ev-detail-grid">
            {item.document_id && (
              <div className="ev-detail-item">
                <span className="ev-detail-label">document</span>
                <span className="ev-detail-val">{item.document_id}</span>
              </div>
            )}
            <div className="ev-detail-item">
              <span className="ev-detail-label">field</span>
              <span className="ev-detail-val">{item.field || "—"}</span>
            </div>
            <div className="ev-detail-item">
              <span className="ev-detail-label">system</span>
              <span className="ev-detail-val" style={{ color: sysColor, fontWeight: 600 }}>
                {item.system}
              </span>
            </div>
            <div className="ev-detail-item">
              <span className="ev-detail-label">status</span>
              <span className="ev-detail-val">{item.support_status || "—"}</span>
            </div>
            {hasChars && (
              <div className="ev-detail-item">
                <span className="ev-detail-label">char offset</span>
                <span className="ev-detail-val">{item.char_start}–{item.char_end}</span>
              </div>
            )}
            {item.note && (
              <div className="ev-detail-item" style={{ gridColumn: "1 / -1" }}>
                <span className="ev-detail-label">note</span>
                <span className="ev-detail-val">{item.note}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Evidence() {
  const { data, state } = useContext(AppContext);
  const { searchQuery } = state;
  const [sysFilter, setSysFilter] = useState("All");
  const [expandedId, setExpandedId] = useState(null);

  const all = data.evidence_examples || [];

  const visible = all.filter((e) => {
    const matchSys = sysFilter === "All" || e.system === sysFilter;
    const q = searchQuery.toLowerCase();
    const matchSearch =
      !q ||
      (e.quote || "").toLowerCase().includes(q) ||
      (e.document_id || "").toLowerCase().includes(q) ||
      (e.field || "").toLowerCase().includes(q);
    return matchSys && matchSearch;
  });

  const toggle = (id) => setExpandedId((prev) => (prev === id ? null : id));

  return (
    <>
      <div className="ev-header">
        <div>
          <h1 className="view-title">Evidence Validity</h1>
          <p className="view-sub" style={{ marginBottom: 0 }}>
            {visible.length} of {all.length} extracted quotes · click any row to inspect
          </p>
        </div>

        <div className="filter-bar" style={{ marginBottom: 0, marginTop: 6 }}>
          {SYS_FILTERS.map((s) => (
            <button
              key={s}
              className={`filter-btn ${sysFilter === s ? "is-active" : ""}`}
              onClick={() => setSysFilter(s)}
              style={
                sysFilter === s && s !== "All"
                  ? {
                      color: SYSTEM_COLORS[s],
                      background: `${SYSTEM_COLORS[s]}15`,
                      borderColor: `${SYSTEM_COLORS[s]}50`,
                    }
                  : {}
              }
            >
              {s}
            </button>
          ))}
          {searchQuery && (
            <>
              <span className="filter-sep" />
              <span className="filter-count">
                {visible.length} match{visible.length !== 1 ? "es" : ""} for "{searchQuery}"
              </span>
            </>
          )}
        </div>
      </div>

      <div className="ev-list">
        {visible.length === 0 && (
          <p className="ev-empty">
            {all.length === 0
              ? "no evidence examples in bundle\nfinal validation artifacts needed to populate this view"
              : "no matches for current filter — clear search or change system"}
          </p>
        )}
        {visible.map((item, i) => {
          const id = `${item.system}-${item.document_id}-${i}`;
          return (
            <EvidenceRow
              key={id}
              item={item}
              isExpanded={expandedId === id}
              onToggle={() => toggle(id)}
              index={i}
            />
          );
        })}
      </div>
    </>
  );
}
