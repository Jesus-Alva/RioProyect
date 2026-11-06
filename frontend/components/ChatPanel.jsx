"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";

import ChatComposer from "./ChatComposer.jsx";
import ChatMessage from "./ChatMessage.jsx";
import { ROLE_PROFILES } from "../lib/authRoles.js";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

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
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const endOfMessagesRef = useRef(null);
  const inputId = `chat-message-${agentRole}`;
  const isWarehouse = agentRole === "bodega";

  useEffect(() => {
    if (!isActive || (messages.length === 0 && !isSending)) return;
    endOfMessagesRef.current?.scrollIntoView({
      behavior: reduceMotion ? "auto" : "smooth",
    });
  }, [isActive, messages, isSending, reduceMotion]);

  async function handleSubmit(event) {
    event.preventDefault();
    const content = message.trim();
    if (!content || isSending) return;

    const userMessage = {
      id: `${Date.now()}-user`,
      role: "user",
      content,
    };
    setMessages((current) => [...current, userMessage]);
    setMessage("");
    setError("");
    setIsSending(true);

    try {
      const body = {
        message: content,
        conversation_id: conversationId,
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
        typeof payload.conversation_id !== "string"
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
      </header>

      <div
        className="chat-messages"
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        aria-label={`Conversación con ${ROLE_PROFILES[agentRole].label}`}
      >
        {messages.length === 0 && !isSending ? (
          <p className="welcome-message">
            Escribe una pregunta para iniciar la conversación. Las respuestas
            pueden incluir las fuentes utilizadas.
          </p>
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
        />
      </footer>
    </section>
  );
}
