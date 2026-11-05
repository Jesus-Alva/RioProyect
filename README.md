# Levantar servicios

## Inicializar entorno venv

```bash
.\venv\Scripts\Activate.ps1   
```

## Backend

Configura `CORS_ORIGINS` en `.env` con el origen del frontend. En desarrollo:
`CORS_ORIGINS=http://localhost:3000`.

Levanta FastAPI desde la raíz del repositorio:

```bash
uvicorn backend.app.main:app --reload
```

## Frontend

Copia `frontend\.env.example` a `frontend\.env.local`, instala dependencias y
levanta Next.js:

```powershell
cd frontend
npm install
npm run dev
```

La aplicación estará disponible en `http://localhost:3000`.
