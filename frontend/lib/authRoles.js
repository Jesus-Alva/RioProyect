export const ROLE_PROFILES = {
  directivo: { label: "Directivo", name: "Ernesto" },
  analista: { label: "Analista", name: "Laura" },
  gerente: { label: "Gerente", name: "Mariana" },
  bodega: { label: "Bodega", name: "Toño" },
  ti: { label: "TI", name: "Carlos" },
  admin: { label: "Administrador", name: "Administración" },
};

export const OPERATIONAL_ROLES = Object.keys(ROLE_PROFILES).filter(
  (role) => role !== "admin",
);

export function isSupportedRole(role) {
  return Object.hasOwn(ROLE_PROFILES, role);
}
