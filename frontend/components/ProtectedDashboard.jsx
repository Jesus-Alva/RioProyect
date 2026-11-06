"use client";

import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";
import { useRouter } from "next/navigation";

import ChatPanel from "./ChatPanel.jsx";
import { getRoleFromClaims, ROLE_PROFILES } from "../lib/authRoles.js";

const SALES_DEMO = [
  { city: "Guadalajara", sales: "$128,400" },
  { city: "Zapopan", sales: "$96,250" },
  { city: "León", sales: "$87,900" },
  { city: "Querétaro", sales: "$103,600" },
  { city: "Aguascalientes", sales: "$74,300" },
];

const INVOICE_DEMO = [
  { invoice: "Factura de demostración A", confidence: "0.72" },
  { invoice: "Factura de demostración B", confidence: "0.64" },
];

const CUSTOMER_REQUESTS_DEMO = [
  { topic: "Disponibilidad de producto", status: "Pendiente de respuesta" },
  { topic: "Seguimiento de pedido", status: "En preparación" },
  { topic: "Consulta de facturación", status: "Pendiente de respuesta" },
];

function SystemStatusPanel() {
  const [isPaused, setIsPaused] = useState(false);

  return (
    <section className="role-dashboard" aria-labelledby="system-status-title">
      <h2 id="system-status-title">Estado del sistema</h2>
      <p className="system-status">
        <span
          className={`status-light ${isPaused ? "status-light-paused" : ""}`}
          aria-hidden="true"
        />
        {isPaused ? "IA pausada (demostración)" : "Conectado a Azure (demostración)"}
      </p>
      <p>
        Indicador visual de ejemplo; no consulta telemetría ni controla el
        servicio real.
      </p>
      <button
        className="button button-secondary"
        type="button"
        onClick={() => setIsPaused((paused) => !paused)}
        aria-pressed={isPaused}
      >
        {isPaused ? "Reanudar IA (demo)" : "Pausar IA (demo)"}
      </button>
    </section>
  );
}

const ROLE_PANELS = {
  directivo: (
    <section className="role-dashboard">
      <h2>Reporte de ventas</h2>
      <p>Datos ilustrativos. Consulta tendencias por región con el asistente.</p>
      <div className="table-scroll">
        <table className="dashboard-table">
          <thead>
            <tr>
              <th scope="col">Sucursal</th>
              <th scope="col">Ventas de ejemplo</th>
            </tr>
          </thead>
          <tbody>
            {SALES_DEMO.map(({ city, sales }) => (
              <tr key={city}>
                <th scope="row">{city}</th>
                <td>{sales}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  ),
  analista: (
    <section className="role-dashboard">
      <h2>Revisión manual</h2>
      <p>
        Elementos ilustrativos con confianza inferior a 0.8; confirma siempre
        los datos contra el documento original.
      </p>
      <ul className="invoice-list">
        {INVOICE_DEMO.map(({ invoice, confidence }) => (
          <li key={invoice}>
            <span>{invoice}</span>
            <strong>Confianza: {confidence}</strong>
            <span className="review-status">Requiere revisión</span>
          </li>
        ))}
      </ul>
      <p className="dashboard-note">
        Las facturas dudosas requieren validación humana antes de tomar acción.
      </p>
    </section>
  ),
  gerente: (
    <section className="role-dashboard">
      <h2>Atención a clientes</h2>
      <p>
        Solicitudes de ejemplo para preparar respuestas con información oficial.
      </p>
      <ul className="customer-request-list">
        {CUSTOMER_REQUESTS_DEMO.map(({ topic, status }) => (
          <li key={topic}>
            <strong>{topic}</strong>
            <span>{status}</span>
          </li>
        ))}
      </ul>
    </section>
  ),
  bodega: (
    <section className="role-dashboard warehouse-dashboard">
      <h2>Asistente de bodega</h2>
      <p>
        Interfaz optimizada para uso móvil. Dicta una consulta de inventario
        desde el botón grande del chat.
      </p>
    </section>
  ),
};

export default function ProtectedDashboard() {
  const { instance, accounts } = useMsal();
  const router = useRouter();
  const [account, setAccount] = useState(null);
  const [role, setRole] = useState("");
  const [roleError, setRoleError] = useState("");

  useEffect(() => {
    const currentAccount = instance.getActiveAccount() || accounts[0];
    if (!currentAccount) {
      router.replace("/login");
      return;
    }
    instance.setActiveAccount(currentAccount);
    setAccount(currentAccount);
    try {
      setRole(getRoleFromClaims(currentAccount.idTokenClaims));
      setRoleError("");
    } catch (error) {
      setRole("");
      setRoleError(error.message);
    }
  }, [accounts, instance, router]);

  async function signOut() {
    try {
      await instance.logoutPopup({ account });
      router.replace("/login");
    } catch {
      setRoleError("No se pudo cerrar la sesión. Inténtalo de nuevo.");
    }
  }

  if (!account) {
    return (
      <main className="auth-page">
        <p role="status">Verificando tu sesión...</p>
      </main>
    );
  }

  if (roleError) {
    return (
      <main className="auth-page">
        <section className="auth-card" aria-labelledby="role-error-title">
          <h1 id="role-error-title">No se puede habilitar el acceso</h1>
          <p className="error-message" role="alert">
            {roleError}
          </p>
          <p>Contacta al administrador de Río Claro para corregir tu acceso.</p>
          <button
            className="button button-secondary auth-button"
            type="button"
            onClick={signOut}
          >
            Cerrar sesión
          </button>
        </section>
      </main>
    );
  }

  const profile = ROLE_PROFILES[role];
  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Distribuidora Río Claro</p>
          <h1>Hola, {profile.name}</h1>
          <p className="chat-subtitle">Panel de {profile.label}</p>
        </div>
        <button
          className="button button-secondary"
          type="button"
          onClick={signOut}
        >
          Cerrar sesión
        </button>
      </header>

      {role === "ti" ? <SystemStatusPanel /> : ROLE_PANELS[role]}
      <ChatPanel role={role} account={account} />
      <aside className="transparency-banner" role="note">
        Estás interactuando con un asistente de IA. Las respuestas se basan en
        documentos oficiales.
      </aside>
    </main>
  );
}
