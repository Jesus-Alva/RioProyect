"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

import AdminSidebar from "./AdminSidebar.jsx";
import AdminUserManagement from "./AdminUserManagement.jsx";
import BranchMultiSelect from "./BranchMultiSelect.jsx";
import ChatPanel from "./ChatPanel.jsx";
import { isSupportedRole, OPERATIONAL_ROLES, ROLE_PROFILES } from "../lib/authRoles.js";
import { clearSession, readSession, saveSession } from "../lib/authSession.js";
import { BRANCH_OPTIONS, formatBranchNames } from "../lib/branches.js";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const SALES_DEMO = [
  { branch: "guadalajara", city: "Guadalajara", sales: 128400 },
  { branch: "zapopan", city: "Zapopan", sales: 96250 },
  { branch: "leon", city: "León", sales: 87900 },
  { branch: "queretaro", city: "Querétaro", sales: 103600 },
  { branch: "aguascalientes", city: "Aguascalientes", sales: 74300 },
];

function RoleHero({ kicker, title, description, badge = "Espacio de trabajo", titleId }) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.header
      className="role-hero"
      initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduceMotion ? 0 : 0.26, ease: [0.22, 1, 0.36, 1] }}
    >
      <div>
        <p className="director-kicker">{kicker}</p>
        <h2 id={titleId}>{title}</h2>
        <p>{description}</p>
      </div>
      <span className="role-hero-badge"><span aria-hidden="true" />{badge}</span>
    </motion.header>
  );
}

function RoleActionCard({ eyebrow, title, description, index = 0 }) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.article
      className="role-action-card"
      initial={{ opacity: 0, y: reduceMotion ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduceMotion ? 0 : 0.2, delay: reduceMotion ? 0 : index * 0.05 }}
    >
      <span className="role-action-eyebrow">{eyebrow}</span>
      <h3>{title}</h3>
      <p>{description}</p>
    </motion.article>
  );
}

