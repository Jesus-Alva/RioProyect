export const AUTH_SESSION_KEY = "rio-claro-session";

export function readSession() {
  const serialized = window.localStorage.getItem(AUTH_SESSION_KEY);
  if (!serialized) return null;

  try {
    const session = JSON.parse(serialized);
    if (typeof session.token !== "string" || !session.token) {
      window.localStorage.removeItem(AUTH_SESSION_KEY);
      return null;
    }
    return session;
  } catch {
    window.localStorage.removeItem(AUTH_SESSION_KEY);
    return null;
  }
}

export function saveSession(token, user) {
  if (typeof token !== "string" || !token || !user?.id) {
    throw new Error("La respuesta de autenticación está incompleta.");
  }
  window.localStorage.setItem(
    AUTH_SESSION_KEY,
    JSON.stringify({ token, user }),
  );
}

export function clearSession() {
  window.localStorage.removeItem(AUTH_SESSION_KEY);
}
