# Instrucciones del Proyecto: Río Claro Data-First

## ¿Qué es este proyecto?
Sistema web para Distribuidora Río Claro. **La prioridad #1 es ordenar la capa de datos** (facturas, catálogo, políticas) antes de crear agentes.
El backend (FastAPI) orquesta la lógica de negocio y selecciona el agente de Foundry según el rol del usuario autenticado.
El frontend (Next.js + Tailwind) solo consume la API del backend.

## Entorno de desarrollo
- Ubuntu 26.04.1 LTS
- Node.js 22.22.1 y npm, Nada de Typescript ni builders.

## Stack y versiones
- **Backend**: Python 3.11+, FastAPI, Uvicorn, `azure-ai-projects` (2.x), `azure-identity`, `azure-search-documents`.
- **Frontend**: Next.js 15 (App Router), React, Tailwind CSS. **Con TypeScript**.
- **Autenticación**: `DefaultAzureCredential` en Python; Entra ID para identidad de usuario final.
- **Variables de entorno**: Se leen con `os.getenv()`.

## Arquitectura (no la cambies sin preguntar)
1. **Capa de Datos (Fase 1)**: Scripts en `backend/scripts/` para extraer facturas (Document Intelligence) e indexar datos con seguridad (Azure AI Search).
2. **Agentes (Fase 2)**: Creación de agentes en Foundry conectados al índice.
3. **Backend (Fase 3)**: Endpoints `/api/chat` y `/health` en FastAPI.
4. **Frontend (Fase 4)**: Interfaz de chat en Next.js.

## Seguridad
- Nunca escribas llaves, tokens ni endpoints reales en el código.
 Todo sale de variables de entorno.
- En Azure se usa identidad administrada (managed identity), no API keys.
- Valida la entrada (1 a 2000 caracteres) y responde 422 si no cumple.
- Si Foundry falla, responde 502 con un mensaje genérico; no filtres trazas.
## Estilo de código
- Comentarios en español neutro; nombres de variables en inglés.
- Cambios mínimos y enfocados: no reescribas archivos completos si basta editar.
## Cómo validar
- Local: `npm run dev` y abrir http://localhost:3000
- Salud: `Invoke-RestMethod http://localhost:3000/health` debe devolver `status: ok`
- Antes de desplegar, confirma que `package.json` incluye todo lo que se importa.