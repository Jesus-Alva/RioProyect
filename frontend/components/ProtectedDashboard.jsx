"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

import AdminSidebar from "./AdminSidebar.jsx";
import AdminUserManagement from "./AdminUserManagement.jsx";
import BranchMultiSelect from "./BranchMultiSelect.jsx";
import ChatPanel from "./ChatPanel.jsx";
import InvoiceWorkspace from "./InvoiceWorkspace.jsx";
import { isSupportedRole, OPERATIONAL_ROLES, ROLE_PROFILES } from "../lib/authRoles.js";
import { clearSession, readSession, saveSession } from "../lib/authSession.js";
import { BRANCH_OPTIONS, formatBranchNames } from "../lib/branches.js";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const LOW_STOCK_THRESHOLD = 15;

function parseInventoryQuantity(value) {
  if (value === null || value === undefined || value === "") return null;
  const quantity = Number(value);
  return Number.isFinite(quantity) ? quantity : null;
}

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
  const [isInventoryFormOpen, setIsInventoryFormOpen] = useState(false);
  const [productName, setProductName] = useState("");
  const [quantityToAdd, setQuantityToAdd] = useState("1");
  const [targetBranch, setTargetBranch] = useState(branches[0] || "");
  const [isSavingInventory, setIsSavingInventory] = useState(false);
  const [inventorySaveError, setInventorySaveError] = useState("");
  const [inventorySaveNotice, setInventorySaveNotice] = useState("");

  async function handleInventorySubmit(event) {
    event.preventDefault();
    setInventorySaveError("");
    setInventorySaveNotice("");
    setIsSavingInventory(true);
    try {
      const response = await fetch(`${BACKEND_URL.replace(/\/$/, "")}/api/inventory`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          producto: productName,
          cantidad: Number(quantityToAdd),
          branch: targetBranch,
        }),
      });
      let payload = {};
      try {
        payload = await response.json();
      } catch {
        throw new Error("El servidor devolvió una respuesta inválida.");
      }
      if (response.status === 401) {
        clearSession();
        window.location.replace("/login");
        return;
      }
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "No se pudo guardar el producto.",
        );
      }
      const branchLabel = BRANCH_OPTIONS.find((option) => option.value === payload.branch)?.label || payload.branch;
      setInventorySaveNotice(
        `${payload.operation === "increased" ? "Stock actualizado" : "Producto registrado"}: ${payload.producto}. Total en ${branchLabel}: ${Number(payload.cantidad_total).toLocaleString("es-MX")} unidades.`,
      );
      setProductName("");
      setQuantityToAdd("1");
      setReloadVersion((version) => version + 1);
    } catch (requestError) {
      setInventorySaveError(
        requestError instanceof TypeError
          ? "No se pudo conectar con el servicio de inventario."
          : requestError.message,
      );
    } finally {
      setIsSavingInventory(false);
    }
  }

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
    return total + (parseInventoryQuantity(item.cantidad) ?? 0);
  }, 0);
  const lowStockCount = filteredInventory.filter((item) => {
    const quantity = parseInventoryQuantity(item.cantidad);
    return quantity !== null && quantity <= LOW_STOCK_THRESHOLD;
  }).length;
  const inventoryGroups = branches
    .map((branch) => ({
      branch,
      items: filteredInventory
        .filter((item) => item.branch === branch)
        .sort((first, second) => String(first.producto).localeCompare(String(second.producto), "es-MX")),
    }))
    .filter((group) => group.items.length > 0);

  return (
    <section className="role-dashboard role-dashboard-bodega" aria-labelledby="inventory-title">
      <RoleHero
        kicker="Operación de bodega"
        title="Inventario disponible"
        titleId="inventory-title"
        description={`Consulta existencias autorizadas para: ${formatBranchNames(branches)}.`}
        badge="Datos de inventario"
      />
      <div className="role-kpi-grid">
        <article className="director-kpi-card director-kpi-primary">
          <span className="director-kpi-label">Productos encontrados</span>
          <strong>{isLoading ? "…" : filteredInventory.length}</strong>
          <span className="director-kpi-footnote">En la búsqueda actual</span>
        </article>
        <article className={`director-kpi-card ${!isLoading && lowStockCount ? "director-kpi-warning" : ""}`}>
          <span className="director-kpi-label">Stock bajo</span>
          <strong>{isLoading ? "…" : lowStockCount}</strong>
          <span className="director-kpi-footnote">≤ {LOW_STOCK_THRESHOLD} unidades</span>
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
            <h3 id="inventory-results-title">Stock por sucursal</h3>
          </div>
          <div className="inventory-header-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => setIsInventoryFormOpen((open) => !open)}
              disabled={!branches.length || isSavingInventory}
              aria-expanded={isInventoryFormOpen}
              aria-controls="inventory-add-form"
            >
              {isInventoryFormOpen ? "Cerrar formulario" : "+ Agregar stock"}
            </button>
            <button className="button button-secondary" type="button" onClick={() => setReloadVersion((version) => version + 1)} disabled={isLoading || isSavingInventory}>
              {isLoading ? "Actualizando…" : "Actualizar"}
            </button>
          </div>
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
        <AnimatePresence initial={false}>
          {isInventoryFormOpen && (
            <motion.form
              className="inventory-add-form"
              id="inventory-add-form"
              onSubmit={handleInventorySubmit}
              initial={{ opacity: 0, height: 0, y: reduceMotion ? 0 : -6 }}
              animate={{ opacity: 1, height: "auto", y: 0 }}
              exit={{ opacity: 0, height: 0, y: reduceMotion ? 0 : -6 }}
              transition={{ duration: reduceMotion ? 0 : 0.2 }}
            >
              <div className="inventory-form-heading">
                <div>
                  <p className="director-kicker">Entrada de inventario</p>
                  <h4>Registrar producto o agregar unidades</h4>
                </div>
                <p>Si el producto ya existe en esa sucursal, la cantidad se sumará al stock actual.</p>
              </div>
              <div className="inventory-form-fields">
                <label>
                  Producto
                  <input
                    type="text"
                    value={productName}
                    onChange={(event) => setProductName(event.target.value)}
                    maxLength={120}
                    placeholder="Ej. Agua natural 1.5 L"
                    required
                    disabled={isSavingInventory}
                  />
                </label>
                <label>
                  Cantidad a agregar
                  <input
                    type="number"
                    value={quantityToAdd}
                    onChange={(event) => setQuantityToAdd(event.target.value)}
                    min="1"
                    max="1000000"
                    step="1"
                    required
                    disabled={isSavingInventory}
                  />
                </label>
                <label>
                  Sucursal
                  <select
                    value={targetBranch}
                    onChange={(event) => setTargetBranch(event.target.value)}
                    required
                    disabled={isSavingInventory || !branches.length}
                  >
                    {BRANCH_OPTIONS.filter((option) => branches.includes(option.value)).map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
              </div>
              {inventorySaveError && <p className="error-message" role="alert">{inventorySaveError}</p>}
              {inventorySaveNotice && <p className="success-message" role="status">{inventorySaveNotice}</p>}
              <div className="inventory-form-footer">
                <span>El cambio se guardará en el inventario de Azure.</span>
                <button className="button button-primary" type="submit" disabled={isSavingInventory || !targetBranch}>
                  {isSavingInventory ? "Guardando…" : "Guardar inventario"}
                </button>
              </div>
            </motion.form>
          )}
        </AnimatePresence>
        {isLoading ? (
          <p className="role-data-feedback" role="status">Cargando inventario…</p>
        ) : error ? (
          <p className="error-message role-data-feedback" role="alert">{error}</p>
        ) : inventoryGroups.length ? (
          <div className="inventory-branch-groups">
            {inventoryGroups.map(({ branch, items }) => (
              <section className="inventory-branch-group" key={branch} aria-label={`Stock de ${BRANCH_OPTIONS.find((option) => option.value === branch)?.label || branch}`}>
                <header className="inventory-branch-heading">
                  <div className="inventory-branch-title">
                    <span className="inventory-branch-icon" aria-hidden="true">⌖</span>
                    <h4>{BRANCH_OPTIONS.find((option) => option.value === branch)?.label || branch}</h4>
                  </div>
                  <span className="inventory-branch-count">
                    {items.length} {items.length === 1 ? "producto" : "productos"}
                  </span>
                </header>
                <ul className="inventory-results">
                  {items.map((item, index) => {
                    const quantity = parseInventoryQuantity(item.cantidad);
                    const hasQuantity = quantity !== null;
                    const isOutOfStock = hasQuantity && quantity <= 0;
                    const isLowStock = hasQuantity && quantity > 0 && quantity <= LOW_STOCK_THRESHOLD;
                    return (
                      <motion.li
                        className={`inventory-stock-item ${isOutOfStock ? "is-out-of-stock" : isLowStock ? "is-low-stock" : ""}`}
                        key={`${item.producto}-${branch}-${index}`}
                        layout
                        initial={{ opacity: reduceMotion ? 1 : 0 }}
                        animate={{ opacity: 1 }}
                      >
                        <span className="inventory-product-mark" aria-hidden="true">
                          {String(item.producto || "?").slice(0, 1).toLocaleUpperCase("es-MX")}
                        </span>
                        <div className="inventory-item-copy">
                          <strong>{item.producto}</strong>
                        </div>
                        <span className="inventory-quantity">
                          <strong>{hasQuantity ? quantity.toLocaleString("es-MX") : "—"}</strong>
                          <small>unidades</small>
                        </span>
                        <span className={`inventory-stock-badge ${isOutOfStock ? "is-empty" : isLowStock ? "is-low" : "is-available"}`}>
                          {isOutOfStock ? "Agotado" : isLowStock ? "Stock bajo" : hasQuantity ? "Disponible" : "Sin dato"}
                        </span>
                      </motion.li>
                    );
                  })}
                </ul>
              </section>
            ))}
          </div>
        ) : (
          <p className="role-data-feedback">
            {inventory.length
              ? "No hay coincidencias para esa búsqueda."
              : "No hay productos de inventario disponibles para esta sucursal."}
          </p>
        )}
      </section>
      <p className="role-data-note">Stock bajo: {LOW_STOCK_THRESHOLD} unidades o menos. Los resultados se consultan en el índice en tiempo real y permanecen limitados a las sucursales autorizadas.</p>
    </section>
  );
}