function SystemStatusPanel() {
  const [health, setHealth] = useState("checking");
  const [isChecking, setIsChecking] = useState(true);

  const checkService = useCallback(async () => {
    setIsChecking(true);
    try {
      const response = await fetch(`${BACKEND_URL.replace(/\/$/, "")}/health`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error("Backend no disponible");
      const payload = await response.json();
      setHealth(payload.status === "ok" ? "online" : "offline");
    } catch {
      setHealth("offline");
    } finally {
      setIsChecking(false);
    }
  }, []);

  useEffect(() => {
    checkService();
  }, [checkService]);

  return (
    <section className="role-dashboard role-dashboard-ti" aria-labelledby="system-status-title">
      <RoleHero
        kicker="Soporte técnico"
        title="Estado del servicio"
        titleId="system-status-title"
        description="Consulta la disponibilidad del backend y utiliza el asistente para resolver dudas técnicas sobre el sistema."
        badge="Comprobación en vivo"
      />
      <section className="role-status-card" aria-live="polite">
        <div>
          <span className={`status-light ${health === "offline" ? "status-light-paused" : ""} ${health === "checking" ? "status-light-checking" : ""}`} aria-hidden="true" />
          <div>
            <p className="role-action-eyebrow">API del sistema</p>
            <h3>
              {health === "checking" ? "Verificando conexión…" : health === "online" ? "Backend disponible" : "No se pudo conectar"}
            </h3>
            <p>{health === "online" ? "La comprobación /health respondió correctamente." : health === "offline" ? "Revisa la conexión con el backend y vuelve a intentarlo." : "Consultando el endpoint de salud del backend."}</p>
          </div>
        </div>
        <button className="button button-secondary" type="button" onClick={checkService} disabled={isChecking}>
          {isChecking ? "Comprobando…" : "Comprobar de nuevo"}
        </button>
      </section>
      <div className="role-action-grid role-action-grid-two">
        <RoleActionCard eyebrow="Disponible" title="Consultas técnicas" description="Pregunta al asistente por el uso del sistema y la información técnica permitida." index={0} />
        <RoleActionCard eyebrow="Protegido" title="Acceso autorizado" description="El asistente responde según las fuentes y permisos asignados a tu sesión." index={1} />
      </div>
      <p className="role-data-note">El indicador revisa únicamente la disponibilidad del backend; no mide Azure AI ni otros servicios externos.</p>
    </section>
  );
}

function InventoryPanel({ token, branches }) {
  const reduceMotion = useReducedMotion();
  const [inventory, setInventory] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    let active = true;
    async function loadInventory() {
      setIsLoading(true);
      setError("");
      try {
        const response = await fetch(
          `${BACKEND_URL.replace(/\/$/, "")}/api/inventory`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (response.status === 401) {
          clearSession();
          window.location.replace("/login");
          return;
        }
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(
            typeof payload.detail === "string"
              ? payload.detail
              : "No se pudo consultar el inventario.",
          );
        }
        if (active) setInventory(Array.isArray(payload.items) ? payload.items : []);
      } catch (requestError) {
        if (active) {
          setError(
            requestError instanceof TypeError
              ? "No se pudo conectar con el servicio de inventario."
              : requestError.message,
          );
        }
      } finally {
        if (active) setIsLoading(false);
      }
    }
    loadInventory();
    return () => {
      active = false;
    };
  }, [token, branches, reloadVersion]);

  const normalizedSearch = search.trim().toLocaleLowerCase("es-MX");
  const filteredInventory = inventory.filter((item) =>
    `${item.producto} ${item.branch} ${BRANCH_OPTIONS.find((option) => option.value === item.branch)?.label || ""}`
      .toLocaleLowerCase("es-MX")
      .includes(normalizedSearch),
  );
  const totalUnits = filteredInventory.reduce((total, item) => {
    const quantity = Number(item.cantidad);
    return total + (Number.isFinite(quantity) ? quantity : 0);
  }, 0);

  return (
    <section className="role-dashboard role-dashboard-bodega" aria-labelledby="inventory-title">
      <RoleHero
        kicker="Operación de bodega"
        title="Inventario disponible"
        titleId="inventory-title"
        description={`Consulta existencias autorizadas para: ${formatBranchNames(branches)}.`}
        badge="Datos de inventario"
      />
      <div className="role-kpi-grid role-kpi-grid-two">
        <article className="director-kpi-card director-kpi-primary">
          <span className="director-kpi-label">Productos encontrados</span>
          <strong>{isLoading ? "…" : filteredInventory.length}</strong>
          <span className="director-kpi-footnote">En los resultados visibles</span>
        </article>
        <article className="director-kpi-card">
          <span className="director-kpi-label">Unidades registradas</span>
          <strong>{isLoading ? "…" : totalUnits.toLocaleString("es-MX")}</strong>
          <span className="director-kpi-footnote">Suma de la búsqueda actual</span>
        </article>
      </div>
      <section className="role-data-card" aria-labelledby="inventory-results-title">
        <div className="role-data-card-heading">
          <div>
            <p className="director-kicker">Existencias</p>
            <h3 id="inventory-results-title">Productos por sucursal</h3>
          </div>
          <button className="button button-secondary" type="button" onClick={() => setReloadVersion((version) => version + 1)} disabled={isLoading}>
            {isLoading ? "Actualizando…" : "Actualizar"}
          </button>
        </div>
        <label className="role-search-label" htmlFor="inventory-search">Buscar producto o sucursal</label>
        <input
          className="role-search-input"
          id="inventory-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Ej. agua, Guadalajara…"
        />
        {isLoading ? (
          <p className="role-data-feedback" role="status">Cargando inventario…</p>
        ) : error ? (
          <p className="error-message role-data-feedback" role="alert">{error}</p>
        ) : filteredInventory.length ? (
          <ul className="inventory-results">
            {filteredInventory.map((item, index) => (
              <motion.li
                key={`${item.producto}-${item.branch}-${index}`}
                layout
                initial={{ opacity: reduceMotion ? 1 : 0 }}
                animate={{ opacity: 1 }}
              >
                <span className="inventory-product-mark" aria-hidden="true">
                  {String(item.producto || "?").slice(0, 1).toLocaleUpperCase("es-MX")}
                </span>
                <div className="inventory-item-copy">
                  <strong>{item.producto}</strong>
                  <span>{BRANCH_OPTIONS.find((option) => option.value === item.branch)?.label || item.branch}</span>
                </div>
                <span className="inventory-quantity">
                  <strong>{(Number.isFinite(Number(item.cantidad)) ? Number(item.cantidad) : 0).toLocaleString("es-MX")}</strong>
                  <small>unidades</small>
                </span>
              </motion.li>
            ))}
          </ul>
        ) : (
          <p className="role-data-feedback">
            {inventory.length
              ? "No hay coincidencias para esa búsqueda."
              : "No hay productos de inventario disponibles para esta sucursal."}
          </p>
        )}
      </section>
      <p className="role-data-note">Los resultados se consultan en tiempo real desde el índice y permanecen limitados a las sucursales autorizadas.</p>
    </section>
  );
}

