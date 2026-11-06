---
name: 'Backend y Agentes Foundry'
description: 'Usar al crear o modificar FastAPI, scripts de ingesta y creación de agentes.'
applyTo: 'backend/**/*.py'
---
# Reglas de Backend y Agentes

## FastAPI (main.py)
- Endpoint `POST /api/chat` recibe `message`, `conversation_id` y `agent_role` opcional (solo para `admin`).
- **Seguridad estricta**: Deriva el rol efectivo del JWT validado y la cuenta activa en SQLite. El rol seleccionado para un agente nunca puede exceder los permisos del usuario.
- El `userFilter` debe ser uno de los cinco roles operativos en minúsculas; nunca uses `admin` como filtro.
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

## Autenticación (Custom JWT)
- Usa `SQLAlchemy` para una base de datos SQLite local `users.db`.
- Crea endpoints `POST /api/auth/register` y `POST /api/auth/login`.
- Usa `passlib[bcrypt]` para hashear contraseñas. Las cuentas nuevas quedan pendientes hasta aprobación de `admin`.
- Usa `PyJWT` para generar y validar tokens firmados con `JWT_SECRET` (desde `.env`).
- `authenticate_user` debe leer y validar el JWT, comprobar en SQLite que la cuenta siga activa y extraer su rol vigente.
- Solo `admin` puede asignar o revocar permisos. El administrador puede consultar los cinco agentes operativos por separado; nunca uses `admin` como filtro de búsqueda.