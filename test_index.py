import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient

load_dotenv()

search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "rioclaro-index")

print(f"🔍 Conectando al índice: {index_name}...")
credential = DefaultAzureCredential()
client = SearchClient(endpoint=search_endpoint, index_name=index_name, credential=credential)

# Buscar todos los documentos (sin filtros)
results = list(client.search(search_text="*"))

if not results:
    print("❌ No hay ningún documento en el índice. El script seed_data.py no subió la factura correctamente o lo hizo a otro índice.")
else:
    print(f"✅ Se encontraron {len(results)} documentos:")
    for doc in results:
        print("-" * 50)
        print(f"Archivo: {doc.get('document_filename')}")
        print(f"Proveedor: {doc.get('vendor_name')}")
        print(f"Total: {doc.get('invoice_total')}")
        print(f"Roles permitidos (security_id): {doc.get('security_id')}")