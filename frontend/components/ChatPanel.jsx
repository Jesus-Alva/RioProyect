"use client";

import { useEffect, useRef, useState } from "react";
import { InteractionRequiredAuthError } from "@azure/msal-browser";
import { useMsal } from "@azure/msal-react";

import ChatComposer from "./ChatComposer.jsx";
import ChatMessage from "./ChatMessage.jsx";
import { apiScope } from "../lib/msalConfig.js";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

function getErrorMessage(status) {
  if (status === 401) {
    return "La sesión o el token de acceso no son válidos. Inicia sesión de nuevo.";
  }
  if (status === 403) {
    return "Tu cuenta no tiene exactamente un rol de aplicación autorizado. Solicita la corrección al administrador.";
  }
  if (status === 422) {
    return "Revisa que tu mensaje tenga entre 1 y 2000 caracteres.";
  }
  if (status === 502) {
    return "El asistente no está disponible por el momento. Inténtalo más tarde.";
  }
  return "No se pudo procesar la solicitud. Inténtalo de nuevo.";
}

export default function ChatPanel({ role, account }) {
  const { instance } = useMsal();
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const endOfMessagesRef = useRef(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  async function getAccessToken() {
    if (!apiScope) {
      throw new Error(
        "Falta configurar el scope de acceso de la API de Río Claro.",
      );
    }
    try {
      const result = await instance.acquireTokenSilent({
        scopes: [apiScope],
        account,
      });
      return result.accessToken;
    } catch (tokenError) {
      if (!(tokenError instanceof InteractionRequiredAuthError)) {
        throw tokenError;
      }
      const result = await instance.acquireTokenPopup({
        scopes: [apiScope],
        account,
      });
      return result.accessToken;
    }
  }

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
      const accessToken = await getAccessToken();
      const response = await fetch(
        `${BACKEND_URL.replace(/\/$/, "")}/api/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            message: content,
            conversation_id: conversationId,
          }),
        },
      );

      let payload;
      try {
        payload = await response.json();
      } catch {
        throw new Error("El backend devolvió una respuesta que no se pudo leer.");
      }
      if (!response.ok) {
        throw new Error(getErrorMessage(response.status));
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
          : requestError.message ||
            "No se pudo obtener un token de acceso. Inicia sesión de nuevo.",
      );
    } finally {
      setIsSending(false);
    }
  }

  return (
    <section className="chat-panel" aria-labelledby="chat-title">
      <header className="chat-header">
        <h2 className="chat-title" id="chat-title">
          Asistente Río Claro
        </h2>
        <p className="chat-subtitle">
          Las consultas se autorizan con el rol de tu cuenta.
        </p>
      </header>

      <div
        className="chat-messages"
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        aria-label="Conversación"
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
          role={role}
          largeVoiceButton={role === "bodega"}
          value={message}
          onChange={setMessage}
          onSubmit={handleSubmit}
          isSending={isSending}
        />
      </footer>
    </section>
  );
}
