# Frontend Río Claro

Interfaz de chat con Next.js 15, React y Tailwind CSS.

## Desarrollo local

1. Copia `.env.example` a `.env.local` y configura `NEXT_PUBLIC_BACKEND_URL`.
2. Desde esta carpeta ejecuta `npm install`.
3. Inicia el servidor con `npm run dev`.
4. Ejecuta las pruebas con `npm test` y genera la compilación con `npm run build`.

El backend debe permitir el origen del frontend en `CORS_ORIGINS`. El registro
solicita nombre de usuario, correo, contraseña, rol y sucursal, y crea una
solicitud pendiente. El nombre de usuario debe ser único; el inicio de sesión
sigue usando el correo. El administrador asigna permisos desde su panel. El
JWT de sesión se guarda en `localStorage` y se envía en el header
`Authorization` a los endpoints protegidos.
