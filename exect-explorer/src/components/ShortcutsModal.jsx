import React from "react";
import { X, Keyboard } from "lucide-react";

const SHORTCUTS = [
  { keys: ["Ctrl/Cmd", "←"], action: "Previous letter" },
  { keys: ["Ctrl/Cmd", "→"], action: "Next letter" },
  { keys: ["Esc"], action: "Close panels / clear selection" },
  { keys: ["?"], action: "Show this help" },
];

export default function ShortcutsModal({ onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <Keyboard size={16} />
          <span>Keyboard Shortcuts</span>
          <button className="modal-close" onClick={onClose}>
            <X size={14} />
          </button>
        </div>
        <div className="modal-body">
          {SHORTCUTS.map((s, i) => (
            <div key={i} className="shortcut-row">
              <div className="shortcut-keys">
                {s.keys.map((k, j) => (
                  <span key={j} className="shortcut-key">{k}</span>
                ))}
              </div>
              <span className="shortcut-action">{s.action}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
