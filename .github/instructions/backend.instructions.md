---
name: 'Backend y Agentes Foundry'
description: 'Usar al crear o modificar FastAPI, scripts de ingesta y creación de agentes.'
applyTo: 'backend/**/*.py'
---
# Reglas de Backend y Agentes

## FastAPI (main.py)
- Endpoint `POST /api/chat` recibe `message`, `role`, `conversation_id`.
- **Seguridad estricta**: El rol debe validarse con el token (o el bypass de desarrollo). El `role` debe pasarse SIEMPRE en minúsculas al `userFilter` del agente para que coincida con el índice.
- **Rendición de cuentas (Human-in-the-loop)**: Si el agente intenta responder sobre una factura, debe incluir la cita del documento.
- Devuelve 502 genérico si falla Foundry.

## Agentes Foundry (create_agents.py)
- Crea los 5 agentes (Directivo, Analista, Gerente, Bodega, TI).
- **Instrucciones del Agente Analista**: "Nunca inventes cifras. Si no encuentras el dato en la herramienta de búsqueda, di que no está disponible y que requiere revisión humana."
- **Instrucciones del Agente Directivo**: "Genera reportes ejecutivos usando tablas Markdown."
- **Filtro de Seguridad (Equidad y Privacidad)**: Usa `search.in(security_id, '{{userFilter}}')` en `AzureAISearchTool`. Asegúrate de que el campo `security_id` sea inyectado dinámicamente.

## Ingesta de Datos (seed_data.py)
- Extrae usando Document Intelligence (prebuilt-invoice).
- **Confiabilidad**: Si la confianza del total o proveedor es `< 0.8`, NO lo subas al índice; márcalo en `needs_review.jsonl` para que Laura lo revise manualmente.