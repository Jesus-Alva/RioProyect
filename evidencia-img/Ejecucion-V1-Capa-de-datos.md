## Paso 1
1. crea un entorno virtual e instala las librerías para que el Constructor pueda probar el código:
```bash
python -m venv venv
.\venv\Scripts\activate
pip install azure-identity azure-ai-documentintelligence azure-search-documents
```

2. @Arquitecto Lee las instrucciones. Necesito el plan detallado para crear los 3 scripts de la Fase 1 en la carpeta backend/scripts/. Tenemos que cumplir con la regla de confianza < 0.8 y el campo security_id.

3. @Constructor Implementa el plan aprobado para crear los scripts de Python.

### Hasta aqui se generan archivos que usaremos para crear físicamente el índice en Azure y probar la extracción de una factura.

## Paso 2

1. Confiurar variables de entorno

```bash
$env:SEARCH_ENDPOINT="https://srch-rioclaro.search.windows.net"
$env:SEARCH_INDEX_NAME="rioclaro-index"
$env:DOC_INTEL_ENDPOINT="https://di-rioclaro-facturas.cognitiveservices.azure.com/"
$env:STORAGE_ACCOUNT_NAME="strioclarofacturas"
```
