"use client";

import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const { instance, accounts, inProgress } = useMsal();
  const router = useRouter();
  const [error, setError] = useState("");
  const [isSigningIn, setIsSigningIn] = useState(false);

  useEffect(() => {
    const account = instance.getActiveAccount() || accounts[0];
    if (account) {
      instance.setActiveAccount(account);
      router.replace("/dashboard");
    }
  }, [accounts, instance, router]);

  async function signIn() {
    setError("");
    setIsSigningIn(true);
    try {
      const result = await instance.loginPopup();
      if (result.account) instance.setActiveAccount(result.account);
      router.replace("/dashboard");
    } catch {
      setError("No se pudo completar el inicio de sesión. Inténtalo de nuevo.");
    } finally {
      setIsSigningIn(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="login-title">
        <p className="eyebrow">Distribuidora Río Claro</p>
        <h1 id="login-title">Inicia sesión</h1>
        <p>
          Usa tu cuenta organizacional. El acceso a las herramientas depende
          del único rol de aplicación asignado a tu cuenta.
        </p>
        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
        <button
          className="button button-primary auth-button"
          type="button"
          onClick={signIn}
          disabled={isSigningIn || inProgress !== "none"}
        >
          {isSigningIn || inProgress !== "none"
            ? "Conectando..."
            : "Continuar con Microsoft"}
        </button>
      </section>
    </main>
  );
}
