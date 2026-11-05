# Levantar servicios

## Inicializar entorno venv

```bash
.\venv\Scripts\Activate.ps1   
```

## Backend
Levantar el servicio backend con uvicorn
```bash
uvicorn backend.app.main:app --reload
```