import React, { useState } from "react";
import { X, Trophy, Target, Crosshair, CheckCircle2, AlertCircle } from "lucide-react";
import RadialProgress from "./RadialProgress.jsx";

export default function ScoringView({ result, userAnnotations, goldEntities, colours, onClose, onHighlightGold }) {
  const [activeTab, setActiveTab] = useState("summary"); // summary | spans | full

  const { overall, byType } = result;

  const typeNames = Object.keys(byType).sort();

  return (
    <div className="side-panel scoring-view">
      <div className="panel-header">
        <Trophy size={15} />
        <span>Your Score</span>
        <button className="panel-close" onClick={onClose}>
          <X size={14} />
        </button>
      </div>

      <div className="score-tabs">
        <button className={activeTab === "summary" ? "is-active" : ""} onClick={() => setActiveTab("summary")}>
          <Target size={12} /> Summary
        </button>
        <button className={activeTab === "spans" ? "is-active" : ""} onClick={() => setActiveTab("spans")}>
          <Crosshair size={12} /> Spans
        </button>
        <button className={activeTab === "full" ? "is-active" : ""} onClick={() => setActiveTab("full")}>
          <CheckCircle2 size={12} /> Full
        </button>
      </div>

      {activeTab === "summary" && (
        <div className="score-summary">
          <div className="score-big">
            <RadialProgress value={overall.fullF1} color={overall.fullF1 > 0.6 ? "#2d8a5e" : overall.fullF1 > 0.3 ? "#b88a5c" : "#c45c3e"} />
            <div className="score-ring-text">
              <span className="score-number">{(overall.fullF1 * 100).toFixed(1)}%</span>
              <span className="score-label">Full F1</span>
            </div>
          </div>

          <div className="score-metrics">
            <div className="score-metric">
              <span className="metric-name">Span Precision</span>
              <span className="metric-value">{(overall.spanPrecision * 100).toFixed(1)}%</span>
            </div>
            <div className="score-metric">
              <span className="metric-name">Span Recall</span>
              <span className="metric-value">{(overall.spanRecall * 100).toFixed(1)}%</span>
            </div>
            <div className="score-metric">
              <span className="metric-name">Span F1</span>
              <span className="metric-value">{(overall.spanF1 * 100).toFixed(1)}%</span>
            </div>
            <div className="score-divider" />
            <div className="score-metric">
              <span className="metric-name">Full Precision</span>
              <span className="metric-value">{(overall.fullPrecision * 100).toFixed(1)}%</span>
            </div>
            <div className="score-metric">
              <span className="metric-name">Full Recall</span>
              <span className="metric-value">{(overall.fullRecall * 100).toFixed(1)}%</span>
            </div>
          </div>

          <div className="score-entities">
            <div className="section-title">Per Entity Type</div>
            {typeNames.map((type) => {
              const r = byType[type];
              const spanF1 = r.spanTP + r.spanFP > 0 && r.spanTP + r.spanFN > 0
                ? (2 * (r.spanTP / (r.spanTP + r.spanFP)) * (r.spanTP / (r.spanTP + r.spanFN))) /
                  ((r.spanTP / (r.spanTP + r.spanFP)) + (r.spanTP / (r.spanTP + r.spanFN)))
                : 0;
              const fullF1 = r.fullTP + r.fullFP > 0 && r.fullTP + r.fullFN > 0
                ? (2 * (r.fullTP / (r.fullTP + r.fullFP)) * (r.fullTP / (r.fullTP + r.fullFN))) /
                  ((r.fullTP / (r.fullTP + r.fullFP)) + (r.fullTP / (r.fullTP + r.fullFN)))
                : 0;
              const colour = colours[type] || "#999";
              return (
                <div key={type} className="score-entity-row">
                  <div className="se-type" style={{ color: colour }}>
                    {type.replace(/([A-Z])/g, " $1").trim()}
                  </div>
                  <div className="se-bars">
                    <div className="se-bar-wrap">
                      <div className="se-bar-label">Span</div>
                      <div className="se-bar-track">
                        <div className="se-bar" style={{ width: `${spanF1 * 100}%`, background: colour }} />
                      </div>
                    </div>
                    <div className="se-bar-wrap">
                      <div className="se-bar-label">Full</div>
                      <div className="se-bar-track">
                        <div className="se-bar" style={{ width: `${fullF1 * 100}%`, background: colour }} />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {activeTab === "spans" && (
        <ScoreDetail typeNames={typeNames} byType={byType} mode="span" colours={colours} onHighlightGold={onHighlightGold} />
      )}

      {activeTab === "full" && (
        <ScoreDetail typeNames={typeNames} byType={byType} mode="full" colours={colours} onHighlightGold={onHighlightGold} />
      )}
    </div>
  );
}

function ScoreDetail({ typeNames, byType, mode, colours, onHighlightGold }) {
  return (
    <div className="score-detail">
      {typeNames.map((type) => {
        const r = byType[type];
        const matches = mode === "span" ? r.matches : r.matches.filter((m) => {
          // For full mode, only show matches that also have good attributes
          const userKeys = Object.keys(m.user.attributes || {}).filter(k => k !== "CUI" && k !== "CUIPhrase");
          const goldKeys = Object.keys(m.gold.attributes || {}).filter(k => k !== "CUI" && k !== "CUIPhrase");
          if (userKeys.length === 0 && goldKeys.length === 0) return true;
          let matchCount = 0;
          let total = 0;
          const allKeys = new Set([...userKeys, ...goldKeys]);
          allKeys.forEach(k => {
            total++;
            const u = String(m.user.attributes[k] || "").toLowerCase().trim();
            const g = String(m.gold.attributes[k] || "").toLowerCase().trim();
            if (u === g) matchCount++;
          });
          return total > 0 ? matchCount / total >= 0.5 : true;
        });
        const fp = mode === "span" ? r.falsePositives : r.falsePositives;
        const fn = mode === "span" ? r.falseNegatives : r.falseNegatives;

        return (
          <div key={type} className="score-type-block">
            <div className="stb-header" style={{ color: colours[type] || "#999" }}>
              {type.replace(/([A-Z])/g, " $1").trim()}
            </div>

            {matches.length > 0 && (
              <div className="stb-section">
                <div className="stb-label correct">
                  <CheckCircle2 size={11} /> Matches ({matches.length})
                </div>
                {matches.map((m, i) => (
                  <div key={i} className="stb-item correct" onClick={() => onHighlightGold?.(m.gold.id)}>
                    <span className="stb-text">{m.user.text.replace(/-/g, " ").slice(0, 40)}</span>
                  </div>
                ))}
              </div>
            )}

            {fp.length > 0 && (
              <div className="stb-section">
                <div className="stb-label fp">
                  <AlertCircle size={11} /> False Positives ({fp.length})
                </div>
                {fp.map((f, i) => (
                  <div key={i} className="stb-item fp">
                    <span className="stb-text">{f.text.replace(/-/g, " ").slice(0, 40)}</span>
                  </div>
                ))}
              </div>
            )}

            {fn.length > 0 && (
              <div className="stb-section">
                <div className="stb-label fn">
                  <AlertCircle size={11} /> Missed ({fn.length})
                </div>
                {fn.map((f, i) => (
                  <div key={i} className="stb-item fn" onClick={() => onHighlightGold?.(f.id)}>
                    <span className="stb-text">{f.text.replace(/-/g, " ").slice(0, 40)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
