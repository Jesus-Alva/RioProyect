const ROLES = [
  { value: "directivo", label: "Directivo (Ernesto)" },
  { value: "analista", label: "Analista (Laura)" },
  { value: "gerente", label: "Gerente (Mariana)" },
  { value: "bodega", label: "Bodega (Toño)" },
  { value: "ti", label: "TI (Carlos)" },
];

export default function RoleSelector({ value, onChange, disabled }) {
  return (
    <label className="role-picker" htmlFor="role">
      <span>Perfil de prueba</span>
      <select
        id="role"
        name="role"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        {ROLES.map((role) => (
          <option key={role.value} value={role.value}>
            {role.label}
          </option>
        ))}
      </select>
    </label>
  );
}
