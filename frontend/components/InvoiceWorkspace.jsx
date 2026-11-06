"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { clearSession } from "../lib/authSession.js";
import { BRANCH_OPTIONS } from "../lib/branches.js";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const MAX_FILE_BYTES = 20 * 1024 * 1024;

async function readResponse(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

export default function InvoiceWorkspace({
  token,
  branches,
  onUnauthorized,
  allowUpload = true,
}) {
  const [branch, setBranch] = useState(branches[0] || "");
  const [file, setFile] = useState(null);
  const [uploadState, setUploadState] = useState({ kind: "", message: "" });
  const [reviews, setReviews] = useState([]);
  const [isLoadingReviews, setIsLoadingReviews] = useState(true);
  const [reviewError, setReviewError] = useState("");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const formRef = useRef(null);
  const allowedBranches = useMemo(
    () => BRANCH_OPTIONS.filter((option) => branches.includes(option.value)),
    [branches],
  );

  useEffect(() => {
    if (!branches.includes(branch)) setBranch(branches[0] || "");
  }, [branch, branches]);

  const loadReviews = useCallback(async () => {
    setIsLoadingReviews(true);
    setReviewError("");
    try {
      const response = await fetch(
        `${BACKEND_URL.replace(/\/$/, "")}/api/invoices/reviews`,
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
      const payload = await readResponse(response);
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "No se pudo consultar la bandeja de revisión.",
        );
      }
      setReviews(Array.isArray(payload.items) ? payload.items : []);
    } catch (error) {
      setReviewError(
        error instanceof TypeError
          ? "No se pudo conectar con el servicio de facturas."
          : error.message,
      );
    } finally {
      setIsLoadingReviews(false);
    }
  }, [onUnauthorized, token]);

  useEffect(() => {
    loadReviews();
  }, [loadReviews, refreshVersion]);

  async function submitInvoice(event) {
    event.preventDefault();
    if (!file || !branch) {
      setUploadState({
        kind: "error",
        message: "Selecciona un archivo y una sucursal autorizada.",
      });
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setUploadState({
        kind: "error",
        message: "El archivo no puede superar 20 MB.",
      });
      return;
    }

    setUploadState({ kind: "processing", message: "Procesando..." });
    const body = new FormData();
    body.append("file", file);
    body.append("branch", branch);

    try {
      const response = await fetch(
        `${BACKEND_URL.replace(/\/$/, "")}/api/invoices/upload`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body,
        },
      );
      const payload = await readResponse(response);
      if (response.status === 401) {
        clearSession();
        onUnauthorized?.();
        return;
      }
      if (response.status === 201) {
        setUploadState({
          kind: "success",
          message: `Factura guardada con éxito: ${payload.filename || file.name}`,
        });
        setFile(null);
        formRef.current?.reset();
        setRefreshVersion((version) => version + 1);
        return;
      }
      if (response.status === 202) {
        setUploadState({
          kind: "review",
          message: `Requiere revisión manual: ${payload.filename || file.name}`,
        });
        setFile(null);
        formRef.current?.reset();
        setRefreshVersion((version) => version + 1);
        return;
      }
      if (response.status === 409) {
        setUploadState({
          kind: "error",
          message: "Factura duplicada.",
        });
        return;
      }
      throw new Error(
        typeof payload.detail === "string"
          ? payload.detail
          : "No se pudo procesar la factura.",
      );
    } catch (error) {
      setUploadState({
        kind: "error",
        message:
          error instanceof TypeError
            ? "No se pudo conectar con el servicio de facturas."
            : error.message,
      });
    }
  }

  return (
    <section className="invoice-workspace" aria-labelledby="invoice-workspace-title">
      <header className="invoice-workspace-heading">
        <div>
          <p className="role-action-eyebrow">Bandeja documental</p>
          <h3 id="invoice-workspace-title">Facturas para revisión</h3>
          <p>Los documentos con datos inciertos o coincidencias posibles esperan revisión humana.</p>
        </div>
        <button
          className="button button-secondary"
          type="button"
          onClick={() => setRefreshVersion((version) => version + 1)}
          disabled={isLoadingReviews}
        >
          {isLoadingReviews ? "Actualizando..." : "Actualizar"}
        </button>
      </header>

      {allowUpload && (
        <form ref={formRef} className="invoice-upload-form" onSubmit={submitInvoice}>
          <label>
            Sucursal de la factura
            <select
              className="role-search-input"
              value={branch}
              onChange={(event) => setBranch(event.target.value)}
              required
              disabled={!allowedBranches.length}
            >
              {allowedBranches.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Archivo PDF o imagen (máximo 20 MB)
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,application/pdf,image/png,image/jpeg,image/tiff,image/bmp"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
              required
            />
          </label>
          {file && (
            <p className="invoice-file-name">
              {file.name} · {(file.size / (1024 * 1024)).toFixed(2)} MB
            </p>
          )}
          <button
            className="button button-primary"
            type="submit"
            disabled={!allowedBranches.length || uploadState.kind === "processing"}
          >
            {uploadState.kind === "processing" ? "Procesando..." : "Subir factura"}
          </button>
          {uploadState.message && (
            <p
              className={`invoice-upload-status is-${uploadState.kind}`}
              role="status"
              aria-live="polite"
            >
              {uploadState.message}
            </p>
          )}
        </form>
      )}

      {reviewError && <p className="error-message">{reviewError}</p>}
      {isLoadingReviews ? (
        <p role="status">Cargando revisiones...</p>
      ) : reviews.length ? (
        <ul className="invoice-review-list">
          {reviews.map((review) => (
            <li className="invoice-review-card" key={review.id}>
              <div className="invoice-review-title">
                <strong>{review.filename}</strong>
                <span>
                  {BRANCH_OPTIONS.find((option) => option.value === review.branch)?.label ||
                    review.branch}
                </span>
              </div>
              {review.original_filename &&
                review.original_filename !== review.filename && (
                  <p className="invoice-original-name">
                    Archivo recibido: {review.original_filename}
                  </p>
                )}
              <dl>
                <div>
                  <dt>Proveedor</dt>
                  <dd>{review.vendor_name || "No identificado"}</dd>
                </div>
                <div>
                  <dt>Fecha</dt>
                  <dd>{review.invoice_date || "No identificada"}</dd>
                </div>
                <div>
                  <dt>Total</dt>
                  <dd>
                    {Number.isFinite(Number(review.invoice_total))
                      ? Number(review.invoice_total).toLocaleString("es-MX", {
                          style: "currency",
                          currency: "MXN",
                        })
                      : "No identificado"}
                  </dd>
                </div>
              </dl>
              <ul className="invoice-review-reasons">
                {review.reasons.map((reason, index) => (
                  <li key={`${review.id}-${index}`}>{reason}</li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      ) : (
        <p className="invoice-review-empty">No hay facturas pendientes de revisión.</p>
      )}
    </section>
  );
}
