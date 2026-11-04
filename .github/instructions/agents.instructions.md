---
name: 'Foundry Agents y FastAPI'
description: 'Usar al crear los agentes en Foundry o el backend FastAPI.'
applyTo: 'backend/app/**/*.py, backend/scripts/create_agents.py'
---
# Reglas de los Agentes y Backend

## Creación de Agentes (create_agents.py)
- Usa el SDK `azure-ai-projects` (versión 2.x).
- El endpoint se lee de la variable de entorno `FOUNDRY_PROJECT_ENDPOINT`.
- Crea un agente por cada rol: Directivo, Analista, Gerente, Bodega, TI.
- Cada agente debe tener instrucciones específicas de su rol (ej. el de Analista extrae facturas, el de Directivo genera reportes).
- **Seguridad Crítica**: Para la herramienta `AzureAISearchTool`, debes configurar el filtro dinámico: `security_id/any(g: search.in(g, '{{userFilter}}'))`. Define `userFilter` como un `StructuredInput` requerido.
- Usa el modelo `gpt-4o` o el que esté desplegado en el proyecto.

## Backend FastAPI (main.py)
- Endpoint `GET /health` que devuelva `{"status": "ok"}`.
- Endpoint `POST /api/chat` que reciba `message`, `role` y `conversation_id` (opcional).
- Valida que el mensaje tenga entre 1 y 2000 caracteres (si no, lanza `HTTPException` 422).
- Inicializa el `AIProjectClient` una sola vez (Singleton).
- Usa `openai.conversations.create()` y `openai.responses.create()` para mantener la memoria del chat.
- Pasa el `role` recibido al agente como el `userFilter` para que Azure AI Search aplique la seguridad.
- Si hay un error en Foundry, devuelve un `HTTPException` 502 genérico.