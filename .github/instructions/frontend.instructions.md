---
name: 'Frontend Next.js Web System'
description: 'Usar al crear o modificar la interfaz web con login y dashboards por rol.'
applyTo: 'frontend/**/*.{js,jsx,css}'
---
# Reglas del frontend (Next.js + Tailwind)

## Arquitectura de la App
- Usa Next.js 15 (App Router). Sin TypeScript.
- **Protección de rutas**: Si no hay usuario en `localStorage`, el `/dashboard` redirige a `/login`.

## Dashboard por Roles (El sistema cambia según el usuario)
En `/dashboard`, renderiza diferentes componentes según el rol logueado:
1. **Directivo (Ernesto)**: Muestra una tabla simulada de "Reporte de Ventas" (Guadalajara, Zapopan, León, Querétaro, Aguascalientes) y un chat para consultar tendencias.
2. **Analista (Laura)**: Muestra un panel de "Revisión Manual" (una lista estática simulada de facturas con confianza < 0.8) y el chat para consultar facturas procesadas.
3. **Gerente (Mariana)**: Muestra un panel de "Atención a Clientes" (simulado) y el chat para responder dudas de clientes.
4. **Bodega (Toño)**: Muestra una interfaz simplificada, mobile-first, con un botón de micrófono gigante (Web Speech API) para dictar consultas al chat.
5. **TI (Carlos)**: Muestra un panel de "Estado del Sistema" (luz verde de conexión a Azure) y un botón de "Pausar IA".

## Reglas del Chat (En todos los roles)
- El rol ya no se elige en el chat; se lee automáticamente del `localStorage` y se envía al backend.
- Banner fijo: *"Estás interactuando con un asistente de IA. Las respuestas se basan en documentos oficiales."*
- Si el backend devuelve la respuesta con citas `【...】`, resáltalas.
- Usa `whitespace-pre-wrap` para los saltos de línea.

## Login Real con MSAL
- Instala `@azure/msal-browser` y `@azure/msal-react`.
- Configura el `MsalProvider` en `layout.jsx` usando las variables `NEXT_PUBLIC_ENTRA_CLIENT_ID`, `NEXT_PUBLIC_ENTRA_TENANT_ID` y `NEXT_PUBLIC_ENTRA_API_SCOPE`.
- La página `/login` debe tener un botón que ejecute `instance.loginPopup()`.
- El componente de chat debe obtener el token usando `acquireTokenSilent` e inyectarlo en la cabecera `Authorization: Bearer <token>`.
- La vista del dashboard debe leer el rol desde el token de MSAL (usando `useMsal` y `account.idTokenClaims.roles`) para mostrar el panel del Directivo, Analista, etc.