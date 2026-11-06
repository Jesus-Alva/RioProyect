"use client";

import { BRANCH_OPTIONS } from "../lib/branches.js";

export default function BranchMultiSelect({
  id,
  label,
  selectedBranches = [],
  onChange,
  branches = BRANCH_OPTIONS,
  disabled = false,
  description,
  compact = false,
}) {
  const selected = new Set(selectedBranches);

  function toggleBranch(branch, isChecked) {
    const next = new Set(selected);
    if (isChecked) next.add(branch);
    else next.delete(branch);
    onChange(
      BRANCH_OPTIONS.filter(
        ({ value }) => next.has(value) && branches.some((option) => option.value === value),
      ).map(({ value }) => value),
    );
  }

  return (
    <fieldset
      className={`branch-selector ${compact ? "branch-selector-compact" : ""}`}
      disabled={disabled}
      aria-describedby={description ? `${id}-help` : undefined}
    >
      <legend className="branch-selector-legend">
        <span>{label}</span>
        <span className="branch-selector-count">
          {selected.size} de {branches.length} seleccionadas
        </span>
      </legend>
      {description && (
        <p className="branch-selector-help" id={`${id}-help`}>
          {description}
        </p>
      )}
      <div className="branch-option-grid">
        {branches.map(({ value, label: branchLabel }) => {
          const isSelected = selected.has(value);
          const inputId = `${id}-${value}`;
          return (
            <label
              className={`branch-option ${isSelected ? "is-selected" : ""}`}
              htmlFor={inputId}
              key={value}
            >
              <input
                className="branch-option-input"
                id={inputId}
                type="checkbox"
                value={value}
                checked={isSelected}
                onChange={(event) => toggleBranch(value, event.target.checked)}
              />
              <span className="branch-option-check" aria-hidden="true">
                <svg viewBox="0 0 16 16" fill="none">
                  <path d="m3.5 8.2 2.8 2.7 6.2-6" />
                </svg>
              </span>
              <span className="branch-option-label">{branchLabel}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
