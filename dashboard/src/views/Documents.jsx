import React, { useContext, useState } from "react";
import { AppContext } from "../context.js";
import { SYSTEM_COLORS, pct } from "../utils.js";

export default function Documents() {
  const { data, state, dispatch } = useContext(AppContext);
  const { searchQuery, fieldFilter } = state;
  const [sysFilter, setSysFilter] = useState("All");
  const [schemaFilter, setSchemaFilter] = useState("all");
  const [openDrawer, setOpenDrawer] = useState(null);

  const all = data.documents || [];

  const fieldKey = fieldFilter
    ? fieldFilter.toLowerCase().replace(/\s+/g, "_")
    : null;

  const rows = all.filter((row) => {
    const matchSys =
      sysFilter === "All" || row.system === sysFilter;
    const matchSchema =
      schemaFilter === "all" ||
      (schemaFilter === "valid" ? row.schema_valid : !row.schema_valid);
    const q = searchQuery.toLowerCase();
    const matchSearch =
      !q || (row.document_id || "").toLowerCase().includes(q);
    const matchField =
      !fieldKey ||
      (row.issues || []).some((issue) =>
        issue.toLowerCase().includes(fieldKey)
      );
    return matchSys && matchSchema && matchSearch && matchField;
  });

  const clearField = () => dispatch({ type: "SET_FIELD_FILTER", payload: null });

  const toggleDrawer = (key) =>
    setOpenDrawer((prev) => (prev === key ? null : key));

  return (
    <>
      <h1 className="view-title">Documents</h1>
      <p className="view-sub">
        Per-document extraction audit — {rows.length} of {all.length} showing · click row for cross-system view
      </p>

      {fieldFilter && (
        <div className="field-filter-banner">
          <span>
            Filtered to field: <strong>{fieldFilter}</strong>
            {rows.length === 0 && " — no issues recorded for this field in current bundle"}
          </span>
          <button className="banner-clear" onClick={clearField}>clear ×</button>
        </div>
      )}

      <div className="filter-bar">
        {["All", "S2", "E2", "E3"].map((s) => (
          <button
            key={s}
            className={`filter-btn ${sysFilter === s ? "is-active" : ""}`}
            onClick={() => setSysFilter(s)}
          >
            {s}
          </button>
        ))}
        <span className="filter-sep" />
        {[["all", "All"], ["valid", "Valid"], ["invalid", "Failures"]].map(([v, l]) => (
          <button
            key={v}
            className={`filter-btn ${schemaFilter === v ? "is-active" : ""}`}
            onClick={() => setSchemaFilter(v)}
          >
            {l}
          </button>
        ))}
        {searchQuery && (
          <>
            <span className="filter-sep" />
            <span className="filter-count">
              {rows.length} match{rows.length !== 1 ? "es" : ""} for "{searchQuery}"
            </span>
          </>
        )}
      </div>

      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <div className="doc-table-wrap">
          <table className="doc-table">
            <thead>
              <tr>
                <th>Document ID</th>
                <th>System</th>
                <th>Schema</th>
                <th>Evidence</th>
                <th>Temporal</th>
                <th>Issues</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan="6"
                    style={{ textAlign: "center", color: "var(--dim)", padding: 28 }}
                  >
                    no documents match current filter
                  </td>
                </tr>
              )}
              {rows.map((row) => {
                const key = `${row.system}-${row.document_id}`;
                const isOpen = openDrawer === key;
                const siblings = all.filter(
                  (r) => r.document_id === row.document_id && r.system !== row.system
                );
                const allVariants = [row, ...siblings].sort((a, b) =>
                  (a.system || "").localeCompare(b.system || "")
                );

                return (
                  <React.Fragment key={key}>
                    <tr
                      className={isOpen ? "doc-row-selected" : "doc-row"}
                      style={{ cursor: "pointer" }}
                      onClick={() => toggleDrawer(key)}
                    >
                      <td style={{ color: "var(--blue)", fontWeight: 600 }}>
                        {row.document_id}
                      </td>
                      <td>
                        <span
                          style={{
                            color: SYSTEM_COLORS[row.system] || "var(--muted)",
                            fontWeight: 700,
                          }}
                        >
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
                      <td
                        style={{
                          maxWidth: 300,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          color: "var(--muted)",
                        }}
                      >
                        {row.issues?.length
                          ? row.issues.map((issue, i) => (
                              <span
                                key={issue}
                                style={{
                                  color:
                                    fieldKey && issue.toLowerCase().includes(fieldKey)
                                      ? "var(--blue-text)"
                                      : "var(--muted)",
                                  fontWeight:
                                    fieldKey && issue.toLowerCase().includes(fieldKey)
                                      ? 700
                                      : 400,
                                }}
                              >
                                {issue}
                                {i < row.issues.length - 1 ? ", " : ""}
                              </span>
                            ))
                          : "—"}
                      </td>
                    </tr>

                    {isOpen && (
                      <tr className="doc-drawer-row">
                        <td colSpan="6" style={{ padding: 0 }}>
                          <div className="doc-drawer">
                            <div className="doc-drawer-title">
                              Cross-system comparison — {row.document_id}
                            </div>
                            <div className="doc-drawer-grid">
                              {allVariants.map((v) => (
                                <div key={v.system} className="doc-drawer-sys">
                                  <div className="doc-drawer-sys-header">
                                    <span
                                      className="doc-drawer-sys-id"
                                      style={{ color: SYSTEM_COLORS[v.system] || "var(--muted)" }}
                                    >
                                      {v.system}
                                    </span>
                                  </div>
                                  <div className="doc-drawer-row">
                                    <span className="doc-drawer-key">schema</span>
                                    <span className={`tag ${v.schema_valid ? "tag-ok" : "tag-err"}`} style={{ fontSize: 10 }}>
                                      {v.schema_valid ? "valid" : "fail"}
                                    </span>
                                  </div>
                                  <div className="doc-drawer-row">
                                    <span className="doc-drawer-key">evidence</span>
                                    <span className="doc-drawer-val">{pct(v.quote_validity)}</span>
                                  </div>
                                  <div className="doc-drawer-row">
                                    <span className="doc-drawer-key">temporal</span>
                                    <span className="doc-drawer-val">{pct(v.temporal_accuracy)}</span>
                                  </div>
                                  {v.issues?.length > 0 && (
                                    <div className="doc-drawer-issues">
                                      {v.issues.map((iss) => (
                                        <span key={iss} className="doc-drawer-issue-item">{iss}</span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              ))}
                              {allVariants.length < 2 && (
                                <div className="doc-drawer-na">
                                  no other systems evaluated this document
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
