"use client";

import { useEffect, useState } from "react";
import { MsalProvider } from "@azure/msal-react";

import { initializeMsal } from "../lib/msalConfig.js";

export default function MsalClientProvider({ children }) {
  const [instance, setInstance] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    initializeMsal()
      .then((readyInstance) => {
        if (active) setInstance(readyInstance);
      })
      .catch(() => {
        if (active) {
          setError(
            "La autenticación no está configurada. Revisa las variables de Microsoft Entra ID.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <main className="auth-page">
        <section className="auth-card" role="alert">
          <h1>No se puede iniciar sesión</h1>
          <p>{error}</p>
        </section>
      </main>
    );
  }
  if (!instance) {
    return (
      <main className="auth-page">
        <p role="status">Preparando inicio de sesión seguro...</p>
      </main>
    );
  }
  return <MsalProvider instance={instance}>{children}</MsalProvider>;
}
