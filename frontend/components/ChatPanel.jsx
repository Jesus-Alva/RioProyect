"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";

import ChatComposer from "./ChatComposer.jsx";
import ChatMessage from "./ChatMessage.jsx";
import BranchMultiSelect from "./BranchMultiSelect.jsx";
import { ROLE_PROFILES } from "../lib/authRoles.js";
import { BRANCH_OPTIONS, formatBranchNames } from "../lib/branches.js";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const ROLE_STARTERS = {
  directivo: [
    "Resume los hallazgos ejecutivos de las facturas disponibles.",
    "Compara los principales movimientos entre las sucursales seleccionadas.",
  ],
  analista: [
    "Analiza las facturas encontradas y extrae proveedor, fecha, productos y total.",
    "Identifica los datos que requieren revisión humana e incluye sus fuentes.",
  ],
  gerente: [
    "Resume los hallazgos más relevantes de las facturas para apoyar decisiones operativas.",
    "Compara la información disponible de proveedores e indica las fuentes.",
  ],
  bodega: [
    "Consulta las existencias actuales por producto y sucursal.",
    "Busca un producto en el inventario y dime la cantidad disponible.",
  ],
  ti: [
    "¿Qué información técnica está disponible en las fuentes autorizadas?",
    "Ayúdame a entender cómo usar las funciones de este sistema.",
  ],
};

function getErrorMessage(status) {
  if (status === 401) {
    return "Tu sesión venció o no es válida. Inicia sesión de nuevo.";
  }
  if (status === 403) {
    return "Tu cuenta no tiene permiso para consultar este agente.";
  }
  if (status === 422) {
    return "Revisa que tu mensaje tenga entre 1 y 2000 caracteres.";
  }
  if (status === 502) {
    return "El asistente no está disponible por el momento. Inténtalo más tarde.";
  }
  return "No se pudo procesar la solicitud. Inténtalo de nuevo.";
}

export default function ChatPanel({ user, token, agentRole, isActive = true }) {
  const reduceMotion = useReducedMotion();
  const allowedBranches =
    user.role === "admin"
      ? BRANCH_OPTIONS.map(({ value }) => value)
      : (user.branches || []);
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [selectedBranches, setSelectedBranches] = useState(() =>
    allowedBranches.length ? [allowedBranches[0]] : [],
  );
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const endOfMessagesRef = useRef(null);
  const inputId = `chat-message-${agentRole}`;
  const isWarehouse = agentRole === "bodega";

  function changeBranches(branches) {
    setSelectedBranches(branches);
    setConversationId(null);
    setMessages([]);
    setError("");
  }

  useEffect(() => {
    if (!isActive || (messages.length === 0 && !isSending)) return;
    endOfMessagesRef.current?.scrollIntoView({
      behavior: reduceMotion ? "auto" : "smooth",
    });
  }, [isActive, messages, isSending, reduceMotion]);

  async function handleSubmit(event) {
    event.preventDefault();
    const content = message.trim();
    if (!content || !selectedBranches.length || isSending) return;

    const userMessage = {
      id: `${Date.now()}-user`,
      role: "user",
      content,
      branches: selectedBranches,
    };
    setMessages((current) => [...current, userMessage]);
    setMessage("");
    setError("");
    setIsSending(true);

    try {
      const body = {
        message: content,
        conversation_id: conversationId,
        branches: selectedBranches,
      };
      if (user.role === "admin") body.agent_role = agentRole;

      const response = await fetch(
        `${BACKEND_URL.replace(/\/$/, "")}/api/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(body),
        },
      );

      let payload;
      try {
        payload = await response.json();
      } catch {
        throw new Error("El backend devolvió una respuesta que no se pudo leer.");
      }
      if (!response.ok) {
        if (response.status === 401) {
          throw new Error(getErrorMessage(response.status));
        }
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : getErrorMessage(response.status),
        );
      }
      if (
        typeof payload.response !== "string" ||
        typeof payload.conversation_id !== "string" ||
        !Array.isArray(payload.branches) ||
        payload.branches.length !== selectedBranches.length ||
        !selectedBranches.every((branch) => payload.branches.includes(branch))
      ) {
        throw new Error("El backend devolvió una respuesta incompleta.");
      }

      setConversationId(payload.conversation_id);
      setMessages((current) => [
        ...current,
        {
          id: `${Date.now()}-assistant`,
          role: "assistant",
          content: payload.response,
          branches: payload.branches,
        },
      ]);
    } catch (requestError) {
      setMessages((current) =>
        current.filter((item) => item.id !== userMessage.id),
      );
      setMessage(content);
      setError(
        requestError instanceof TypeError
          ? "No se pudo conectar con el servidor. Verifica que el backend esté disponible."
          : requestError.message,
      );
    } finally {
      setIsSending(false);
    }
  }

  return (
    <section
      className={`chat-panel ${user.role === "admin" ? "admin-agent-panel" : ""}`}
      aria-labelledby={`chat-title-${agentRole}`}
    >
      <header className="chat-header">
        <h2 className="chat-title" id={`chat-title-${agentRole}`}>
          Asistente {ROLE_PROFILES[agentRole].label}
        </h2>
        <p className="chat-subtitle">
          {user.role === "admin"
            ? "Panel independiente para consultar este agente."
            : `Tu cuenta está autorizada como ${ROLE_PROFILES[agentRole].label}.`}
        </p>
        <BranchMultiSelect
          id={`chat-branches-${agentRole}`}
          label="Sucursales de la consulta"
          description={`Selecciona sucursales permitidas. Cambiar la selección inicia una conversación nueva. Actuales: ${formatBranchNames(selectedBranches)}.`}
          branches={BRANCH_OPTIONS.filter(({ value }) =>
            allowedBranches.includes(value),
          )}
          selectedBranches={selectedBranches}
          onChange={changeBranches}
          disabled={isSending}
          compact
        />
      </header>

      <div
        className="chat-messages"
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        aria-label={`Conversación con ${ROLE_PROFILES[agentRole].label}`}
      >
        {messages.length === 0 && !isSending ? (
          <div className="chat-welcome">
            <p className="welcome-message">
              Escribe una pregunta para iniciar la conversación. Las respuestas
              pueden incluir las fuentes utilizadas.
            </p>
            <div className="chat-starters" role="group" aria-label="Consultas sugeridas">
              {(ROLE_STARTERS[agentRole] || []).map((starter) => (
                <button
                  className="chat-starter"
                  key={starter}
                  type="button"
                  onClick={() => {
                    setMessage(starter);
                    document.getElementById(inputId)?.focus();
                  }}
                  disabled={isSending || !selectedBranches.length}
                >
                  {starter}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((item) => <ChatMessage key={item.id} message={item} />)
        )}
        {isSending && (
          <p className="message message-assistant" role="status">
            El asistente está preparando una respuesta...
          </p>
        )}
        <div ref={endOfMessagesRef} />
      </div>

      <footer className="chat-footer">
        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
        <ChatComposer
          role={agentRole}
          inputId={inputId}
          largeVoiceButton={isWarehouse}
          value={message}
          onChange={setMessage}
          onSubmit={handleSubmit}
          isSending={isSending}
          disabled={!selectedBranches.length}
        />
      </footer>
    </section>
  );
}
