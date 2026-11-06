"use client";

import { useEffect, useRef, useState } from "react";

export default function ChatComposer({
  role,
  largeVoiceButton = false,
  value,
  onChange,
  onSubmit,
  isSending,
}) {
  const recognitionRef = useRef(null);
  const [isListening, setIsListening] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("");

  useEffect(
    () => () => {
      recognitionRef.current?.stop();
    },
    [],
  );

  function toggleVoiceInput() {
    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceStatus("El dictado por voz no está disponible en este navegador.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "es-MX";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0].transcript)
        .join(" ")
        .trim();
      if (transcript) {
        onChange(value ? `${value.trimEnd()} ${transcript}` : transcript);
      }
    };
    recognition.onerror = (event) => {
      setVoiceStatus(
        event.error === "not-allowed"
          ? "Permite el acceso al micrófono en tu navegador para dictar."
          : "No se pudo completar el dictado. Inténtalo de nuevo.",
      );
      setIsListening(false);
    };
    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    setVoiceStatus("");
    try {
      recognition.start();
      setIsListening(true);
    } catch {
      setVoiceStatus("No se pudo iniciar el micrófono. Inténtalo de nuevo.");
      setIsListening(false);
      recognitionRef.current = null;
    }
  }

  return (
    <form
      className={`composer ${largeVoiceButton ? "composer-bodega" : ""}`}
      onSubmit={onSubmit}
    >
      <label className="sr-only" htmlFor="chat-message">
        Escribe tu consulta
      </label>
      <textarea
        id="chat-message"
        name="message"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Escribe tu consulta..."
        maxLength={2000}
        disabled={isSending}
        required
      />
      {voiceStatus && (
        <p className="voice-status" role="status">
          {voiceStatus}
        </p>
      )}
      <div className="composer-actions">
        <span className="character-count" aria-live="polite">
          {value.length}/2000 caracteres
        </span>
        <div className="composer-buttons">
          {role === "bodega" && (
            <button
              className={`button voice-button ${largeVoiceButton ? "voice-button-large" : ""} ${isListening ? "button-listening" : "button-secondary"}`}
              type="button"
              onClick={toggleVoiceInput}
              disabled={isSending}
              aria-pressed={isListening}
              aria-label={isListening ? "Detener dictado" : "Dictar consulta"}
            >
              {isListening
                ? largeVoiceButton
                  ? "■ Detener dictado"
                  : "■ Detener"
                : largeVoiceButton
                  ? "🎙 Dictar consulta"
                  : "🎙 Dictar"}
            </button>
          )}
          <button
            className="button button-primary"
            type="submit"
            disabled={isSending || !value.trim()}
          >
            {isSending ? "Enviando..." : "Enviar"}
          </button>
        </div>
      </div>
    </form>
  );
}
