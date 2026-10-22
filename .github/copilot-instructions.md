# Instrucciones del Proyecto Chatbot Foundry Certificador en APP Service

## ¿Qué es este proyecto?
Página web de una sola vista con un chatbot con IA.
EL frontend (HTML, CSS y JS sin frameworks) llama a un backend Node.js con Express y el backend conversa con un agente en Microsoft Foundry. Se despliega en Azure App Service (Linux, Node 24 LTS).

## Entorno de desarrollo
- Ubuntu 26.04.1 LTS
- Node.js 22.22.1 y npm, Nada de Typescript ni builders.

## Stack y versiones
- Express 5, ES Modules (`"type": "module"`), `async/await`.
- SDK de Foundry: `@azure/ai-projects` 2.x (API "Foundry projects (new)").
 No uses `@azure/ai-agents` ni la API 1.x.
- Autenticación: `DefaultAzureCredential` de `@azure/identity`.
- Variables de entorno en local con `node --env-file-if-exists=.env` (sin dotenv).

## Arquitectura (no la cambies sin preguntar)
- `server.js`: sirve `public/` en `/`, expone `POST /api/chat` y `GET /health`.
- El navegador NUNCA habla directo con Foundry. Solo el backend.
- `FOUNDRY_PROJECT_ENDPOINT` apunta a la raíz del proyecto
 (`.../api/projects/<project>`), no a una ruta del agente.
- El cliente OpenAI se vincula al endpoint dedicado del agente con
 `getOpenAIClient({ azureConfig: { allowPreview: true, agentName } })`.
- Conversación multi-turno: `openai.conversations.create()` y
 `openai.responses.create({ conversation, input })`.
 El `conversation_id` viaja entre frontend y backend en el JSON.
- El servidor escucha en `process.env.PORT` (App Service lo define).

## Seguridad
- Nunca escribas llaves, tokens ni endpoints reales en el código.
 Todo sale de variables de entorno: `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_AGENT_NAME`.
- En Azure se usa identidad administrada (managed identity), no API keys.
- Valida la entrada (1 a 2000 caracteres) y responde 422 si no cumple.
- Si Foundry falla, responde 502 con un mensaje genérico; no filtres trazas.
## Estilo de código
- Comentarios en español neutro; nombres de variables en inglés.
- Cambios mínimos y enfocados: no reescribas archivos completos si basta editar.
## Cómo validar
- Local: `npm run dev` y abrir http://localhost:3000
- Salud: `Invoke-RestMethod http://localhost:3000/health` debe devolver `status: ok`
- Antes de desplegar, confirma que `package.json` incluye todo lo que se importa
 y que el script `start` es `node server.js`.