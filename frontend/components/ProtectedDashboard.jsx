"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "motion/react";

import AdminSidebar from "./AdminSidebar.jsx";
import AdminUserManagement from "./AdminUserManagement.jsx";
import ChatPanel from "./ChatPanel.jsx";
import { isSupportedRole, OPERATIONAL_ROLES, ROLE_PROFILES } from "../lib/authRoles.js";
import { clearSession, readSession, saveSession } from "../lib/authSession.js";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

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

async function getApiError(response) {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") return payload.detail;
  } catch {
    return "El servidor devolvió una respuesta inválida.";
  }
  return "No se pudo verificar la sesión.";
}

export default function ProtectedDashboard() {
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const [session, setSession] = useState(null);
  const [activeAgentRole, setActiveAgentRole] = useState(OPERATIONAL_ROLES[0]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function verifySession() {
      const storedSession = readSession();
      if (!storedSession) {
        if (active) setIsLoading(false);
        router.replace("/login");
        return;
      }

      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), 10000);
      try {
        const response = await fetch(
          `${BACKEND_URL.replace(/\/$/, "")}/api/auth/me`,
          {
            signal: controller.signal,
            headers: { Authorization: `Bearer ${storedSession.token}` },
          },
        );
        if (response.status === 401 || response.status === 403) {
          clearSession();
          router.replace("/login");
          return;
        }
        if (!response.ok) {
          throw new Error(await getApiError(response));
        }

        const user = await response.json();
        if (!isSupportedRole(user.role)) {
          clearSession();
          router.replace("/login");
          return;
        }
        saveSession(storedSession.token, user);
        if (active) setSession({ token: storedSession.token, user });
      } catch (requestError) {
        if (active) {
          setError(
            requestError.name === "AbortError"
              ? "El backend tardó demasiado en validar la sesión. Confirma que FastAPI esté activo e inténtalo de nuevo."
              : requestError instanceof TypeError
                ? `No se pudo conectar con el backend (${BACKEND_URL}). Confirma que FastAPI esté activo y que CORS_ORIGINS incluya el origen del frontend.`
                : requestError.message,
          );
        }
      } finally {
        window.clearTimeout(timeoutId);
        if (active) setIsLoading(false);
      }
    }
    verifySession();
    return () => {
      active = false;
    };
  }, [router]);

  function signOut() {
    clearSession();
    router.replace("/login");
  }

  function returnToLogin() {
    clearSession();
    router.replace("/login");
  }

  if (isLoading) {
    return (
      <main className="auth-page">
        <p role="status">Verificando tu sesión...</p>
      </main>
    );
  }
  if (error) {
    return (
      <main className="auth-page">
        <section className="auth-card" role="alert">
          <h1>No se pudo verificar el acceso</h1>
          <p className="error-message">{error}</p>
          <button
            className="button button-secondary auth-button"
            type="button"
            onClick={returnToLogin}
          >
            Volver al inicio de sesión
          </button>
        </section>
      </main>
    );
  }
  if (!session) return null;

  const { user, token } = session;
  const profile = ROLE_PROFILES[user.role];
  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Distribuidora Río Claro</p>
          <h1>
            {user.role === "admin"
              ? "Panel de administración"
              : `Hola, ${profile.name}`}
          </h1>
          <p className="chat-subtitle">
            {user.email} · {profile.label}
          </p>
        </div>
        <button
          className="button button-secondary"
          type="button"
          onClick={signOut}
        >
          Cerrar sesión
        </button>
      </header>

      {user.role === "admin" ? (
        <motion.div
          className="admin-dashboard-layout"
          initial={{ opacity: 0, y: reduceMotion ? 0 : 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduceMotion ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] }}
        >
          <AdminSidebar />
          <div className="admin-dashboard-content">
            <AdminUserManagement
              token={token}
              onUnauthorized={returnToLogin}
            />
            <section
              className="admin-agents-section"
              id="admin-agents"
              aria-labelledby="admin-agents-title"
            >
              <div className="role-dashboard">
                <p className="admin-section-kicker">Asistencia inteligente</p>
                <h2 id="admin-agents-title">Agentes operativos</h2>
                <p>
                  Selecciona un agente para consultar su conversación. Cada uno
                  mantiene su propio historial y filtro de acceso.
                </p>
              </div>
              <div className="admin-agent-tabs" role="tablist" aria-label="Seleccionar agente">
                {OPERATIONAL_ROLES.map((agentRole) => (
                  <button
                    className={`admin-agent-tab ${activeAgentRole === agentRole ? "is-active" : ""}`}
                    id={`agent-tab-${agentRole}`}
                    key={agentRole}
                    type="button"
                    role="tab"
                    aria-selected={activeAgentRole === agentRole}
                    aria-controls={`agent-panel-${agentRole}`}
                    tabIndex={activeAgentRole === agentRole ? 0 : -1}
                    onClick={() => setActiveAgentRole(agentRole)}
                    onKeyDown={(event) => {
                      const currentIndex = OPERATIONAL_ROLES.indexOf(agentRole);
                      let nextIndex = currentIndex;
                      if (event.key === "ArrowRight") {
                        nextIndex = (currentIndex + 1) % OPERATIONAL_ROLES.length;
                      } else if (event.key === "ArrowLeft") {
                        nextIndex = (currentIndex - 1 + OPERATIONAL_ROLES.length) % OPERATIONAL_ROLES.length;
                      } else if (event.key === "Home") {
                        nextIndex = 0;
                      } else if (event.key === "End") {
                        nextIndex = OPERATIONAL_ROLES.length - 1;
                      } else {
                        return;
                      }
                      event.preventDefault();
                      const nextRole = OPERATIONAL_ROLES[nextIndex];
                      setActiveAgentRole(nextRole);
                      document.getElementById(`agent-tab-${nextRole}`)?.focus();
                    }}
                  >
                    <span className="admin-agent-tab-dot" aria-hidden="true" />
                    {ROLE_PROFILES[agentRole].label}
                  </button>
                ))}
              </div>
              <div className="admin-chat-stage">
                {OPERATIONAL_ROLES.map((agentRole) => {
                  const isActive = activeAgentRole === agentRole;
                  return (
                    <motion.div
                      className={`admin-chat-view ${isActive ? "is-active" : ""}`}
                      id={`agent-panel-${agentRole}`}
                      key={agentRole}
                      role="tabpanel"
                      aria-labelledby={`agent-tab-${agentRole}`}
                      aria-hidden={!isActive}
                      inert={!isActive}
                      initial={false}
                      animate={{ opacity: isActive ? 1 : 0, x: isActive ? 0 : 10 }}
                      transition={{
                        duration: reduceMotion ? 0 : 0.22,
                        ease: [0.22, 1, 0.36, 1],
                      }}
                    >
                      <ChatPanel
                        user={user}
                        token={token}
                        agentRole={agentRole}
                        isActive={isActive}
                      />
                    </motion.div>
                  );
                })}
              </div>
            </section>
          </div>
        </motion.div>
      ) : (
        <>
          {user.role === "ti" ? <SystemStatusPanel /> : ROLE_PANELS[user.role]}
          <ChatPanel user={user} token={token} agentRole={user.role} />
        </>
      )}
      <aside className="transparency-banner" role="note">
        Estás interactuando con un asistente de IA. Las respuestas se basan en
        documentos oficiales.
      </aside>
    </main>
  );
}