function DirectorPanel({ branches }) {
  const reduceMotion = useReducedMotion();
  const [selectedBranches, setSelectedBranches] = useState(branches);
  const availableBranches = BRANCH_OPTIONS.filter(({ value }) =>
    branches.includes(value),
  );
  const rows = SALES_DEMO.filter(
    (sales) => branches.includes(sales.branch) && selectedBranches.includes(sales.branch),
  ).sort((first, second) => second.sales - first.sales);
  const totalSales = rows.reduce((total, row) => total + row.sales, 0);
  const averageSales = rows.length ? Math.round(totalSales / rows.length) : 0;
  const topBranch = rows[0];
  const maxSales = topBranch?.sales || 1;
  const formatSales = (amount) => `$${amount.toLocaleString("en-US")}`;

  return (
    <section className="director-dashboard" aria-labelledby="director-dashboard-title">
      <motion.header
        className="director-hero"
        initial={{ opacity: 0, y: reduceMotion ? 0 : 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: reduceMotion ? 0 : 0.3, ease: [0.22, 1, 0.36, 1] }}
      >
        <div>
          <p className="director-kicker">Panel directivo</p>
          <h2 id="director-dashboard-title">Resumen ejecutivo</h2>
          <p>Ventas de demostración para las sucursales que tienes autorizadas.</p>
        </div>
        <span className="director-demo-badge">
          <span aria-hidden="true" /> Datos de demostración
        </span>
      </motion.header>

      <div className="director-filter-panel">
        <BranchMultiSelect
          id="director-branches"
          label="Sucursales del reporte"
          description="Selecciona una o más sucursales autorizadas para comparar sus ventas."
          branches={availableBranches}
          selectedBranches={selectedBranches}
          onChange={setSelectedBranches}
          compact
        />
      </div>

      {rows.length === 0 ? (
        <div className="director-empty-state" role="status">
          Selecciona al menos una sucursal para ver el resumen.
        </div>
      ) : (
        <>
          <div className="director-kpi-grid">
            <motion.article
              className="director-kpi-card director-kpi-primary"
              layout
              initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.24, delay: reduceMotion ? 0 : 0.04 }}
            >
              <span className="director-kpi-label">Ventas totales</span>
              <strong>{formatSales(totalSales)}</strong>
              <span className="director-kpi-footnote">
                {rows.length} {rows.length === 1 ? "sucursal seleccionada" : "sucursales seleccionadas"}
              </span>
            </motion.article>
            <motion.article
              className="director-kpi-card"
              layout
              initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.24, delay: reduceMotion ? 0 : 0.1 }}
            >
              <span className="director-kpi-label">Promedio por sucursal</span>
              <strong>{formatSales(averageSales)}</strong>
              <span className="director-kpi-footnote">Promedio de la selección actual</span>
            </motion.article>
            <motion.article
              className="director-kpi-card"
              layout
              initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.24, delay: reduceMotion ? 0 : 0.16 }}
            >
              <span className="director-kpi-label">Mayor venta</span>
              <strong>{topBranch.city}</strong>
              <span className="director-kpi-footnote">{formatSales(topBranch.sales)}</span>
            </motion.article>
          </div>

          <div className="director-insights-grid">
            <section className="director-performance-card" aria-labelledby="director-performance-title">
              <div className="director-section-heading">
                <div>
                  <p className="director-kicker">Comparativo</p>
                  <h3 id="director-performance-title">Ventas por sucursal</h3>
                </div>
                <span className="director-period-label">Vista actual</span>
              </div>
              <ol className="director-performance-list">
                {rows.map(({ branch, city, sales }, index) => (
                  <motion.li
                    key={branch}
                    layout
                    initial={{ opacity: 0, x: reduceMotion ? 0 : 8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: reduceMotion ? 0 : 0.2, delay: reduceMotion ? 0 : index * 0.04 }}
                  >
                    <div className="director-performance-topline">
                      <span className="director-rank">{String(index + 1).padStart(2, "0")}</span>
                      <span className="director-branch-name">{city}</span>
                      <strong>{formatSales(sales)}</strong>
                    </div>
                    <div
                      className="director-bar-track"
                      role="img"
                      aria-label={`${city}: ${formatSales(sales)}`}
                    >
                      <motion.span
                        className="director-bar-fill"
                        initial={{ width: 0 }}
                        animate={{ width: `${(sales / maxSales) * 100}%` }}
                        transition={{ duration: reduceMotion ? 0 : 0.55, delay: reduceMotion ? 0 : 0.12 + index * 0.05 }}
                      />
                    </div>
                  </motion.li>
                ))}
              </ol>
            </section>

            <aside className="director-highlights-card" aria-label="Hallazgo destacado">
              <span className="director-highlight-icon" aria-hidden="true">↗</span>
              <p className="director-kicker">Sucursal destacada</p>
              <h3>{topBranch.city}</h3>
              <strong>{formatSales(topBranch.sales)}</strong>
              <p>Registra la cifra más alta dentro de las sucursales seleccionadas.</p>
            </aside>
          </div>
          <p className="director-data-note">
            Las cifras son ilustrativas y no representan ventas operativas reales.
          </p>
        </>
      )}
    </section>
  );
}