function DirectorPanel({ token, branches, onUnauthorized }) {
  const reduceMotion = useReducedMotion();
  const [selectedBranches, setSelectedBranches] = useState(branches);
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadVersion, setReloadVersion] = useState(0);
  const availableBranches = BRANCH_OPTIONS.filter(({ value }) =>
    branches.includes(value),
  );
  useEffect(() => {
    setSelectedBranches((current) =>
      current.filter((branch) => branches.includes(branch)),
    );
  }, [branches]);

  useEffect(() => {
    let active = true;
    async function loadReport() {
      setIsLoading(true);
      setError("");
      try {
        const response = await fetch(
          `${BACKEND_URL.replace(/\/$/, "")}/api/director/sales-report`,
          {
            cache: "no-store",
            headers: { Authorization: `Bearer ${token}` },
          },
        );
        if (response.status === 401) {
          clearSession();
          onUnauthorized?.();
          return;
        }
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(
            typeof payload.detail === "string"
              ? payload.detail
              : "No se pudo consultar el reporte de facturas.",
          );
        }
        if (active) setReport(payload);
      } catch (requestError) {
        if (active) {
          setError(
            requestError instanceof TypeError
              ? "No se pudo conectar con el servicio de reportes."
              : requestError.message,
          );
        }
      } finally {
        if (active) setIsLoading(false);
      }
    }
    loadReport();
    return () => {
      active = false;
    };
  }, [onUnauthorized, reloadVersion, token]);

  const rows = (report?.branches || [])
    .filter(
      (row) =>
        branches.includes(row.branch) &&
        selectedBranches.includes(row.branch),
    )
    .map((row) => ({
      ...row,
      city:
        BRANCH_OPTIONS.find((option) => option.value === row.branch)?.label ||
        row.branch,
    }))
    .sort((first, second) => second.total - first.total);
  const totalSales = rows.reduce((total, row) => total + row.total, 0);
  const invoiceCount = rows.reduce(
    (total, row) => total + row.invoice_count,
    0,
  );
  const invoicesWithTotal = rows.reduce(
    (total, row) => total + row.invoices_with_total,
    0,
  );
  const topBranch = rows.find((row) => row.invoices_with_total > 0);
  const maxSales = topBranch?.total || 1;
  const formatSales = (amount) =>
    new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency: report?.currency || "MXN",
    }).format(amount);

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
          <p>Importes y conteos agregados a partir de las facturas procesadas en las sucursales autorizadas.</p>
        </div>
        <button
          className="button button-secondary"
          type="button"
          onClick={() => setReloadVersion((version) => version + 1)}
          disabled={isLoading}
        >
          {isLoading ? "Actualizando..." : "Actualizar reporte"}
        </button>
      </motion.header>

      <div className="director-filter-panel">
        <BranchMultiSelect
          id="director-branches"
          label="Sucursales del reporte"
          description="Selecciona una o más sucursales autorizadas para comparar los importes de sus facturas."
          branches={availableBranches}
          selectedBranches={selectedBranches}
          onChange={setSelectedBranches}
          compact
        />
      </div>

      {error && <p className="error-message" role="alert">{error}</p>}
      {isLoading ? (
        <div className="director-empty-state" role="status">
          Consultando facturas procesadas...
        </div>
      ) : rows.length === 0 ? (
        <div className="director-empty-state" role="status">
          Selecciona al menos una sucursal autorizada para ver el resumen.
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
              <span className="director-kpi-label">Importe facturado</span>
              <strong>{formatSales(totalSales)}</strong>
              <span className="director-kpi-footnote">
                {invoicesWithTotal} de {invoiceCount} facturas con importe identificado
              </span>
            </motion.article>
            <motion.article
              className="director-kpi-card"
              layout
              initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.24, delay: reduceMotion ? 0 : 0.1 }}
            >
              <span className="director-kpi-label">Facturas procesadas</span>
              <strong>{invoiceCount.toLocaleString("es-MX")}</strong>
              <span className="director-kpi-footnote">
                {rows.length} sucursales seleccionadas
              </span>
            </motion.article>
            <motion.article
              className="director-kpi-card"
              layout
              initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.24, delay: reduceMotion ? 0 : 0.16 }}
            >
              <span className="director-kpi-label">Mayor venta</span>
              <strong>{topBranch?.city || "Sin datos"}</strong>
              <span className="director-kpi-footnote">
                {topBranch ? formatSales(topBranch.total) : "Sin importes identificados"}
              </span>
            </motion.article>
          </div>

          <div className="director-insights-grid">
            <section className="director-performance-card" aria-labelledby="director-performance-title">
              <div className="director-section-heading">
                <div>
                  <p className="director-kicker">Comparativo</p>
                  <h3 id="director-performance-title">Ventas por sucursal</h3>
                </div>
                <span className="director-period-label">Histórico · MXN</span>
              </div>
              <ol className="director-performance-list">
                {rows.map(({ branch, city, total, invoice_count, invoices_with_total }, index) => (
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
                      <strong>{formatSales(total)}</strong>
                    </div>
                    <div
                      className="director-bar-track"
                      role="img"
                      aria-label={`${city}: ${formatSales(total)} de ${invoices_with_total} facturas con importe`}
                    >
                      <motion.span
                        className="director-bar-fill"
                        initial={{ width: 0 }}
                        animate={{ width: `${(total / maxSales) * 100}%` }}
                        transition={{ duration: reduceMotion ? 0 : 0.55, delay: reduceMotion ? 0 : 0.12 + index * 0.05 }}
                      />
                    </div>
                    <span className="director-kpi-footnote">
                      {invoice_count} facturas procesadas · {invoices_with_total} con importe
                    </span>
                  </motion.li>
                ))}
              </ol>
            </section>

            {topBranch && (
              <aside className="director-highlights-card" aria-label="Hallazgo destacado">
                <span className="director-highlight-icon" aria-hidden="true">↗</span>
                <p className="director-kicker">Mayor importe facturado</p>
                <h3>{topBranch.city}</h3>
                <strong>{formatSales(topBranch.total)}</strong>
                <p>Importe sumado desde {topBranch.invoices_with_total} facturas con total identificado.</p>
              </aside>
            )}
          </div>
          <p className="director-data-note">
            Suma histórica de facturas indexadas y aprobadas. Es importe bruto facturado, no ventas netas; las facturas pendientes o declinadas se excluyen.
          </p>
        </>
      )}
    </section>
  );
}

