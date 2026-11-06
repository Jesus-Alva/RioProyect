# Instalacion Local del Proyecto (Step to Step) 

# Levantar servicios

## Inicializar el entorno virtual Python

Desde la raíz del repositorio, crea el entorno virtual e instala las
dependencias del backend:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

## Backend

Configura `.env` a partir de `.env.example`. `JWT_SECRET` debe ser un secreto
aleatorio de al menos 32 bytes; puedes generarlo con:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Configura también `CORS_ORIGINS` con el origen del frontend. La base local
`backend\users.db` se crea automáticamente al arrancar y está excluida de Git.

Instala dependencias e inicia FastAPI desde la raíz:

```bash
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

El registro público deja las cuentas pendientes de aprobación. Crea la cuenta
inicial de administración de forma interactiva:

```powershell
.\.venv\Scripts\python.exe backend\scripts\create_admin.py
```

Después, inicia sesión con esa cuenta para aprobar solicitudes y asignar uno
de los cinco roles operativos. `admin` no es un filtro de búsqueda ni un agente.
El registro solicita nombre de usuario único, correo, rol y sucursal; el nombre
de usuario se muestra en el panel administrativo. El inicio de sesión sigue
usando el correo electrónico.
El frontend guarda el JWT en `localStorage`; por ello, despliega solo sobre
orígenes HTTPS y evita insertar contenido HTML no confiable para reducir el
riesgo de exposición ante XSS.

El dashboard de Directivo consulta `GET /api/director/sales-report` y agrupa
los importes y conteos de las facturas indexadas o aprobadas por sucursal
autorizada. El total representa importes brutos extraídos de facturas, no ventas
netas; excluye facturas pendientes de revisión y declinadas.

## Frontend

Copia `frontend\.env.example` a `frontend\.env.local`, instala dependencias y
levanta Next.js:

```powershell
cd frontend
npm install
npm run dev
```

La aplicación estará disponible en `http://localhost:3000`.


## Creacion de la cuenta Admin
```bash no me
python -m pip install -r backend\requirements.txt
python backend\scripts\create_admin.py
```

# Credenciales Actuales del sistema
Credenciales para administrador
- Correo: admin@gmail.com
- Password: 123456789pass

Creadenciales para Directivo
- Correo: directivo@gmail.com
- Password: Directivo@123

Credenciales para Analista
- Correo: analista@gmail.com
- Password: Analista@123

Credenciales para Gerente Sucursal Guadalajara
- Correo: gerente_guadalajara@gmail.com
- Password: GerenteGDL@1

Credenciales para Bodega Sucursal Gudalajara
- Correo: bodega_guadalajara@gmail.com
- Password: BodegaGDL@12

Credenciales para TI
- Correo: ti@gmail.com
- Password: Ti@123456789