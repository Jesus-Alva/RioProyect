"use client";

import { useEffect, useRef, useState } from "react";

import ChatComposer from "../components/ChatComposer.jsx";
import ChatMessage from "../components/ChatMessage.jsx";
import RoleSelector from "../components/RoleSelector.jsx";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

function getErrorMessage(status) {
  if (status === 401) {
    return "No se pudo autenticar la solicitud. Inicia sesión e inténtalo de nuevo.";
  }
  if (status === 422) {
    return "Revisa que tu mensaje tenga entre 1 y 2000 caracteres y que el perfil esté autorizado.";
  }
  if (status === 502) {
    return "El asistente no está disponible por el momento. Inténtalo más tarde.";
  }
  return "No se pudo procesar la solicitud. Inténtalo de nuevo.";
}

export default function Home() {
  const [role, setRole] = useState("directivo");
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const endOfMessagesRef = useRef(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  function changeRole(nextRole) {
    if (nextRole === role) return;
    setRole(nextRole);
    setMessages([]);
    setConversationId(null);
    setError("");
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
      const response = await fetch(`${BACKEND_URL.replace(/\/$/, "")}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          role,
          conversation_id: conversationId,
        }),
      });

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
          : requestError.message,
      );
    } finally {
      setIsSending(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="chat-panel" aria-labelledby="chat-title">
        <header className="chat-header">
          <h1 className="chat-title" id="chat-title">
            Asistente Río Claro
          </h1>
          <p className="chat-subtitle">
            Consulta información de la distribuidora según tu perfil.
          </p>
          <RoleSelector
            value={role}
            onChange={changeRole}
            disabled={isSending}
          />
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
            value={message}
            onChange={setMessage}
            onSubmit={handleSubmit}
            isSending={isSending}
          />
        </footer>
      </section>

      <aside className="transparency-banner" role="note">
        Estás interactuando con un asistente de IA. Las respuestas se basan en
        documentos oficiales.
      </aside>
    </main>
  );
}
