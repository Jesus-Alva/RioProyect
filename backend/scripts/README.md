# Scripts de la capa de datos

Los scripts usan `DefaultAzureCredential`; no configures API keys en el código.
Antes de ejecutar, inicia sesión con una identidad autorizada para Document
Intelligence y Azure AI Search.

## Variables de entorno

| Variable | Uso | Valor predeterminado |
| --- | --- | --- |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | Endpoint de Document Intelligence | Requerida por `seed_data.py` |
| `AZURE_SEARCH_ENDPOINT` | Endpoint de Azure AI Search | Requerida |
| `AZURE_SEARCH_INDEX_NAME` | Nombre del índice de facturas | `rio-claro-invoices` |
| `AZURE_SEARCH_SYNONYM_MAP_NAME` | Nombre del mapa Solr | `producto-sinonimos` |
| `SYNONYM_FILE_PATH` | Ruta del archivo de reglas Solr | `backend/config/product-synonyms.txt` |
| `INVOICE_INPUT_DIR` | Carpeta local con facturas | `data/invoices` |
| `INVOICE_ACCESS_MANIFEST_PATH` | JSON de roles permitidos por archivo | `backend/config/invoice-access.example.json` |
| `NEEDS_REVIEW_REPORT_PATH` | Reporte JSONL de documentos que requieren revisión | `data/needs_review.jsonl` |

Ejecuta los scripts desde la raíz del repositorio y en este orden:

1. `python backend/scripts/create_synonym_map.py`
2. `python backend/scripts/setup_search_index.py`
3. `python backend/scripts/seed_data.py`

El manifiesto de permisos debe asignar explícitamente una lista no vacía de
roles a cada archivo que se quiera indexar. Usa una copia propia del archivo de
ejemplo y configúrala mediante `INVOICE_ACCESS_MANIFEST_PATH`. Los roles se
guardan en `security_id`, que es filtrable y no recuperable desde resultados de
búsqueda. Los archivos sin asignación no se indexan.

`seed_data.py` registra en el reporte JSONL los documentos en estado
`needs_review`. Si falta la confianza o `VendorName`/`InvoiceTotal` tiene
confianza menor que `0.8`, el documento no se envía al índice. Una confianza
igual a `0.8` pasa el umbral.
