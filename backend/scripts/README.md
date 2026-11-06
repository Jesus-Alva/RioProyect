# Scripts de la capa de datos

Los scripts usan `DefaultAzureCredential`; no configures API keys en el código.
Antes de ejecutar, inicia sesión con una identidad autorizada para Document
Intelligence y Azure AI Search.

## Preparar el entorno Python

Desde la raíz del repositorio, crea y activa un entorno virtual e instala las
dependencias del backend:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Ejecuta los scripts con ese entorno activo. Si no quieres activarlo, invoca
explícitamente `.\.venv\Scripts\python.exe`; por ejemplo:

```powershell
.\.venv\Scripts\python.exe backend\scripts\create_agents.py
```

## Variables de entorno

| Variable | Uso | Valor predeterminado |
| --- | --- | --- |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | Endpoint de Document Intelligence | Requerida por `seed_data.py` |
| `AZURE_SEARCH_ENDPOINT` | Endpoint de Azure AI Search | Requerida |
| `AZURE_SEARCH_INDEX_NAME` | Nombre del índice de facturas | `rio-claro-invoices` |
| `AZURE_SEARCH_INVENTORY_INDEX_NAME` | Índice de inventario | `inventario-index` |
| `AZURE_SEARCH_SYNONYM_MAP_NAME` | Nombre del mapa Solr | `producto-sinonimos` |
| `SYNONYM_FILE_PATH` | Ruta del archivo de reglas Solr | `backend/config/product-synonyms.txt` |
| `INVOICE_INPUT_DIR` | Carpeta local con facturas | `data/invoices` |
| `INVOICE_ACCESS_MANIFEST_PATH` | Manifiesto de acceso por archivo | `backend/config/invoice-access.example.json` |
| `NEEDS_REVIEW_REPORT_PATH` | Reporte JSONL de documentos que requieren revisión | `data/needs_review.jsonl` |
| `INVENTORY_DATA_PATH` | JSON opcional para cargar inventario | Sin valor (no ingesta inventario) |

Ejecuta los scripts desde la raíz del repositorio y en este orden:

1. `python backend/scripts/create_synonym_map.py`
2. `python backend/scripts/setup_search_index.py`
3. `python backend/scripts/seed_data.py`

El manifiesto de factura es un objeto JSON cuyas claves son nombres de archivo.
Cada valor debe tener exactamente `roles` (lista no vacía de los roles
operativos `directivo`, `analista`, `gerente`, `bodega` o `ti`) y `branch` (una
de `guadalajara`, `zapopan`, `leon`, `queretaro` o `aguascalientes`). No uses
`all` en un documento: el manifiesto siempre concede acceso a una sucursal
concreta. Por ejemplo:

```json
{
  "factura_001.pdf": {
    "roles": ["analista", "gerente", "directivo"],
    "branch": "leon"
  }
}
```

Usa una copia propia de `backend/config/invoice-access.example.json` y
configúrala mediante `INVOICE_ACCESS_MANIFEST_PATH`. Los roles se guardan en
`security_id`; `branch` se guarda por separado y es filtrable. Los archivos sin
una entrada válida no se indexan.
La ingesta guarda el texto OCR y un resumen de campos en `invoice_content`,
utilizado por el agente como contenido de búsqueda. Si el índice ya existía,
actualízalo y vuelve a ejecutar `seed_data.py` para completar ese campo en los
documentos existentes.

`seed_data.py` registra en el reporte JSONL los documentos en estado
`needs_review`. Si falta la confianza o `VendorName`/`InvoiceTotal` tiene
confianza menor que `0.8`, el documento no se envía al índice. Una confianza
igual a `0.8` pasa el umbral.

El índice de facturas y el índice `inventario-index` incluyen `branch`
filtrable y `security_id` de tipo colección. `setup_search_index.py` crea o
actualiza ambos índices; es una operación remota. Debe ejecutarse con una
identidad Azure autorizada después de revisar los nombres configurados.

Para cargar inventario, `INVENTORY_DATA_PATH` debe apuntar a una lista JSON; cada
fila contiene exactamente `id`, `producto`, `cantidad`, `branch` y `roles`.
`branch` debe ser una sucursal concreta y `roles` debe incluir `bodega`. El
ejemplo está en `backend/config/inventory.example.json`.

La migración SQLite de arranque agrega `branches` y `requested_branches` como
listas JSON, migrando de forma idempotente los campos escalares anteriores.
Los usuarios existentes con una sucursal conservan esa asignación; los que
tenían `all` reciben la lista explícita de las cinco sucursales, y las cuentas
sin asignación válida permanecen bloqueadas hasta intervención administrativa.
Los tokens antiguos con una claim escalar dejan de ser válidos y requieren
iniciar sesión de nuevo. El registro solo solicita una sucursal concreta;
Admin asigna una o más sucursales.

`POST /api/chat` recibe `branches` con una o más sucursales seleccionadas. La
selección del cliente no autoriza el acceso: el backend la valida como subconjunto
de `branches` en SQLite antes de construir el filtro de Azure AI Search.
`branchFilter` se entrega como lista separada por comas a
`search.in(branch, '{{branchFilter}}', ',')`. Los documentos y resultados de
inventario conservan su propio `branch` escalar para no mezclar su clasificación.

### Probar ingesta de una factura en una sucursal

Desde PowerShell en la raíz del repositorio, selecciona una sucursal concreta
en el manifiesto propio. Este ejemplo procesa `data\invoices\factura_001.pdf`:

```powershell
$branch = "leon"
$manifest = @{
    "factura_001.pdf" = @{
        roles = @("analista", "gerente", "directivo")
        branch = $branch
    }
} | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText(
    (Join-Path $PWD "backend\config\invoice-access.json"),
    $manifest,
    [System.Text.UTF8Encoding]::new($false)
)
$env:AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = "<endpoint-document-intelligence>"
$env:AZURE_SEARCH_ENDPOINT = "<endpoint-azure-ai-search>"
$env:AZURE_SEARCH_INDEX_NAME = "rio-claro-invoices"
$env:INVOICE_INPUT_DIR = (Resolve-Path ".\data\invoices").Path
$env:INVOICE_ACCESS_MANIFEST_PATH = (Resolve-Path ".\backend\config\invoice-access.json").Path
$env:NEEDS_REVIEW_REPORT_PATH = (Join-Path $PWD "data\needs_review.jsonl")
.\venv\Scripts\python.exe backend\scripts\seed_data.py
```

Los endpoints se deben tomar del entorno autorizado; no guardes sus valores ni
credenciales en el repositorio. Antes de ejecutar la ingesta, crea/actualiza los
índices una vez con `.\venv\Scripts\python.exe backend\scripts\setup_search_index.py`
y verifica que `DefaultAzureCredential` use una identidad con acceso a ambos
servicios. En una ejecución indexable, el resultado debe indicar
`factura_001.pdf: indexada correctamente.` y en Search verificar que el
documento contiene `branch=leon` y `security_id` con los roles del manifiesto.
Si el OCR tiene confianza insuficiente, debe aparecer como `needs_review` y no
subirse; confirma el motivo en `data\needs_review.jsonl`.
