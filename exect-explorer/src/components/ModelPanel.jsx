import React from "react";
import { BrainCircuit, Clock, Database, AlertCircle } from "lucide-react";

export default function ModelPanel() {
  return (
    <div className="side-panel model-panel">
      <div className="panel-header">
        <BrainCircuit size={15} />
        <span>Model Lens</span>
      </div>

      <div className="panel-section">
        <div className="coming-soon-badge">
          <Clock size={12} />
          Later Stage
        </div>
        <p className="panel-lead">
          This lens would overlay model extractions on the gold-standard text,
          showing where inference and annotation diverge.
        </p>
      </div>

      <div className="panel-section">
        <div className="section-title">Recommended Candidate</div>
        <div className="model-candidate">
          <div className="candidate-name">GPT-4.1-mini · E3</div>
          <div className="candidate-meta">
            Best validation F1 across medication, diagnosis and investigations
          </div>
          <div className="candidate-scores">
            <div className="c-score">
              <span className="c-label">Med Name</span>
              <span className="c-val">0.872</span>
            </div>
            <div className="c-score">
              <span className="c-label">Med Full</span>
              <span className="c-val">0.707</span>
            </div>
            <div className="c-score">
              <span className="c-label">Sz Collapsed</span>
              <span className="c-val">0.633</span>
            </div>
            <div className="c-score">
              <span className="c-label">Dx Acc</span>
              <span className="c-val">0.775</span>
            </div>
          </div>
        </div>

        <div className="model-candidate alt">
          <div className="candidate-name">GPT-4.1-mini · S2</div>
          <div className="candidate-meta">
            Strongest on test split for diagnosis (0.850) and medication (0.885)
          </div>
        </div>

        <div className="model-candidate alt">
          <div className="candidate-name">qwen3.6:35b · H6fs</div>
          <div className="candidate-meta">
            Best local deployment candidate — matches frontier at zero cost
          </div>
        </div>
      </div>

      <div className="panel-section">
        <div className="section-title">
          <Database size={12} />
          Data Pipeline Challenge
        </div>
        <div className="challenge-box">
          <AlertCircle size={12} />
          <p>
            Dozens of model + harness variants were tested, but only a subset
            of letters were processed per run. To show model outputs here, we
            would need to:
          </p>
        </div>
        <ol className="challenge-list">
          <li>Pick one authoritative system per split (val / test)</li>
          <li>Map its JSON output back to character spans</li>
          <li>Align model extractions with gold entities for diff rendering</li>
          <li>Handle schema differences between harness outputs</li>
        </ol>
      </div>

      <div className="panel-section">
        <div className="section-title">Proposed Visual Design</div>
        <div className="design-preview">
          <div className="preview-row">
            <span className="preview-gold">Gold</span>
            <span className="preview-arrow">→</span>
            <span className="preview-model">Model</span>
          </div>
          <div className="preview-legend">
            <div className="legend-item">
              <span className="dot match" />
              Exact match
            </div>
            <div className="legend-item">
              <span className="dot partial" />
              Partial / synonym
            </div>
            <div className="legend-item">
              <span className="dot miss" />
              Miss / hallucination
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