function AnalystPanel() {
  return (
    <section className="role-dashboard role-dashboard-analista" aria-labelledby="analyst-workspace-title">
      <RoleHero
        kicker="Análisis documental"
        title="Revisión de facturas"
        titleId="analyst-workspace-title"
        description="Extrae información clave, localiza datos faltantes y valida los hallazgos contra las fuentes disponibles."
        badge="Revisión humana"
      />
      <div className="role-action-grid">
        <RoleActionCard eyebrow="01 · Extracción" title="Identificar datos" description="Consulta proveedor, fecha, productos y total a partir de las facturas indexadas." index={0} />
        <RoleActionCard eyebrow="02 · Validación" title="Revisar hallazgos" description="Pide al asistente señalar campos ausentes o información que requiera confirmación humana." index={1} />
        <RoleActionCard eyebrow="03 · Trazabilidad" title="Consultar fuentes" description="Las respuestas pueden incluir referencias para contrastar la información con el documento original." index={2} />
      </div>
      <div className="role-guidance-card">
        <span className="role-guidance-icon" aria-hidden="true">✓</span>
        <div>
          <h3>Valida antes de aprobar</h3>
          <p>Usa las consultas sugeridas del asistente para analizar documentos y confirma los datos en la fuente citada.</p>
        </div>
      </div>
    </section>
  );
}

