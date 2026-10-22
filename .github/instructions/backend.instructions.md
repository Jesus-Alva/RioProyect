---
name: 'Backend Express'
description: 'Usar al crear o modificar el backend Node.js que llama a Microsoft Foundry.'
applyTo: 'server.js,scripts/**'
---
# Reglas del backend
* Crea el `AIProjectClient` y el cliente de OpenAI una sola vez al iniciar, no en cada request.
* `FOUNDRY_PROJECT_ENDPOINT` debe ser la raíz del proyecto; no incluyas rutas
 `/agents/.../endpoint/protocols/openai/...`.
* Vincula el cliente OpenAI al endpoint dedicado del agente con
 `getOpenAIClient({ azureConfig: { allowPreview: true, agentName } })`.
 No uses `agent_reference` en las peticiones del endpoint compartido.
* Usa `async/await` y envuelve las llamadas al SDK en `try/catch` → 502 genérico.
* Resuelve rutas de archivos con `import.meta.dirname`, no con el directorio actual.
* No agregues dependencias nuevas sin mencionarlas en el plan.
 
 