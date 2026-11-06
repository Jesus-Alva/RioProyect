"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { BRANCH_OPTIONS, formatBranchNames } from "../lib/branches.js";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const STATUS_LABELS = {
  received: "Recibida",
  in_progress: "En proceso",
  resolved: "Resuelta",
};

const CATEGORY_LABELS = {
  demora: "Demora",
  mala_atencion: "Mala atención",
  producto: "Producto",
  facturacion: "Facturación",
  sugerencia: "Sugerencia",
  otro: "Otro",
};

async function readResponse(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

export default function ComplaintInbox({
  token,
  branches,
  onUnauthorized,
}) {
  const [complaints, setComplaints] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingError, setLoadingError] = useState("");
  const [actionState, setActionState] = useState({ id: null, message: "" });
  const [updatingId, setUpdatingId] = useState(null);
  const requestInFlight = useRef(false);

  const loadComplaints = useCallback(async ({ background = false } = {}) => {
    if (requestInFlight.current) return;
    requestInFlight.current = true;
    if (!background) setIsLoading(true);
    setLoadingError("");
    try {
      const response = await fetch(
        `${BACKEND_URL.replace(/\/$/, "")}/api/complaints`,
        {
          cache: "no-store",
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      if (response.status === 401) {
        onUnauthorized?.();
        return;
      }
      const payload = await readResponse(response);
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "No se pudo consultar la bandeja de quejas.",
        );
      }
      setComplaints(Array.isArray(payload.items) ? payload.items : []);
    } catch (error) {
      setLoadingError(
        error instanceof TypeError
          ? "No se pudo conectar con el servicio de quejas."
          : error.message,
      );
    } finally {
      requestInFlight.current = false;
      if (!background) setIsLoading(false);
    }
  }, [onUnauthorized, token]);

  useEffect(() => {
    loadComplaints();
  }, [loadComplaints]);

  useEffect(() => {
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") {
        loadComplaints({ background: true });
      }
    };
    const intervalId = window.setInterval(refreshWhenVisible, 30_000);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [loadComplaints]);

  async function updateStatus(complaint, status) {
    setActionState({ id: complaint.id, message: "" });
    setUpdatingId(complaint.id);
    try {
      const response = await fetch(
        `${BACKEND_URL.replace(/\/$/, "")}/api/complaints/${complaint.id}`,
        {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ estado: status }),
        },
      );
      if (response.status === 401) {
        onUnauthorized?.();
        return;
      }
      const payload = await readResponse(response);
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "No se pudo actualizar el estado de la queja.",
        );
      }
      setComplaints((current) =>
        current.map((item) =>
          item.id === complaint.id ? { ...item, estado: payload.estado } : item,
        ),
      );
      setActionState({
        id: complaint.id,
        message: "Estado actualizado.",
      });
    } catch (error) {
      setActionState({
        id: complaint.id,
        message:
          error instanceof TypeError
            ? "No se pudo conectar con el servicio de quejas."
            : error.message,
      });
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <section className="complaint-inbox" aria-labelledby="complaint-inbox-title">
      <header className="complaint-inbox-heading">
        <div>
          <p className="role-action-eyebrow">Atención al cliente</p>
          <h3 id="complaint-inbox-title">Bandeja de Quejas</h3>
          <p>
            Sucursales visibles: {formatBranchNames(branches)}. La bandeja se
            actualiza automáticamente cada 30 segundos.
          </p>
        </div>
        <button
          className="button button-secondary"
          type="button"
          onClick={loadComplaints}
          disabled={isLoading}
        >
          {isLoading ? "Actualizando..." : "Actualizar"}
        </button>
      </header>

      {loadingError && (
        <p className="error-message" role="alert">
          {loadingError}
        </p>
      )}
      {isLoading ? (
        <p role="status">Cargando quejas...</p>
      ) : complaints.length ? (
        <ul className="complaint-list">
          {complaints.map((complaint) => {
            const branchLabel =
              BRANCH_OPTIONS.find(
                (branch) => branch.value === complaint.sucursal,
              )?.label || complaint.sucursal;
            return (
              <li className="complaint-card" key={complaint.id}>
                <header className="complaint-card-heading">
                  <div>
                    <span className="role-action-eyebrow">{branchLabel}</span>
                    <h4>{complaint.cliente_nombre}</h4>
                    <a href={`mailto:${complaint.cliente_email}`}>
                      {complaint.cliente_email}
                    </a>
                  </div>
                  <span className={`complaint-status is-${complaint.estado}`}>
                    {STATUS_LABELS[complaint.estado] || complaint.estado}
                  </span>
                </header>
                <dl className="complaint-summary">
                  <div>
                    <dt>Categoría</dt>
                    <dd>
                      {CATEGORY_LABELS[complaint.categoria] ||
                        (complaint.categoria
                          ? "Otra"
                          : "Pendiente de clasificación")}
                    </dd>
                  </div>
                  <div>
                    <dt>Recibida</dt>
                    <dd>
                      {complaint.fecha
                        ? new Date(complaint.fecha).toLocaleString("es-MX")
                        : "Fecha no disponible"}
                    </dd>
                  </div>
                </dl>
                {complaint.estado_analisis === "completed" ? (
                  <>
                    <p className="complaint-analysis">
                      <strong>Resumen de IA:</strong> {complaint.resumen_ia}
                    </p>
                    <p className="complaint-critical-point">
                      <strong>Punto crítico:</strong> {complaint.punto_critico}
                    </p>
                  </>
                ) : (
                  <p className="complaint-analysis-pending" role="status">
                    El análisis automático no estuvo disponible. Revisa el
                    mensaje original para dar seguimiento.
                  </p>
                )}
                <details className="complaint-original">
                  <summary>Ver mensaje original</summary>
                  <p>{complaint.mensaje}</p>
                </details>
                {complaint.estado !== "resolved" && (
                  <div className="complaint-actions">
                    {complaint.estado === "received" && (
                      <button
                        className="button button-secondary"
                        type="button"
                        onClick={() =>
                          updateStatus(complaint, "in_progress")
                        }
                        disabled={updatingId === complaint.id}
                      >
                        Marcar en proceso
                      </button>
                    )}
                    <button
                      className="button button-primary"
                      type="button"
                      onClick={() => updateStatus(complaint, "resolved")}
                      disabled={updatingId === complaint.id}
                    >
                      {updatingId === complaint.id
                        ? "Guardando..."
                        : "Marcar resuelta"}
                    </button>
                  </div>
                )}
                {actionState.id === complaint.id && actionState.message && (
                  <p
                    className={
                      actionState.message === "Estado actualizado."
                        ? "success-message"
                        : "error-message"
                    }
                    role="status"
                  >
                    {actionState.message}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="complaint-empty">
          No hay quejas ni sugerencias para las sucursales asignadas.
        </p>
      )}
      {branches.length === 0 && (
        <p className="complaint-empty">
          Tu cuenta no tiene sucursales asignadas.
        </p>
      )}
    </section>
  );
}
