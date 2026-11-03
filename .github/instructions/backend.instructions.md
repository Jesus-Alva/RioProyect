---
name: 'Backend FastAPI Data-First'
description: 'Usar al crear scripts de ingesta o el backend FastAPI.'
applyTo: 'backend/**/*.py'
---
# Reglas del backend
# Reglas de la Capa de Datos (Fase 1)
- **Document Intelligence**: Usa `prebuilt-invoice`. Si la confianza de `InvoiceTotal` o `VendorName` es `< 0.8`, marca el documento como `needs_review` (no lo insertes en el índice).
- **Azure AI Search**: El índice debe tener el campo `security_id` de tipo `Collection(Edm.String)` con `filterable: true` y `retrievable: false`.
- **Sinónimos**: Usa un mapa de sinónimos de Solr para normalizar nombres de productos (ej. "cloro 1l", "cloro litro" => "cloro_litro").
- **Autenticación**: Usa `DefaultAzureCredential` de `azure.identity`. No uses API Keys en el código.
- **Manejo de Errores**: Envuelve las llamadas al SDK en `try/except` e imprime errores claros en consola para el usuario.