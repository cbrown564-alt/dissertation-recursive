import React from "react";
import { AlertTriangle, Info, Skull } from "lucide-react";

export default function OraclePanel({ data, oracleRates }) {
  if (!data) return null;

  const hasFlaws = data.flaws && data.flaws.length > 0;

  return (
    <div className="side-panel oracle-panel">
      <div className="panel-header">
        <Skull size={15} />
        <span>Oracle Lens</span>
      </div>

      <div className="panel-section">
        <div className="section-title">Hard Ceilings</div>
        <div className="oracle-meters">
          {Object.entries(oracleRates).map(([field, rate]) => {
            const severity = rate > 0.2 ? "critical" : rate > 0.1 ? "warning" : "safe";
            return (
              <div key={field} className={`oracle-meter ${severity}`}>
                <div className="meter-label">{field.replace(/_/g, " ")}</div>
                <div className="meter-bar-wrap">
                  <div className="meter-bar" style={{ width: `${rate * 100}%` }} />
                </div>
                <div className="meter-value">{(rate * 100).toFixed(1)}%</div>
              </div>
            );
          })}
        </div>
      </div>

      {hasFlaws && (
        <div className="panel-section">
          <div className="section-title">Document Flaws</div>
          <div className="flaw-list">
            {data.flaws.map((flaw, i) => (
              <div key={i} className="flaw-item">
                <div className="flaw-top">
                  <AlertTriangle size={12} />
                  <span className="flaw-cat">{flaw.category.replace(/_/g, " ")}</span>
                </div>
                <p className="flaw-desc">{flaw.description}</p>
                {flaw.details && flaw.details.length > 0 && (
                  <div className="flaw-details">
                    {flaw.details.slice(0, 3).map((d, j) => (
                      <span key={j} className="flaw-detail-tag">
                        {d.id || d.type || ""}: {d.text?.slice(0, 30).replace(/-/g, " ")}
                      </span>
                    ))}
                    {flaw.details.length > 3 && (
                      <span className="flaw-detail-tag">+{flaw.details.length - 3} more</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="panel-section">
        <div className="section-title">Structural Context</div>
        <div className="context-box">
          <Info size={12} />
          <p>
            Even with <em>perfect extraction</em>, some fields cannot score 1.0 due to
            annotation gaps, meta-label ambiguity, and benchmark design mismatches.
          </p>
        </div>
      </div>
    </div>
  );
}