function AnalystPanel({ token, branches, onUnauthorized }) {
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
      <InvoiceWorkspace
        token={token}
        branches={branches}
        onUnauthorized={onUnauthorized}
      />
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

  const returnToLogin = useCallback(() => {
    clearSession();
    router.replace("/login");
  }, [router]);

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
                className={`admin-space-page ${activeAdminSpace === "reviews" ? "is-active" : ""}`}
                id="admin-space-reviews"
                aria-label="Revisión de facturas"
                aria-hidden={activeAdminSpace !== "reviews"}
                inert={activeAdminSpace !== "reviews"}
                initial={false}
                animate={{
                  opacity: activeAdminSpace === "reviews" ? 1 : 0,
                  x: activeAdminSpace === "reviews" ? 0 : -12,
                }}
                transition={{ duration: reduceMotion ? 0 : 0.22, ease: [0.22, 1, 0.36, 1] }}
              >
                <InvoiceWorkspace
                  token={token}
                  branches={user.branches || []}
                  onUnauthorized={returnToLogin}
                  allowUpload={false}
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
            <DirectorPanel
              token={token}
              branches={user.branches || []}
              onUnauthorized={returnToLogin}
            />
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
                <AnalystPanel
                  token={token}
                  branches={user.branches || []}
                  onUnauthorized={returnToLogin}
                />
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
