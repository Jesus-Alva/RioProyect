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

Instala dependencias e inicia FastAPI desde la raíz y levanta el servicio para backend:

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

## Quejas y sugerencias

En `/login`, cualquier cliente puede enviar su nombre, correo, sucursal y
mensaje sin iniciar sesión. `POST /api/complaints` usa el agente `rio-gerente`
de Azure AI Foundry para obtener categoría, resumen y punto crítico antes de
insertar la queja en SQLite. El modelo recibe solo el texto y la sucursal; el
rol y el filtro de sucursal se fijan en el backend. Si el análisis falla, la
queja se conserva para revisión manual y la respuesta indica que el resumen de
IA no está disponible.

El panel Gerente consulta `GET /api/complaints` y actualiza seguimiento con
`PATCH /api/complaints/{id}`. Ambos requieren una sesión Gerente vigente y
limitan los datos a sus sucursales asignadas. Los estados de seguimiento son
`received`, `in_progress` y `resolved`; las categorías provienen del análisis
del agente. La bandeja se actualiza al abrirse, al volver a la pestaña y cada
30 segundos; también puede actualizarse manualmente. El formulario público no
guarda los datos de contacto en el navegador; aplica límites de tamaño y
validación de correo. En despliegues
públicos, configura límites de solicitudes en el gateway o proxy para mitigar
spam.

## Despliegue en Azure App Service

El script `deploy.ps1` publica el backend FastAPI en App Service Linux con
Python 3.11 y el frontend Next.js con Node 22 LTS. Ambos usan un plan Linux. Antes
de ejecutarlo, instala Azure CLI, ejecuta `az login`, completa el `.env` raíz
con los endpoints y un `JWT_SECRET` de al menos 32 caracteres, y confirma que
las cuentas de Storage, AI Search, Foundry y Document Intelligence ya existen.
La identidad que ejecuta el script necesita permisos para crear App Services y
asignar roles RBAC en los recursos indicados.

Ejemplo desde PowerShell, sustituyendo los nombres por los de la suscripción:

```powershell
.\deploy.ps1 `
  -ResourceGroup "rg-rio-claro" `
  -Location "eastus2" `
  -BackendAppName "rio-claro-api-unico" `
  -FrontendAppName "rio-claro-web-unico" `
  -StorageAccountName "rioclarostorage" `
  -SearchServiceName "rio-claro-search" `
  -FoundryAccountName "rio-claro-foundry" `
  -DocumentIntelligenceAccountName "rio-claro-docintel"
```

Los cuatro parámetros `*-ResourceGroup` opcionales permiten indicar si los
servicios de Azure existentes están en grupos distintos. El script pide una
confirmación antes de cambiar recursos, configura App Settings desde `.env`
(sin incluir `.env` en los paquetes), despliega los dos ZIP, habilita HTTPS y
asigna a la identidad del backend `Storage Blob Data Contributor`, `Search
Index Data Contributor`, `Search Service Contributor` y `Cognitive Services
User` en Foundry y Document Intelligence. Al final valida `/health` y la página
del frontend. Los ZIP se envían en modo asíncrono para evitar que la solicitud
de despliegue agote el tiempo de espera mientras App Service compila; el script
espera hasta 40 minutos por cada aplicación y compila backend y frontend de
forma secuencial para no competir por recursos del plan. El ZIP del backend
incluye `main.py` y `requirements.txt` directamente en la raíz (el script
comprueba también las rutas requeridas antes de subirlo) y conserva el paquete
`backend` con separadores `/` portables para Linux. El script configura
`PYTHONPATH=/home/site/wwwroot` para permitir sus
imports en App Service. El backend arranca con `python -m uvicorn main:app --host 0.0.0.0
--port 8000`. El script establece `PORT=8000`, `WEBSITES_PORT=8000`,
`SCM_DO_BUILD_DURING_DEPLOYMENT=true`, `ENABLE_ORYX_BUILD=true` y
`WEBSITES_CONTAINER_START_TIME_LIMIT=1800` para permitir hasta 30 minutos de
inicio del contenedor.

Para redesplegar únicamente un backend existente, sin actualizar el frontend
ni volver a configurar secretos o permisos:

```powershell
.\deploy.ps1 -BackendOnly -ResourceGroup "rg-rio-claro" -BackendAppName "rio-claro-api-unico"
```

El envío del ZIP es asíncrono. Al final el script sigue los logs del backend en
tiempo real; pulsa Ctrl+C para terminar. Consulta también los logs de despliegue
para confirmar que la nueva versión terminó de compilar e iniciar. Una respuesta
de `/health` mientras se despliega podría proceder de la versión anterior.
El registro en vivo se consulta con `az webapp log tail --name <backend>
--resource-group <grupo>`.

Si App Service termina la compilación pero agota el tiempo esperando el sitio,
consulta el diagnóstico de arranque con
`az webapp log startup show --resource-group <grupo> --name <backend>` y los
eventos de despliegue con
`az webapp log deployment show --resource-group <grupo> --name <backend>`.
Las advertencias de Azure CLI sobre Python de 32 bits en Windows son locales
al equipo que despliega; no explican por sí solas que el worker del sitio no
arranque.

La base SQLite queda en `/home/data/users.db`, dentro del almacenamiento
persistente de App Service. Esta opción es para un piloto de una sola instancia;
no escales horizontalmente la aplicación con SQLite compartido. Para escalar,
migra la base de datos a un servicio administrado.
Tras el primer despliegue, abre SSH en el App Service del backend y ejecuta
`python backend/scripts/create_admin.py` para crear la cuenta administrativa
inicial de forma interactiva.

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
