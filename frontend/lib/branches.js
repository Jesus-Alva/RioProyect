export const BRANCH_OPTIONS = [
  { value: "guadalajara", label: "Guadalajara" },
  { value: "zapopan", label: "Zapopan" },
  { value: "leon", label: "León" },
  { value: "queretaro", label: "Querétaro" },
  { value: "aguascalientes", label: "Aguascalientes" },
];

export function formatBranchNames(branches) {
  if (!Array.isArray(branches) || branches.length === 0) {
    return "Sin sucursal asignada";
  }
  const labels = new Map(
    BRANCH_OPTIONS.map(({ value, label }) => [value, label]),
  );
  return branches.map((branch) => labels.get(branch) || branch).join(", ");
}

export function getSelectedBranches(selectedOptions, allowedBranches) {
  const allowed = new Set(
    allowedBranches || BRANCH_OPTIONS.map(({ value }) => value),
  );
  const selected = new Set(
    Array.from(selectedOptions || [], (option) => option.value),
  );
  return BRANCH_OPTIONS.filter(
    ({ value }) => allowed.has(value) && selected.has(value),
  ).map(({ value }) => value);
}
