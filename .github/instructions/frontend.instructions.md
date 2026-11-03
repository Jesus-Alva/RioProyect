---
name: 'Frontend Next.js'
description: 'Usar al crear o modificar la interfaz web del chatbot.'
applyTo: 'frontend/**/*.{js,jsx,css}'
---
# Reglas del frontend
- Usa Next.js 15 (App Router) y Tailwind CSS.
- Sin TypeScript (usa `.js` y `.jsx`).
- La URL del backend se obtiene de `process.env.NEXT_PUBLIC_BACKEND_URL`.
- Incluye el aviso: "Estás interactuando con un asistente de IA".
- El chat debe ser responsivo (mobile-first).