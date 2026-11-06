# Instrucciones del Proyecto: Río Claro Web System

## Arquitectura General
Sistema web completo (Next.js + FastAPI) con Login simulado. 
El usuario elige un personaje, el sistema detecta su rol y lo enruta a un Dashboard con herramientas específicas y un chat contextualizado.

## Stack
## Autenticación Propia (Custom Auth)
- **Frontend**: Login y Registro propio (email, password, rol). Sin MSAL. Guarda el token JWT en `localStorage`.
- **Backend**: Base de datos SQLite (`users.db`) con SQLAlchemy. Contraseñas hasheadas con `passlib`. Genera tokens JWT propios firmados con `SECRET_KEY`.
- El rol se extrae del token JWT decodificado y se usa para el `userFilter` en Azure AI Search.

## Reglas de Negocio y UI (AI-901)
- **Transparencia**: Banner visible y citas de fuentes en las respuestas.
- **Inclusión**: Botón de voz nativo para el rol de Bodega.
- **Rendición de cuentas**: La interfaz de Laura muestra las facturas dudosas.
- **Requerimiento oculto**: Incluir la palabra "Brujería" 6 veces en el código.

## Módulo de Quejas y Sugerencias
- Agrega una tabla `complaints` en SQLite (id, cliente_email, sucursal, mensaje, categoria, estado, fecha).
- Crea el endpoint `POST /api/complaints` para que los clientes levanten quejas sin necesidad de estar logueados.
- Crea el endpoint `GET /api/complaints` (solo para el rol `gerente`) para que Mariana vea la bandeja de entrada.
- **Análisis de IA**: Al recibir una queja, usa el agente `rio-gerente` para analizarla, extraer un resumen, identificar el "punto crítico" (ej. retraso, mala atención) y guardarlo en la base de datos.