import { extractCitations } from "../lib/citations.js";

export default function ChatMessage({ message }) {
  const isUser = message.role === "user";
  const { answer, citations } = isUser
    ? { answer: message.content, citations: [] }
    : extractCitations(message.content);

  return (
    <article
      className={`message ${isUser ? "message-user" : "message-assistant"}`}
      aria-label={isUser ? "Tu mensaje" : "Respuesta del asistente"}
    >
      <span className="message-label">{isUser ? "Tú" : "Asistente"}</span>
      <div className="whitespace-pre-wrap">{answer}</div>
      {citations.length > 0 && (
        <div>
          <span className="message-label">Fuentes citadas</span>
          <ul className="citation-list" aria-label="Fuentes citadas">
            {citations.map((citation, index) => (
              <li className="citation-chip" key={`${citation}-${index}`}>
                Fuente: {citation}
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
