"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { clearSession } from "../lib/authSession.js";
import { BRANCH_OPTIONS } from "../lib/branches.js";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const MAX_FILE_BYTES = 20 * 1024 * 1024;

function dateInputValue(value) {
  const match = String(value || "").match(/^\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : "";
}

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
  const [reviewActionState, setReviewActionState] = useState({
    kind: "",
    message: "",
  });
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [previewLoadingId, setPreviewLoadingId] = useState(null);
  const [reviewEdits, setReviewEdits] = useState({});
  const [resolvingReviewId, setResolvingReviewId] = useState(null);
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

  useEffect(
    () => () => {
      if (preview?.url) URL.revokeObjectURL(preview.url);
    },
    [preview],
  );

  useEffect(() => {
    if (!preview) return undefined;
    function closeOnEscape(event) {
      if (event.key === "Escape") setPreview(null);
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [preview]);

  async function showPreview(review) {
    setPreviewError("");
    setPreviewLoadingId(review.id);
    try {
      const response = await fetch(
        `${BACKEND_URL.replace(/\/$/, "")}/api/invoices/reviews/${review.id}/preview`,
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
      if (!response.ok) {
        const payload = await readResponse(response);
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "No se pudo cargar la vista previa.",
        );
      }
      const fileBlob = await response.blob();
      const url = URL.createObjectURL(fileBlob);
      setPreview({
        review,
        filename: review.filename,
        contentType: response.headers.get("content-type") || fileBlob.type,
        url,
      });
    } catch (error) {
      setPreviewError(
        error instanceof TypeError
          ? "No se pudo conectar con el servicio de facturas."
          : error.message,
      );
    } finally {
      setPreviewLoadingId(null);
    }
  }

  function getReviewData(review) {
    return reviewEdits[review.id] || initialReviewData(review);
  }

  function initialReviewData(review) {
    return {
      vendor_name: review.vendor_name || "",
      invoice_date: dateInputValue(review.invoice_date),
      invoice_total:
        review.invoice_total === null || review.invoice_total === undefined
          ? ""
          : String(review.invoice_total),
    };
  }

  function updateReviewData(review, field, value) {
    setReviewEdits((current) => ({
      ...current,
      [review.id]: {
        ...(current[review.id] || initialReviewData(review)),
        [field]: value,
      },
    }));
  }

  async function resolveReview(review, decision, confirmedData) {
    setReviewActionState({ kind: "", message: "" });
    setResolvingReviewId(review.id);
    const body = { decision };
    if (decision === "approve") {
      body.vendor_name = confirmedData.vendor_name.trim();
      body.invoice_date = confirmedData.invoice_date;
      body.invoice_total = Number(confirmedData.invoice_total);
    }
    try {
      const response = await fetch(
        `${BACKEND_URL.replace(/\/$/, "")}/api/invoices/reviews/${review.id}`,
        {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(body),
        },
      );
      const payload = await readResponse(response);
      if (response.status === 401) {
        clearSession();
        onUnauthorized?.();
        return;
      }
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "No se pudo resolver la factura.",
        );
      }
      setReviewActionState({
        kind: "success",
        message:
          decision === "approve"
            ? `${payload.filename}: confirmada e indexada en AI Search.`
            : `${payload.filename}: declinada.`,
      });
      setPreview(null);
      setReviewEdits((current) => {
        const next = { ...current };
        delete next[review.id];
        return next;
      });
      setRefreshVersion((version) => version + 1);
    } catch (error) {
      setReviewActionState({
        kind: "error",
        message:
          error instanceof TypeError
            ? "No se pudo conectar con el servicio de facturas."
            : error.message,
      });
    } finally {
      setResolvingReviewId(null);
    }
  }

  async function submitReview(event) {
    event.preventDefault();
    if (preview?.review) {
      await resolveReview(
        preview.review,
        "approve",
        getReviewData(preview.review),
      );
    }
  }

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
      {reviewActionState.message && (
        <p
          className={`invoice-upload-status is-${reviewActionState.kind}`}
          role="status"
          aria-live="polite"
        >
          {reviewActionState.message}
        </p>
      )}
      {previewError && <p className="error-message">{previewError}</p>}
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
              <div className="invoice-review-actions">
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => showPreview(review)}
                  disabled={
                    previewLoadingId === review.id ||
                    resolvingReviewId === review.id
                  }
                >
                  {previewLoadingId === review.id
                    ? "Cargando vista previa..."
                    : "Revisar y editar"}
                </button>
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => resolveReview(review, "decline")}
                  disabled={resolvingReviewId === review.id}
                >
                  Declinar
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="invoice-review-empty">No hay facturas pendientes de revisión.</p>
      )}
      {preview && (
        <div
          className="invoice-preview-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setPreview(null);
          }}
        >
          <section
            className="invoice-preview-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="invoice-preview-title"
          >
            <header className="invoice-preview-heading">
              <h3 id="invoice-preview-title">{preview.filename}</h3>
              <button
                className="button button-secondary"
                type="button"
                onClick={() => setPreview(null)}
                autoFocus
              >
                Cerrar
              </button>
            </header>
            <div className="invoice-review-editor">
              <div className="invoice-preview-document">
                {preview.contentType === "application/pdf" ? (
                  <iframe
                    className="invoice-preview-frame"
                    src={preview.url}
                    title={`Vista previa de ${preview.filename}`}
                  />
                ) : (
                  <img
                    className="invoice-preview-image"
                    src={preview.url}
                    alt={`Vista previa de ${preview.filename}`}
                  />
                )}
              </div>
              <form className="invoice-review-form" onSubmit={submitReview}>
                <p>
                  Compara los datos extraídos con la factura. Puedes corregirlos
                  antes de confirmar.
                </p>
                {reviewActionState.message && (
                  <p
                    className={`invoice-upload-status is-${reviewActionState.kind}`}
                    role="alert"
                  >
                    {reviewActionState.message}
                  </p>
                )}
                <label>
                  Proveedor
                  <input
                    type="text"
                    maxLength={255}
                    value={getReviewData(preview.review).vendor_name}
                    onChange={(event) =>
                      updateReviewData(
                        preview.review,
                        "vendor_name",
                        event.target.value,
                      )
                    }
                    required
                  />
                </label>
                <label>
                  Fecha de factura
                  <input
                    type="date"
                    value={getReviewData(preview.review).invoice_date}
                    onChange={(event) =>
                      updateReviewData(
                        preview.review,
                        "invoice_date",
                        event.target.value,
                      )
                    }
                    required
                  />
                </label>
                <label>
                  Total (MXN)
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={getReviewData(preview.review).invoice_total}
                    onChange={(event) =>
                      updateReviewData(
                        preview.review,
                        "invoice_total",
                        event.target.value,
                      )
                    }
                    required
                  />
                </label>
                <button
                  className="button button-primary"
                  type="submit"
                  disabled={resolvingReviewId === preview.review.id}
                >
                  {resolvingReviewId === preview.review.id
                    ? "Guardando..."
                    : "Confirmar datos y guardar"}
                </button>
              </form>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
