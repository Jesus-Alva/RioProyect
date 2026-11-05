# Frontend Río Claro

Interfaz de chat con Next.js 15, React y Tailwind CSS.

## Desarrollo local

1. Copia `.env.example` a `.env.local` y configura `NEXT_PUBLIC_BACKEND_URL`.
2. Desde esta carpeta ejecuta `npm install`.
3. Inicia el servidor con `npm run dev`.
4. Ejecuta las pruebas con `npm test` y genera la compilación con `npm run build`.

El backend debe permitir el origen del frontend en `CORS_ORIGINS`. El modo
desarrollo del backend permite probar los cinco perfiles sin iniciar sesión;
en un entorno protegido, el backend requiere un token de Entra ID.
