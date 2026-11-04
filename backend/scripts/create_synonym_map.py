"""Crea o actualiza el mapa de sinónimos de productos en Azure AI Search."""

import os
from dotenv import load_dotenv
import sys
from pathlib import Path

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SynonymMap

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SYNONYM_FILE = PROJECT_ROOT / "backend" / "config" / "product-synonyms.txt"


def load_synonym_rules(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo de sinónimos: {path}")

    rules = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not rules:
        raise ValueError(f"El archivo de sinónimos no contiene reglas: {path}")

    for line_number, rule in enumerate(rules, start=1):
        if "=>" not in rule and "," not in rule:
            raise ValueError(
                f"Regla de sinónimos inválida en línea {line_number}: {rule}"
            )
        if any(not part.strip() for part in rule.replace("=>", ",").split(",")):
            raise ValueError(
                f"Regla de sinónimos incompleta en línea {line_number}: {rule}"
            )

    return "\n".join(rules)


def main() -> int:
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        print("Error: configura AZURE_SEARCH_ENDPOINT.", file=sys.stderr)
        return 1

    map_name = os.getenv("AZURE_SEARCH_SYNONYM_MAP_NAME", "producto-sinonimos")
    synonym_path = Path(os.getenv("SYNONYM_FILE_PATH", str(DEFAULT_SYNONYM_FILE)))

    try:
        synonym_rules = load_synonym_rules(synonym_path)
    except (OSError, ValueError) as error:
        print(f"Error al cargar sinónimos: {error}", file=sys.stderr)
        return 1

    credential = DefaultAzureCredential()
    try:
        client = SearchIndexClient(endpoint=endpoint, credential=credential)
        client.create_or_update_synonym_map(
            SynonymMap(name=map_name, synonyms=synonym_rules)
        )
    except AzureError as error:
        print(f"Error de Azure AI Search al guardar el mapa: {error}", file=sys.stderr)
        return 1
    finally:
        credential.close()

    print(f"Mapa de sinónimos '{map_name}' creado o actualizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
