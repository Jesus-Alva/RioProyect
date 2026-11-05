"""Crea los cinco agentes de Río Claro en Azure AI Foundry."""

import os
import sys

from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AISearchIndexResource,
    AzureAISearchQueryType,
    AzureAISearchTool,
    AzureAISearchToolResource,
    PromptAgentDefinition,
    StructuredInputDefinition,
)
from azure.identity import DefaultAzureCredential


AGENT_INSTRUCTIONS = {
    "Directivo": (
        "Genera reportes ejecutivos y resume tendencias a partir de las facturas "
        "disponibles. Distingue claramente los datos observados de cualquier "
        "conclusión y no inventes cifras."
    ),
    "Analista": (
        "Analiza y extrae información de facturas, como proveedor, fecha, productos "
        "y total. Explica los cálculos y señala cuando falte información."
    ),
    "Gerente": (
        "Apoya la gestión operativa con información de facturas y proveedores. "
        "Resume hallazgos útiles para decisiones y no presentes datos no verificados "
        "como hechos."
    ),
    "Bodega": (
        "Ayuda a consultar productos y datos de facturas relevantes para bodega. "
        "No deduzcas existencias actuales a partir de facturas; indica cuándo el "
        "índice no contiene información de inventario."
    ),
    "TI": (
        "Apoya consultas técnicas sobre los datos disponibles y el uso del sistema. "
        "No reveles credenciales, tokens, configuración sensible ni información "
        "fuera del índice autorizado."
    ),
}

AGENT_NAMES = {
    "Directivo": "rio-directivo",
    "Analista": "rio-analista",
    "Gerente": "rio-gerente",
    "Bodega": "rio-bodega",
    "TI": "rio-ti",
}

SEARCH_INSTRUCTIONS = (
    "Para cualquier consulta sobre facturas o datos indexados, consulta primero "
    "Azure AI Search. Basa la respuesta únicamente en los documentos devueltos; "
    "no afirmes que no tienes acceso a facturas si la búsqueda no se ejecutó. "
    "Cuando estén disponibles, incluye el nombre del archivo, proveedor, fecha "
    "y total de la factura. "
    "Si la búsqueda no devuelve documentos, indícalo claramente y no inventes datos."
)

SEARCH_FILTER = "security_id/any(g: search.in(g, '{{userFilter}}'))"


def main() -> int:
    load_dotenv()

    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    model_name = os.getenv("FOUNDRY_MODEL_NAME", "gpt-4o")
    search_connection_id = os.getenv("AI_SEARCH_PROJECT_CONNECTION_ID")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "rioclaro-index")
    if not endpoint or not search_connection_id:
        missing = [
            name
            for name, value in (
                ("FOUNDRY_PROJECT_ENDPOINT", endpoint),
                ("AI_SEARCH_PROJECT_CONNECTION_ID", search_connection_id),
            )
            if not value
        ]
        print(
            "Error: configura las variables requeridas: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    try:
        search_tool = AzureAISearchTool(
            azure_ai_search=AzureAISearchToolResource(
                indexes=[
                    AISearchIndexResource(
                        project_connection_id=search_connection_id,
                        index_name=index_name,
                        query_type=AzureAISearchQueryType.SIMPLE,
                        filter=SEARCH_FILTER,
                    )
                ]
            )
        )

        with DefaultAzureCredential() as credential:
            with AIProjectClient(endpoint=endpoint, credential=credential) as client:
                for role, instructions in AGENT_INSTRUCTIONS.items():
                    definition = PromptAgentDefinition(
                        model=model_name,
                        instructions=f"{instructions}\n\n{SEARCH_INSTRUCTIONS}",
                        tools=[search_tool],
                        structured_inputs={
                            "userFilter": StructuredInputDefinition(
                                description=(
                                    "Rol autenticado que limita los documentos "
                                    "consultables en Azure AI Search."
                                ),
                                required=True,
                                schema={"type": "string"},
                            )
                        },
                    )
                    agent = client.agents.create_version(
                        agent_name=AGENT_NAMES[role],
                        definition=definition,
                        description=f"Agente de Río Claro para el rol {role}.",
                    )
                    print(f"Agente creado: {role} ({agent.name}, versión {agent.version}).")
    except Exception:
        print(
            "Error: no fue posible crear los agentes en Azure AI Foundry.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
