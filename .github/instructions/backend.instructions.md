---
name: 'Backend y Agentes Foundry'
description: 'Usar al crear o modificar FastAPI, scripts de ingesta y creación de agentes.'
applyTo: 'backend/**/*.py'
---
# Reglas de Backend y Agentes

## FastAPI (main.py)
- Endpoint `POST /api/chat` recibe `message`, `branches` (lista obligatoria no vacía), `conversation_id` y `agent_role` opcional (solo para `admin`).
- **Seguridad estricta**: Deriva el rol efectivo del JWT validado y la cuenta activa en SQLite. El rol seleccionado para un agente nunca puede exceder los permisos del usuario.
- El `userFilter` debe ser uno de los cinco roles operativos en minúsculas; nunca uses `admin` como filtro. `branchFilter` se obtiene de la sesión verificada consultada en SQLite, nunca del body.
- **Rendición de cuentas (Human-in-the-loop)**: Si el agente intenta responder sobre una factura, debe incluir la cita del documento.
- Devuelve 502 genérico si falla Foundry.

## Agentes Foundry (create_agents.py)
- Crea los 5 agentes (Directivo, Analista, Gerente, Bodega, TI).
- **Instrucciones del Agente Analista**: "Nunca inventes cifras. Si no encuentras el dato en la herramienta de búsqueda, di que no está disponible y que requiere revisión humana."
- **Instrucciones del Agente Directivo**: "Genera reportes ejecutivos usando tablas Markdown."
- **Filtro de Seguridad (Equidad y Privacidad)**: Usa `security_id/any(g: search.in(g, '{{userFilter}}')) and search.in(branch, '{{branchFilter}}', ',')` en `AzureAISearchTool`, con ambos inputs estructurados y requeridos. `branchFilter` es una lista CSV construida solo con sucursales permitidas verificadas por el backend.

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

## Soporte Multi-Sucursal (Inventario y Facturas)
- `users.branches` y `users.requested_branches` almacenan listas JSON de sucursales concretas. El arranque migra de forma idempotente `branch` y `requested_branch` escalares históricos; el valor histórico `all` se expande a la lista explícita de las cinco sucursales.
- El JWT incluye la lista `branches`, comparada exactamente con la cuenta activa en SQLite. Tokens antiguos u obsoletos sin esa claim quedan bloqueados hasta reautenticarse.
- El registro puede solicitar una sucursal concreta y nunca asigna acceso; Admin asigna una o más sucursales válidas.
- `POST /api/chat` requiere `branches` no vacía. El backend comprueba que cada sucursal pertenezca a la cuenta activa, y solo la selección efectiva se guarda en los metadatos de conversación y se pasa a Foundry.
- **Filtro compuesto en Agentes**: usa `security_id/any(g: search.in(g, '{{userFilter}}')) and search.in(branch, '{{branchFilter}}', ',')`; el backend construye `branchFilter` con la lista validada. Los documentos siguen usando un campo `branch` escalar, uno por sucursal.
- `main.py` debe conservar la clasificación `branch` de cada documento/inventario y exponer la lista de sucursales aplicada.

## Scripts de Datos (seed_data.py y setup_search_index.py)
- En `setup_search_index.py`, agrega el campo `branch` (String, filterable).
- En `seed_data.py`, el manifiesto `invoice-access.json` debe incluir la sucursal escalar del documento (ej. `"factura_001.pdf": {"roles": ["analista"], "branch": "leon"}`).
- Para el inventario, el agente de Bodega debe consultar un índice de inventario (`inventario-index`) donde los documentos tengan los campos `producto`, `cantidad`, `branch`.

## Carga y Validación de Facturas (Panel de Analista)
- Crea un endpoint `POST /api/invoices/upload` en FastAPI que reciba un archivo (PDF/Imagen) y valide que el usuario tenga el rol `analista`.
- Usa `DocumentIntelligenceClient` (modelo `prebuilt-invoice`) para extraer proveedor, fecha y total.
- **Control de Duplicados**: Antes de guardar en AI Search, busca en el índice si ya existe una factura con el mismo `vendor_name`, `invoice_date` e `invoice_total`. Si existe, devuelve un error 409 (Conflict) indicando "Factura duplicada".
- Si no es duplicada y la confianza es > 0.8, guárdala en Blob Storage (opcional) y súbela a AI Search con su `security_id` y `branch`.
- Si la confianza es < 0.8, devuélvela a una lista de "Revisión Manual" en el frontend sin indexarla.