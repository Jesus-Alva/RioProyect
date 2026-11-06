"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

import { OPERATIONAL_ROLES, ROLE_PROFILES } from "../../lib/authRoles.js";
import { BRANCH_OPTIONS } from "../../lib/branches.js";
import { readSession, saveSession } from "../../lib/authSession.js";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

async function submitAuthRequest(path, body) {
  let response;
  try {
    response = await fetch(`${BACKEND_URL.replace(/\/$/, "")}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("No se pudo conectar con el servidor de autenticación.");
  }

  let payload = {};
  try {
    payload = await response.json();
  } catch {
    throw new Error("El servidor de autenticación devolvió una respuesta inválida.");
  }
  if (!response.ok) {
    const detail = payload.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : "Revisa los datos e inténtalo de nuevo.",
    );
  }
  return payload;
}

async function submitComplaintRequest(body) {
  let response;
  try {
    response = await fetch(
      `${BACKEND_URL.replace(/\/$/, "")}/api/complaints`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
  } catch {
    throw new Error("No se pudo conectar con el servicio de quejas.");
  }

  let payload = {};
  try {
    payload = await response.json();
  } catch {
    throw new Error("El servicio de quejas devolvió una respuesta inválida.");
  }
  if (!response.ok) {
    const detail = payload.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : "Revisa los datos de la queja e inténtalo de nuevo.",
    );
  }
  return payload;
}

export default function LoginPage() {
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [requestedRole, setRequestedRole] = useState(OPERATIONAL_ROLES[0]);
  const [requestedBranch, setRequestedBranch] = useState("");
  const [complaintName, setComplaintName] = useState("");
  const [complaintEmail, setComplaintEmail] = useState("");
  const [complaintBranch, setComplaintBranch] = useState("");
  const [complaintMessage, setComplaintMessage] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (readSession()) router.replace("/dashboard");
  }, [router]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setNotice("");

    if (mode === "complaint") {
      setIsSubmitting(true);
      try {
        const result = await submitComplaintRequest({
          nombre: complaintName,
          correo: complaintEmail,
          sucursal: complaintBranch,
          mensaje: complaintMessage,
        });
        setNotice(result.detail);
        setComplaintName("");
        setComplaintEmail("");
        setComplaintBranch("");
        setComplaintMessage("");
      } catch (requestError) {
        setError(requestError.message);
      } finally {
        setIsSubmitting(false);
      }
      return;
    }

    if (mode === "register") {
      if (!/\p{Lu}/u.test(password)) {
        setError("La contraseña debe incluir al menos una letra mayúscula.");
        return;
      }
      if (!/[0-9]/.test(password)) {
        setError("La contraseña debe incluir al menos un número.");
        return;
      }
      if (!/[^\p{L}\p{N}\s]/u.test(password)) {
        setError("La contraseña debe incluir al menos un carácter especial.");
        return;
      }
    }

    if (mode === "register" && password !== confirmation) {
      setError("Las contraseñas no coinciden.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (mode === "register") {
        const result = await submitAuthRequest("/api/auth/register", {
          username,
          email,
          password,
          role: requestedRole,
          branch: requestedBranch,
        });
        setPassword("");
        setConfirmation("");
        setUsername("");
        setShowPassword(false);
        setShowConfirmation(false);
        setMode("login");
        setNotice(result.message);
        return;
      }

      const result = await submitAuthRequest("/api/auth/login", {
        email,
        password,
      });
      saveSession(result.access_token, result.user);
      router.replace("/dashboard");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  function changeMode(nextMode) {
    setMode(nextMode);
    setShowPassword(false);
    setShowConfirmation(false);
    setError("");
    setNotice("");
  }

  const isRegistering = mode === "register";
  const isComplaintMode = mode === "complaint";
  const passwordLengthIsValid = password.length >= 12 && password.length <= 128;
  const passwordHasUppercase = /\p{Lu}/u.test(password);
  const passwordHasNumber = /[0-9]/.test(password);
  const passwordHasSpecial = /[^\p{L}\p{N}\s]/u.test(password);
  const passwordsMatch = password.length > 0 && password === confirmation;
  return (
    <main className="auth-page">
      <motion.section
        className="auth-card"
        aria-labelledby="auth-title"
        layout
        initial={{ opacity: 0, y: reduceMotion ? 0 : 18, scale: reduceMotion ? 1 : 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{
          opacity: { duration: reduceMotion ? 0 : 0.28 },
          y: { duration: reduceMotion ? 0 : 0.38, ease: [0.22, 1, 0.36, 1] },
          scale: { duration: reduceMotion ? 0 : 0.38, ease: [0.22, 1, 0.36, 1] },
          layout: { duration: reduceMotion ? 0 : 0.3, ease: [0.22, 1, 0.36, 1] },
        }}
      >
        <div className="brand-logo-frame auth-brand-logo">
          <Image
            src="/rio-claro-logo.png"
            alt="Distribuidora Río Claro"
            fill
            priority
            sizes="(max-width: 480px) 144px, 176px"
            className="brand-logo-image"
          />
        </div>
        <AnimatePresence mode="wait" initial={false}>
          <motion.h1
            id="auth-title"
            key={mode}
            initial={{ opacity: 0, y: reduceMotion ? 0 : 7 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: reduceMotion ? 0 : -5 }}
            transition={{ duration: reduceMotion ? 0 : 0.18 }}
          >
            {isComplaintMode
              ? "Quejas y sugerencias"
              : isRegistering
                ? "Solicitar una cuenta"
                : "Inicia sesión"}
          </motion.h1>
        </AnimatePresence>
        <div className="auth-tabs" role="tablist" aria-label="Acceso">
          <button
            className={`button ${mode === "login" ? "button-primary" : "button-secondary"}`}
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            onClick={() => changeMode("login")}
          >
            Iniciar sesión
          </button>
          <button
            className={`button ${isRegistering ? "button-primary" : "button-secondary"}`}
            type="button"
            role="tab"
            aria-selected={isRegistering}
            onClick={() => changeMode("register")}
          >
            Registrarse
          </button>
        </div>
        <button
          className="button button-secondary auth-client-link"
          type="button"
          aria-pressed={isComplaintMode}
          onClick={() => changeMode(isComplaintMode ? "login" : "complaint")}
        >
          Soy Cliente - Levantar Queja
        </button>
        <AnimatePresence initial={false}>
          {isRegistering && (
            <motion.p
              key="registration-intro"
              initial={{ opacity: 0, height: 0, y: reduceMotion ? 0 : 6 }}
              animate={{ opacity: 1, height: "auto", y: 0 }}
              exit={{ opacity: 0, height: 0, y: reduceMotion ? 0 : -4 }}
              transition={{ duration: reduceMotion ? 0 : 0.2 }}
              style={{ overflow: "hidden" }}
            >
              Elige el perfil que solicitas. Un administrador debe aprobarlo
              antes de habilitar el acceso.
            </motion.p>
          )}
        </AnimatePresence>
        {isComplaintMode && (
          <p className="auth-complaint-intro">
            Comparte lo ocurrido. El equipo de Gerencia dará seguimiento a tu
            mensaje.
          </p>
        )}
        {notice && (
          <p className="success-message" role="status">
            {notice}
          </p>
        )}
        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
        {isComplaintMode ? (
          <form
            className="auth-form complaint-public-form"
            onSubmit={handleSubmit}
          >
            <label htmlFor="complaint-name">Nombre</label>
            <input
              id="complaint-name"
              name="nombre"
              type="text"
              autoComplete="name"
              value={complaintName}
              onChange={(event) => setComplaintName(event.target.value)}
              minLength={1}
              maxLength={120}
              required
            />
            <label htmlFor="complaint-email">Correo electrónico</label>
            <input
              id="complaint-email"
              name="correo"
              type="email"
              autoComplete="email"
              value={complaintEmail}
              onChange={(event) => setComplaintEmail(event.target.value)}
              maxLength={254}
              required
            />
            <label htmlFor="complaint-branch">Sucursal</label>
            <select
              id="complaint-branch"
              name="sucursal"
              value={complaintBranch}
              onChange={(event) => setComplaintBranch(event.target.value)}
              required
            >
              <option value="" disabled>
                Selecciona una sucursal
              </option>
              {BRANCH_OPTIONS.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <label htmlFor="complaint-message">Mensaje</label>
            <textarea
              id="complaint-message"
              name="mensaje"
              value={complaintMessage}
              onChange={(event) => setComplaintMessage(event.target.value)}
              minLength={10}
              maxLength={5000}
              rows={5}
              required
            />
            <button
              className="button button-primary auth-button"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Enviando..." : "Enviar mensaje"}
            </button>
          </form>
        ) : (
        <form className="auth-form" onSubmit={handleSubmit}>
          {isRegistering && (
            <>
              <label htmlFor="auth-username">Nombre de usuario</label>
              <input
                id="auth-username"
                name="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                minLength={3}
                maxLength={32}
                pattern="[A-Za-z0-9][A-Za-z0-9._-]{2,31}"
                title="Usa de 3 a 32 letras, números, punto, guion o guion bajo."
                required
              />
            </>
          )}
          <label htmlFor="auth-email">Correo electrónico</label>
          <input
            id="auth-email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            maxLength={254}
            required
          />
          <label htmlFor="auth-password">Contraseña</label>
          <div className="password-input-group">
            <input
              id="auth-password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete={isRegistering ? "new-password" : "current-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={isRegistering ? 12 : 1}
              maxLength={128}
              required
            />
            <button
              className="password-visibility-toggle"
              type="button"
              aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((visible) => !visible)}
            >
              <PasswordVisibilityIcon isVisible={showPassword} />
            </button>
          </div>
          <AnimatePresence initial={false}>
            {isRegistering && (
              <motion.div
                key="registration-fields"
                className="registration-fields"
                initial={{ opacity: 0, height: 0, y: reduceMotion ? 0 : 8 }}
                animate={{ opacity: 1, height: "auto", y: 0 }}
                exit={{ opacity: 0, height: 0, y: reduceMotion ? 0 : -5 }}
                transition={{ duration: reduceMotion ? 0 : 0.25, ease: [0.22, 1, 0.36, 1] }}
                style={{ overflow: "hidden" }}
              >
                <ul className="password-requirements" aria-label="Requisitos de contraseña">
                  <li className={passwordLengthIsValid ? "requirement-met" : ""}>
                    <span aria-hidden="true">{passwordLengthIsValid ? "✓" : "○"}</span>
                    Entre 12 y 128 caracteres
                  </li>
                  <li className={passwordHasUppercase ? "requirement-met" : ""}>
                    <span aria-hidden="true">{passwordHasUppercase ? "✓" : "○"}</span>
                    Al menos una mayúscula
                  </li>
                  <li className={passwordHasNumber ? "requirement-met" : ""}>
                    <span aria-hidden="true">{passwordHasNumber ? "✓" : "○"}</span>
                    Al menos un número
                  </li>
                  <li className={passwordHasSpecial ? "requirement-met" : ""}>
                    <span aria-hidden="true">{passwordHasSpecial ? "✓" : "○"}</span>
                    Al menos un carácter especial
                  </li>
                </ul>
                <label htmlFor="auth-confirmation">Confirma la contraseña</label>
                <div className="password-input-group">
                  <input
                    id="auth-confirmation"
                    name="confirmation"
                    type={showConfirmation ? "text" : "password"}
                    autoComplete="new-password"
                    value={confirmation}
                    onChange={(event) => setConfirmation(event.target.value)}
                    minLength={12}
                    maxLength={128}
                    required
                  />
                  <button
                    className="password-visibility-toggle"
                    type="button"
                    aria-label={showConfirmation ? "Ocultar confirmación" : "Mostrar confirmación"}
                    aria-pressed={showConfirmation}
                    onClick={() => setShowConfirmation((visible) => !visible)}
                  >
                    <PasswordVisibilityIcon isVisible={showConfirmation} />
                  </button>
                </div>
                <ul className="password-requirements" aria-label="Validación de contraseña">
                  <li className={passwordsMatch ? "requirement-met" : ""} aria-live="polite">
                    <span aria-hidden="true">{passwordsMatch ? "✓" : "○"}</span>
                    Las contraseñas coinciden
                  </li>
                </ul>
                <label htmlFor="requested-role">Perfil solicitado</label>
                <select
                  id="requested-role"
                  name="role"
                  value={requestedRole}
                  onChange={(event) => setRequestedRole(event.target.value)}
                >
                  {OPERATIONAL_ROLES.map((role) => (
                    <option key={role} value={role}>
                      {ROLE_PROFILES[role].label}
                    </option>
                  ))}
                </select>
                  <label htmlFor="requested-branch">Sucursal solicitada</label>
                  <select
                    id="requested-branch"
                    name="branch"
                    value={requestedBranch}
                    required
                    onChange={(event) => setRequestedBranch(event.target.value)}
                  >
                    <option value="" disabled>
                      Selecciona una sucursal
                    </option>
                    {BRANCH_OPTIONS.map(({ value, label }) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </motion.div>
            )}
          </AnimatePresence>
          <button
            className="button button-primary auth-button"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? "Procesando..."
              : isRegistering
                ? "Enviar solicitud"
                : "Iniciar sesión"}
          </button>
        </form>
        )}
      </motion.section>
    </main>
  );
}

function PasswordVisibilityIcon({ isVisible }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {isVisible ? (
        <>
          <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
          <circle cx="12" cy="12" r="3" />
        </>
      ) : (
        <>
          <path d="m3 3 18 18" />
          <path d="M10.6 5.2A10.8 10.8 0 0 1 12 5c6.4 0 10 7 10 7a14.8 14.8 0 0 1-3.1 3.8" />
          <path d="M6.2 6.2C3.5 8 2 12 2 12s3.6 7 10 7c1.2 0 2.3-.2 3.3-.6" />
        </>
      )}
    </svg>
  );
}
