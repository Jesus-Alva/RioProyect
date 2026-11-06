---
name: 'Frontend Next.js Web System'
description: 'Usar al crear o modificar la interfaz web con login y dashboards por rol.'
applyTo: 'frontend/**/*.{js,jsx,css}'
---
# Reglas del frontend (Next.js + Tailwind)

## Arquitectura de la App
- Usa Next.js 15 (App Router). Sin TypeScript.
- Protege `/dashboard` con el JWT guardado en `localStorage` y valida la sesión consultando el backend.

## Dashboard por Roles
- `directivo`: Reporte simulado de ventas para Guadalajara, Zapopan, León, Querétaro y Aguascalientes, con chat.
- `analista`: Facturas de ejemplo con confianza menor a 0.8 y chat.
- `gerente`: Panel simulado de atención a clientes y pedidos, con chat.
- `bodega`: Interfaz mobile-first, botón grande de Web Speech API y chat.
- `ti`: Estado de sistema ilustrativo y controles claramente identificados como demostración.
- `admin`: Gestión de usuarios y cinco paneles de chat separados, uno por cada agente operativo.

## Reglas del Chat
- Envía `Authorization: Bearer <JWT>` y deja que el backend autentique y autorice la petición.
- Solo `admin` puede seleccionar agente; los usuarios operativos consultan únicamente el suyo.
- Nunca uses `admin` como `userFilter` de Azure AI Search.
- Conserva el banner de transparencia, extrae y presenta citas `【...】`, y usa `whitespace-pre-wrap`.

## Login y Registro Propio
- Elimina todas las dependencias, providers, configuración e imports de MSAL.
- `/login` ofrece formularios para iniciar sesión y registrarse.
- El registro puede solicitar uno de los cinco roles operativos; la cuenta queda pendiente y únicamente `admin` asigna permisos efectivos.
- Guarda el JWT recibido al iniciar sesión en `localStorage`; no guardes contraseñas.
- Usa el JWT en las peticiones protegidas. Si el backend rechaza o vence la sesión, limpia el token y vuelve a `/login`.

## Multi-Sucursal en UI
- En el formulario de Registro, pide al usuario seleccionar una **Sucursal** concreta además del Rol; el registro no puede asignar sucursales adicionales ni `all`.
- Admin gestiona una o más sucursales concretas con selección múltiple; el alcance global se representa como la lista explícita de las cinco sucursales.
- En el chat, todos los usuarios (incluido Admin) seleccionan una o más sucursales autorizadas. Envía esa lista y deja que el backend la valide contra SQLite.
- Cada respuesta y documento debe mantener visible su sucursal; al cambiar la selección del chat, inicia una conversación independiente.
- En el Dashboard del **Directivo**, muestra un selector o gráfico con las 5 sucursales.
- En el Dashboard de **Bodega**, clasifica cada elemento de inventario por su campo `branch`.

## Subida de Facturas (Dashboard Analista)
- En el panel de Laura (Analista), agrega un componente de "Subir Factura" (input type="file").
- Al subir el archivo, envíalo a `/api/invoices/upload` con el token JWT.
- Muestra estados visuales: "Procesando...", "Factura guardada con éxito", "Factura duplicada" o "Requiere revisión manual".
- Tras una carga exitosa, actualiza la lista de facturas del panel.
