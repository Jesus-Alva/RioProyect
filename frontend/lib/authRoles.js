export const ROLE_PROFILES = {
  directivo: { label: "Directivo", name: "Ernesto" },
  analista: { label: "Analista", name: "Laura" },
  gerente: { label: "Gerente", name: "Mariana" },
  bodega: { label: "Bodega", name: "Toño" },
  ti: { label: "TI", name: "Carlos" },
};

export function getRoleFromClaims(claims) {
  const roles = claims?.roles;
  if (!Array.isArray(roles) || roles.length === 0) {
    throw new Error(
      "Esta cuenta no tiene un rol asignado. Solicita al administrador que asigne un rol de aplicación.",
    );
  }
  if (roles.length !== 1) {
    throw new Error(
      "Esta cuenta tiene más de un rol asignado. Solicita al administrador que deje solo un rol de aplicación.",
    );
  }
  if (typeof roles[0] !== "string" || !Object.hasOwn(ROLE_PROFILES, roles[0])) {
    throw new Error(
      "El rol asignado a esta cuenta no está autorizado para Río Claro.",
    );
  }
  return roles[0];
}
