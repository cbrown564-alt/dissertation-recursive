import React, { useState, useEffect } from "react";
import { Save, X, Trash2 } from "lucide-react";

export default function AttributeForm({ annotation, draftType, selection, schema, onSave, onCancel, onDelete }) {
  const [values, setValues] = useState({});
  const [type, setType] = useState(annotation?.type || draftType || "");

  useEffect(() => {
    if (annotation) {
      setValues(annotation.attributes || {});
      setType(annotation.type);
    } else if (draftType) {
      setValues({});
      setType(draftType);
    } else {
      setValues({});
      setType("");
    }
  }, [annotation, draftType, selection]);

  if (!schema && !annotation?.type) {
    // Waiting for type selection
    return (
      <div className="attribute-form empty">
        <p className="form-hint">Select an entity type from the toolbar to begin.</p>
        <button className="form-cancel" onClick={onCancel}>
          <X size={14} /> Cancel
        </button>
      </div>
    );
  }

  const effectiveSchema = schema || { fields: [] };
  const isEditing = !!annotation;
  const displayType = type || draftType || "";

  const handleSubmit = (e) => {
    e.preventDefault();
    if (isEditing) {
      onSave(values);
    } else {
      const selectedType = type || draftType;
      if (!selectedType) return;
      onSave(selectedType, values);
    }
  };

  return (
    <div className="attribute-form">
      <div className="form-header">
        <span className="form-title">
          {isEditing ? `Edit ${displayType}` : `New ${displayType}`}
        </span>
        <button className="form-close" onClick={onCancel}>
          <X size={14} />
        </button>
      </div>

      <div className="form-quote">
        "{(annotation?.text || selection?.text || "").slice(0, 50)}"
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-fields">
          {effectiveSchema.fields.map((field) => (
            <div key={field.key} className="form-field">
              <label>{field.label}</label>
              {field.type === "select" ? (
                <select
                  value={values[field.key] || ""}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, [field.key]: e.target.value }))
                  }
                >
                  <option value="">—</option>
                  {field.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  placeholder={field.placeholder || ""}
                  value={values[field.key] || ""}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, [field.key]: e.target.value }))
                  }
                />
              )}
            </div>
          ))}
        </div>

        <div className="form-actions">
          <button type="submit" className="form-save">
            <Save size={14} />
            {isEditing ? "Update" : "Save Annotation"}
          </button>
          {isEditing && onDelete && (
            <button type="button" className="form-delete" onClick={onDelete}>
              <Trash2 size={14} />
              Delete
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
