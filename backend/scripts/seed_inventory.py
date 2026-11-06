"""Crea o actualiza el índice y el catálogo de prueba de inventario."""

import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
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
from backend.scripts.setup_search_index import (
    build_index,
    build_inventory_index,
)


CATALOG_PATH = Path(PROJECT_ROOT) / "backend" / "data" / "inventario_prueba.json"
SKU_PATTERN = re.compile(r"PROD-\d{3}\Z")
ALLOWED_CATEGORIES = {"limpieza", "higiene"}


def load_inventory_catalog(
    catalog_path: str | Path = CATALOG_PATH,
) -> list[dict[str, Any]]:
    """Carga y valida el catálogo explícitamente ficticio para pruebas."""
    with Path(catalog_path).open(encoding="utf-8") as catalog_file:
        catalog = json.load(catalog_file)

    if (
        not isinstance(catalog, dict)
        or set(catalog) != {"aviso", "productos"}
        or not isinstance(catalog["aviso"], str)
        or "SIMULADOS PARA PRUEBAS" not in catalog["aviso"]
        or not isinstance(catalog["productos"], list)
        or not catalog["productos"]
    ):
        raise ValueError(
            "El catálogo debe identificarse como datos simulados y contener productos."
        )

    products = catalog["productos"]
    skus: set[str] = set()
    names: set[str] = set()
    for product in products:
        if (
            not isinstance(product, dict)
            or set(product)
            != {
                "sku",
                "categoria",
                "producto",
                "precio_unitario_prueba_mxn",
                "cantidad_por_sucursal",
            }
            or not isinstance(product["sku"], str)
            or not SKU_PATTERN.fullmatch(product["sku"])
            or product["sku"] in skus
            or not isinstance(product["producto"], str)
            or not product["producto"].strip()
            or not isinstance(product["categoria"], str)
            or product["categoria"] not in ALLOWED_CATEGORIES
            or product["producto"].casefold() in names
            or not isinstance(product["cantidad_por_sucursal"], dict)
            or set(product["cantidad_por_sucursal"]) != set(BRANCHES)
        ):
            raise ValueError(
                "Cada producto debe tener SKU único, nombre y cantidades para "
                "las cinco sucursales."
            )

        try:
            price = Decimal(product["precio_unitario_prueba_mxn"])
        except (InvalidOperation, TypeError):
            raise ValueError("El precio de prueba debe ser un decimal válido.") from None
        if not price.is_finite() or price <= 0:
            raise ValueError("El precio de prueba debe ser positivo y finito.")

        for quantity in product["cantidad_por_sucursal"].values():
            if (
                not isinstance(quantity, int)
                or isinstance(quantity, bool)
                or quantity < 0
            ):
                raise ValueError("Las cantidades deben ser enteros no negativos.")

        skus.add(product["sku"])
        names.add(product["producto"].casefold())
    return products


def build_inventory_documents(
    catalog_path: str | Path = CATALOG_PATH,
) -> list[dict[str, Any]]:
    """Construye documentos repetibles desde el catálogo local de prueba."""
    documents = []
    for product in load_inventory_catalog(catalog_path):
        for branch in BRANCHES:
            documents.append(
                {
                    "id": f"{branch}-{product['sku'].lower()}",
                    "sku": product["sku"],
                    "categoria": product["categoria"],
                    "producto": product["producto"],
                    "cantidad": product["cantidad_por_sucursal"][branch],
                    "branch": branch,
                    "security_id": ["bodega"],
                }
            )
    return documents


def build_shared_inventory_documents(
    catalog_path: str | Path = CATALOG_PATH,
) -> list[dict[str, Any]]:
    """Incluye la cantidad en texto para que Foundry la reciba en sus resultados."""
    return [
        {
            **document,
            "invoice_content": (
                f"Inventario: SKU {document['sku']}; producto {document['producto']}; "
                f"cantidad {document['cantidad']}; sucursal {document['branch']}."
            ),
        }
        for document in build_inventory_documents(catalog_path)
    ]


def main() -> int:
    load_dotenv()

    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        print("Error: configura AZURE_SEARCH_ENDPOINT.", file=sys.stderr)
        return 1

    inventory_index_name = os.getenv(
        "AZURE_SEARCH_INVENTORY_INDEX_NAME", "inventario-index"
    )
    invoice_index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "rio-claro-invoices")
    synonym_map_name = os.getenv(
        "AZURE_SEARCH_SYNONYM_MAP_NAME", "producto-sinonimos"
    )
    if invoice_index_name == inventory_index_name:
        print(
            "Error: los índices de facturas e inventario deben ser distintos.",
            file=sys.stderr,
        )
        return 1

    credential = None
    index_client = None
    search_clients = []
    status = 0

    try:
        credential = DefaultAzureCredential()
        index_client = SearchIndexClient(endpoint=endpoint, credential=credential)
        index_client.create_or_update_index(
            build_index(invoice_index_name, synonym_map_name)
        )
        index_client.create_or_update_index(
            build_inventory_index(inventory_index_name)
        )
        for target_index in (invoice_index_name, inventory_index_name):
            search_clients.append(
                SearchClient(
                    endpoint=endpoint,
                    index_name=target_index,
                    credential=credential,
                )
            )
        inventory_documents = build_inventory_documents()
        uploads = (
            (invoice_index_name, build_shared_inventory_documents()),
            (inventory_index_name, inventory_documents),
        )
        for (target_index, documents), search_client in zip(
            uploads,
            search_clients,
        ):
            results = search_client.merge_or_upload_documents(
                documents=documents
            )
            failures = [
                result
                for result in results or []
                if not getattr(result, "succeeded", False)
            ]
            if failures:
                for failure in failures:
                    print(
                        f"Error al cargar {getattr(failure, 'key', 'documento')} "
                        f"en '{target_index}': "
                        f"{getattr(failure, 'error_message', 'error de indexación')}",
                        file=sys.stderr,
                    )
                status = 1
            elif not results:
                print(
                    f"Error: Azure AI Search no devolvió resultados de carga "
                    f"para '{target_index}'.",
                    file=sys.stderr,
                )
                status = 1
            else:
                print(
                    f"{len(documents)} productos cargados o actualizados en "
                    f"'{target_index}' para {len(BRANCHES)} sucursales."
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
        for resource in (*search_clients, index_client, credential):
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
