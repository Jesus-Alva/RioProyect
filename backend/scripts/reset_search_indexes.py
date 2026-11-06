"""Recrea los índices de prueba de Río Claro; elimina todos sus documentos."""

import argparse
import os
import sys

from dotenv import load_dotenv
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.scripts.setup_search_index import build_index, build_inventory_index


EXPECTED_INVOICE_INDEX = "rioclaro-index"
EXPECTED_INVENTORY_INDEX = "inventario-index"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Elimina y vuelve a crear vacíos rioclaro-index e inventario-index. "
            "No modifica Blob Storage."
        )
    )
    parser.add_argument(
        "--confirm-reset",
        action="store_true",
        help="Confirma el borrado irreversible de documentos en ambos índices.",
    )
    args = parser.parse_args()
    if not args.confirm_reset:
        print(
            "Operación cancelada. Repite con --confirm-reset para borrar ambos índices.",
            file=sys.stderr,
        )
        return 1

    load_dotenv()
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    invoice_index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "rio-claro-invoices")
    inventory_index_name = os.getenv(
        "AZURE_SEARCH_INVENTORY_INDEX_NAME", "inventario-index"
    )
    synonym_map_name = os.getenv(
        "AZURE_SEARCH_SYNONYM_MAP_NAME", "producto-sinonimos"
    )
    if not endpoint:
        print("Error: configura AZURE_SEARCH_ENDPOINT.", file=sys.stderr)
        return 1
    if (
        invoice_index_name != EXPECTED_INVOICE_INDEX
        or inventory_index_name != EXPECTED_INVENTORY_INDEX
    ):
        print(
            "Error: el reinicio está limitado a "
            f"'{EXPECTED_INVOICE_INDEX}' y '{EXPECTED_INVENTORY_INDEX}'. "
            "Revisa las variables de nombre de índice.",
            file=sys.stderr,
        )
        return 1

    credential = None
    index_client = None
    search_clients = []
    try:
        credential = DefaultAzureCredential()
        index_client = SearchIndexClient(endpoint=endpoint, credential=credential)

        index_definitions = (
            build_index(invoice_index_name, synonym_map_name),
            build_inventory_index(inventory_index_name),
        )
        index_names = (invoice_index_name, inventory_index_name)

        try:
            index_client.get_synonym_map(synonym_map_name)
        except ResourceNotFoundError:
            print(
                f"Error: no existe el mapa de sinónimos '{synonym_map_name}'. "
                "No se modificaron los índices.",
                file=sys.stderr,
            )
            return 1

        existing_indexes = []
        for index_name in index_names:
            try:
                existing_indexes.append(index_client.get_index(index_name))
            except ResourceNotFoundError:
                existing_indexes.append(None)

        for index_name in index_names:
            search_clients.append(
                SearchClient(
                    endpoint=endpoint,
                    index_name=index_name,
                    credential=credential,
                )
            )
        document_counts = [
            search_client.get_document_count()
            for search_client in search_clients
        ]
        print(
            "Documentos existentes antes del reinicio: "
            + ", ".join(
                f"{name}={count}"
                for name, count in zip(index_names, document_counts)
            )
        )
        for search_client in search_clients:
            search_client.close()
        search_clients.clear()

        for index_name, existing_index in zip(index_names, existing_indexes):
            if existing_index is not None:
                index_client.delete_index(index_name)
        for definition in index_definitions:
            index_client.create_or_update_index(definition)

        for index_name in index_names:
            search_clients.append(
                SearchClient(
                    endpoint=endpoint,
                    index_name=index_name,
                    credential=credential,
                )
            )
        empty_counts = [
            search_client.get_document_count()
            for search_client in search_clients
        ]
        if any(empty_counts):
            print(
                "Error: la verificación posterior encontró documentos en los "
                "índices recreados.",
                file=sys.stderr,
            )
            return 1
        print(
            f"Índices recreados vacíos: {invoice_index_name}, "
            f"{inventory_index_name}. Blob Storage no fue modificado."
        )
        return 0
    except AzureError as error:
        print(f"Error de Azure AI Search al reiniciar índices: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(
            f"Error al reiniciar índices ({type(error).__name__}): {error}",
            file=sys.stderr,
        )
        return 1
    finally:
        for resource in (*search_clients, index_client, credential):
            if resource is not None:
                resource.close()


if __name__ == "__main__":
    raise SystemExit(main())
