"""Crea o actualiza el índice y el catálogo de prueba de inventario."""

import os
import sys
from typing import Any

from dotenv import load_dotenv

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.branches import BRANCHES
from backend.scripts.setup_search_index import build_inventory_index


INVENTORY_PRODUCTS = (
    ("cloro 1l", "cloro-1l", 48),
    ("detergente 1kg", "detergente-1kg", 36),
    ("jabon lavatrastes 750ml", "jabon-lavatrastes-750ml", 30),
    ("suavizante 1l", "suavizante-1l", 24),
    ("limpiador multiusos 1l", "limpiador-multiusos-1l", 28),
    ("desinfectante 1l", "desinfectante-1l", 26),
    ("jabon en barra 400g", "jabon-en-barra-400g", 32),
    ("bolsas para basura 90l", "bolsas-para-basura-90l", 20),
    ("papel higienico 4 rollos", "papel-higienico-4-rollos", 40),
    ("servilletas 250 piezas", "servilletas-250-piezas", 22),
    ("esponja con fibra 2 piezas", "esponja-con-fibra-2-piezas", 18),
    ("guantes de limpieza medianos", "guantes-de-limpieza-medianos", 15),
    ("trapeador", "trapeador", 12),
    ("escoba", "escoba", 14),
    ("recogedor", "recogedor", 11),
    ("cubeta 10l", "cubeta-10l", 10),
    ("arroz 1kg", "arroz-1kg", 44),
    ("frijol 1kg", "frijol-1kg", 38),
    ("azucar 1kg", "azucar-1kg", 34),
    ("aceite vegetal 1l", "aceite-vegetal-1l", 27),
    ("harina de trigo 1kg", "harina-de-trigo-1kg", 21),
    ("atun en agua 140g", "atun-en-agua-140g", 31),
    ("leche uht 1l", "leche-uht-1l", 42),
    ("agua natural 1.5l", "agua-natural-15l", 50),
    ("sal de mesa 1kg", "sal-de-mesa-1kg", 19),
    ("cafe soluble 120g", "cafe-soluble-120g", 16),
    ("pasta dental 100ml", "pasta-dental-100ml", 23),
    ("shampoo 750ml", "shampoo-750ml", 17),
    ("jabon corporal 150g", "jabon-corporal-150g", 25),
    ("toallas de papel 2 rollos", "toallas-de-papel-2-rollos", 13),
)

BRANCH_STOCK_OFFSETS = (0, 9, 18, 27, 36)


def build_inventory_documents() -> list[dict[str, Any]]:
    """Construye el catálogo con cantidades e IDs repetibles en cada ejecución."""
    documents = []
    for branch_index, branch in enumerate(BRANCHES):
        branch_offset = BRANCH_STOCK_OFFSETS[branch_index]
        for product_index, (product, product_slug, base_quantity) in enumerate(
            INVENTORY_PRODUCTS
        ):
            variation = (product_index * 5 + branch_index * 2) % 7
            documents.append(
                {
                    "id": f"{branch}-{product_slug}",
                    "producto": product,
                    "cantidad": max(0, base_quantity + branch_offset + variation),
                    "branch": branch,
                    "security_id": ["bodega"],
                }
            )
    return documents


def main() -> int:
    load_dotenv()

    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        print("Error: configura AZURE_SEARCH_ENDPOINT.", file=sys.stderr)
        return 1

    index_name = os.getenv(
        "AZURE_SEARCH_INVENTORY_INDEX_NAME", "inventario-index"
    )
    credential = None
    index_client = None
    search_client = None
    status = 0

    try:
        credential = DefaultAzureCredential()
        index_client = SearchIndexClient(endpoint=endpoint, credential=credential)
        index_client.create_or_update_index(build_inventory_index(index_name))

        search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=credential,
        )
        documents = build_inventory_documents()
        results = search_client.merge_or_upload_documents(documents=documents)
        failures = [
            result
            for result in results or []
            if not getattr(result, "succeeded", False)
        ]
        if failures:
            for failure in failures:
                print(
                    f"Error al cargar {getattr(failure, 'key', 'documento')}: "
                    f"{getattr(failure, 'error_message', 'error de indexación')}",
                    file=sys.stderr,
                )
            status = 1
        elif not results:
            print(
                "Error: Azure AI Search no devolvió resultados de carga.",
                file=sys.stderr,
            )
            status = 1
        else:
            print(
                f"{len(documents)} productos cargados o actualizados en "
                f"'{index_name}' para {len(BRANCHES)} sucursales."
            )
    except AzureError as error:
        print(f"Error de Azure AI Search: {error}", file=sys.stderr)
        status = 1
    except Exception as error:
        print(
            f"Error al preparar o cargar el inventario "
            f"({type(error).__name__}): {error}",
            file=sys.stderr,
        )
        status = 1
    finally:
        for resource in (search_client, index_client, credential):
            if resource is not None:
                try:
                    resource.close()
                except Exception as error:
                    print(
                        f"Error al cerrar un recurso de Azure "
                        f"({type(error).__name__}): {error}",
                        file=sys.stderr,
                    )
                    status = 1

    return status


if __name__ == "__main__":
    raise SystemExit(main())
