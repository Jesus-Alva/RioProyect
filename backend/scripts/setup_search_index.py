"""Crea o actualiza el índice seguro de facturas en Azure AI Search."""

import os
from dotenv import load_dotenv
import sys

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchField,
    SearchFieldDataType,
    SearchIndex,
)

load_dotenv() 

def build_index(index_name: str, synonym_map_name: str) -> SearchIndex:
    fields = [
        SearchField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            searchable=False,
            retrievable=True,
        ),
        SearchField(
            name="document_filename",
            type=SearchFieldDataType.String,
            searchable=True,
            filterable=True,
            retrievable=True,
        ),
        SearchField(
            name="vendor_name",
            type=SearchFieldDataType.String,
            searchable=True,
            filterable=True,
            retrievable=True,
        ),
        SearchField(
            name="invoice_content",
            type=SearchFieldDataType.String,
            searchable=True,
            retrievable=True,
        ),
        SearchField(
            name="invoice_total",
            type=SearchFieldDataType.Double,
            filterable=True,
            sortable=True,
            retrievable=True,
        ),
        SearchField(
            name="invoice_date",
            type=SearchFieldDataType.String,
            filterable=True,
            sortable=True,
            retrievable=True,
        ),
        SearchField(
            name="security_id",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
            retrievable=True,
        ),
        SearchField(
            name="product_names",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            synonym_map_names=[synonym_map_name],
            retrievable=True,
        ),
    ]
    return SearchIndex(name=index_name, fields=fields)


def main() -> int:
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        print("Error: configura AZURE_SEARCH_ENDPOINT.", file=sys.stderr)
        return 1

    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "rioclaro-index")
    synonym_map_name = os.getenv(
        "AZURE_SEARCH_SYNONYM_MAP_NAME", "producto-sinonimos"
    )
    credential = DefaultAzureCredential()

    try:
        client = SearchIndexClient(endpoint=endpoint, credential=credential)
        client.create_or_update_index(build_index(index_name, synonym_map_name))
    except AzureError as error:
        print(f"Error de Azure AI Search al crear el índice: {error}", file=sys.stderr)
        return 1
    finally:
        credential.close()

    print(f"Índice '{index_name}' creado o actualizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
