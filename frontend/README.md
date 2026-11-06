# Frontend Río Claro

Interfaz de chat con Next.js 15, React y Tailwind CSS.

## Desarrollo local

1. Copia `.env.example` a `.env.local` y configura `NEXT_PUBLIC_BACKEND_URL`.
2. Desde esta carpeta ejecuta `npm install`.
3. Inicia el servidor con `npm run dev`.
4. Ejecuta las pruebas con `npm test` y genera la compilación con `npm run build`.

El backend debe permitir el origen del frontend en `CORS_ORIGINS`. El registro
crea una solicitud pendiente; el administrador asigna un rol operativo desde
su panel. El JWT de sesión se guarda en `localStorage` y se envía en el header
`Authorization` a los endpoints protegidos.