function ManagerPanel() {
  return (
    <section className="role-dashboard role-dashboard-gerente" aria-labelledby="manager-workspace-title">
      <RoleHero
        kicker="Gestión operativa"
        title="Información para decidir"
        titleId="manager-workspace-title"
        description="Consulta facturas y proveedores para obtener resúmenes útiles en la gestión de la sucursal."
        badge="Consulta por sucursal"
      />
      <div className="role-action-grid">
        <RoleActionCard eyebrow="Documentos" title="Revisar facturas" description="Solicita resúmenes de documentos, montos y conceptos disponibles en las fuentes." index={0} />
        <RoleActionCard eyebrow="Proveedores" title="Comparar información" description="Pregunta por los proveedores que aparecen en las facturas y sus datos documentados." index={1} />
        <RoleActionCard eyebrow="Operación" title="Preparar seguimiento" description="Resume hallazgos relevantes y solicita referencias antes de tomar una decisión." index={2} />
      </div>
      <div className="role-guidance-card">
        <span className="role-guidance-icon" aria-hidden="true">↗</span>
        <div>
          <h3>Contexto delimitado</h3>
          <p>Las consultas utilizan únicamente las sucursales asignadas a tu cuenta y muestran cuando la información no está disponible.</p>
        </div>
      </div>
    </section>
  );
}

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
  const [activeAdminSpace, setActiveAdminSpace] = useState("users");
  const [isDirectorChatOpen, setIsDirectorChatOpen] = useState(false);
  const [isDirectorTooltipVisible, setIsDirectorTooltipVisible] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (session?.user?.role !== "directivo") return;
    setIsDirectorTooltipVisible(true);
    const timeoutId = window.setTimeout(() => setIsDirectorTooltipVisible(false), 20_000);
    return () => window.clearTimeout(timeoutId);
  }, [session?.user?.role]);

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
    <main className={`dashboard-shell ${user.role === "admin" ? "dashboard-shell-admin" : user.role === "directivo" ? "dashboard-shell-director" : "dashboard-shell-operational"}`}>
      <header className="dashboard-header">
        <div className="dashboard-brand-lockup">
          <div className="brand-logo-frame dashboard-brand-logo" aria-hidden="true">
            <Image
              src="/rio-claro-logo.png"
              alt=""
              fill
              sizes="(max-width: 480px) 96px, 128px"
              className="brand-logo-image"
            />
          </div>
          <div className="dashboard-heading-copy">
            <h1>
              {user.role === "admin"
                ? "Panel de administración"
                : `Hola, ${profile.name}`}
            </h1>
            <p className="chat-subtitle">
              {user.email} · {profile.label}
              {user.role !== "admin" &&
                ` · ${formatBranchNames(user.branches)}`}
              {user.role === "admin" &&
                ` · Acceso global (${formatBranchNames(user.branches)})`}
            </p>
          </div>
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
          <AdminSidebar
            activeSection={activeAdminSpace}
            onSectionChange={setActiveAdminSpace}
          />
          <div className="admin-dashboard-content">
            <motion.div
              className="admin-space-stage"
              layout
              transition={{
                layout: { duration: reduceMotion ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] },
              }}
            >
              <motion.section
                className={`admin-space-page ${activeAdminSpace === "users" ? "is-active" : ""}`}
                id="admin-space-users"
                aria-label="Usuarios y permisos"
                aria-hidden={activeAdminSpace !== "users"}
                inert={activeAdminSpace !== "users"}
                initial={false}
                animate={{
                  opacity: activeAdminSpace === "users" ? 1 : 0,
                  x: activeAdminSpace === "users" ? 0 : -12,
                }}
                transition={{ duration: reduceMotion ? 0 : 0.22, ease: [0.22, 1, 0.36, 1] }}
              >
                <AdminUserManagement
                  token={token}
                  onUnauthorized={returnToLogin}
                />
              </motion.section>
              <motion.section
                className={`admin-space-page admin-agents-section ${activeAdminSpace === "agents" ? "is-active" : ""}`}
                id="admin-space-agents"
                aria-label="Agentes operativos"
                aria-hidden={activeAdminSpace !== "agents"}
                inert={activeAdminSpace !== "agents"}
                initial={false}
                animate={{
                  opacity: activeAdminSpace === "agents" ? 1 : 0,
                  x: activeAdminSpace === "agents" ? 0 : 12,
                }}
                transition={{ duration: reduceMotion ? 0 : 0.22, ease: [0.22, 1, 0.36, 1] }}
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
              </motion.section>
            </motion.div>
          </div>
        </motion.div>
      ) : (
        user.role === "directivo" ? (
          <motion.div
            className="director-workspace"
            initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] }}
          >
            <DirectorPanel branches={user.branches || []} />
            <div className="director-chat-widget">
              <AnimatePresence>
                {isDirectorChatOpen && (
                  <motion.section
                    className="director-chat-column"
                    id="director-chat-panel"
                    aria-label="Chat del directivo"
                    initial={{ opacity: 0, y: reduceMotion ? 0 : 18, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: reduceMotion ? 0 : 12, scale: 0.98 }}
                    transition={{ duration: reduceMotion ? 0 : 0.2, ease: [0.22, 1, 0.36, 1] }}
                  >
                    <button
                      className="director-chat-close"
                      type="button"
                      onClick={() => setIsDirectorChatOpen(false)}
                      aria-label="Cerrar chat"
                    >
                      <span aria-hidden="true">×</span>
                    </button>
                    <ChatPanel user={user} token={token} agentRole={user.role} />
                  </motion.section>
                )}
              </AnimatePresence>
              <div className={`director-chat-launcher ${isDirectorChatOpen ? "is-open" : ""} ${isDirectorTooltipVisible ? "is-hint-visible" : ""}`}>
                <span className="director-chat-tooltip" id="director-chat-tooltip" role="tooltip">
                  El asistente puede ayudarte
                </span>
                <motion.button
                  className="director-chat-toggle"
                  type="button"
                  onClick={() => setIsDirectorChatOpen((open) => !open)}
                  aria-expanded={isDirectorChatOpen}
                  aria-controls="director-chat-panel"
                  aria-label={isDirectorChatOpen ? "Cerrar chat" : "Abrir chat con el asistente"}
                  aria-describedby={!isDirectorChatOpen ? "director-chat-tooltip" : undefined}
                  whileHover={reduceMotion ? undefined : { y: -2, scale: 1.04 }}
                  whileTap={reduceMotion ? undefined : { scale: 0.96 }}
                >
                  {isDirectorChatOpen ? (
                    <span className="director-chat-toggle-close" aria-hidden="true">×</span>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path d="M5 18.5 3.8 21l4.4-1.1a9 9 0 1 0-3.2-1.4Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
                      <path d="M8 12h.01M12 12h.01M16 12h.01" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
                    </svg>
                  )}
                </motion.button>
              </div>
            </div>
          </motion.div>
        ) : (
          <motion.div
            className={`operational-workspace operational-workspace-${user.role}`}
            initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.26, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="operational-dashboard-column">
              {user.role === "ti" ? (
                <SystemStatusPanel />
              ) : user.role === "bodega" ? (
                <InventoryPanel token={token} branches={user.branches || []} />
              ) : user.role === "analista" ? (
                <AnalystPanel />
              ) : user.role === "gerente" ? (
                <ManagerPanel />
              ) : (
                <section className="role-dashboard">
                  <RoleHero kicker={profile.label} title={profile.name} description="Consulta al asistente para obtener información de las fuentes autorizadas." />
                </section>
              )}
            </div>
            <div className="operational-chat-column">
              <ChatPanel user={user} token={token} agentRole={user.role} />
            </div>
          </motion.div>
        )
      )}
      <aside className="transparency-banner" role="note">
        Estás interactuando con un asistente de IA. Las respuestas se basan en
        documentos oficiales.
      </aside>
    </main>
  );
}
