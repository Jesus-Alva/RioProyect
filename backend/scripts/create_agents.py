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
        "conclusión, presenta reportes ejecutivos con tablas Markdown y no inventes "
        "cifras."
    ),
    "Analista": (
        "Analiza y extrae información de facturas, como proveedor, fecha, productos "
        "y total. Nunca inventes cifras. Si no encuentras el dato en la herramienta "
        "de búsqueda, di que no está disponible y que requiere revisión humana."
    ),
    "Gerente": (
        "Apoya la gestión operativa con información de facturas y proveedores. "
        "Resume hallazgos útiles para decisiones y no presentes datos no verificados "
        "como hechos."
    ),
    "Bodega": (
        "Consulta el inventario de la sucursal autorizada en el índice "
        "inventario-index. Usa producto y cantidad como fuente de existencias; no "
        "deduzcas inventario actual a partir de facturas. Mantén cada resultado "
        "identificado por el valor de branch y no mezcles cantidades de sucursales "
        "distintas sin presentarlas por separado."
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
    "conserva y muestra la sucursal branch de cada resultado, separando los "
    "hallazgos de sucursales distintas; "
    "no afirmes que no tienes acceso a facturas si la búsqueda no se ejecutó. "
    "Cuando estén disponibles, incluye el nombre del archivo, proveedor, fecha "
    "y total de la factura. "
    "Si la búsqueda no devuelve documentos, indícalo claramente y no inventes datos."
)

SEARCH_FILTER = (
    "security_id/any(g: search.in(g, '{{userFilter}}')) and "
    "search.in(branch, '{{branchFilter}}', ',')"
)


def build_search_tool(
    search_connection_id: str,
    index_name: str,
    inventory_index_name: str,
    role: str,
) -> AzureAISearchTool:
    indexes = [
        AISearchIndexResource(
            project_connection_id=search_connection_id,
            index_name=index_name,
            query_type=AzureAISearchQueryType.SIMPLE,
            filter=SEARCH_FILTER,
        )
    ]
    if role == "Bodega":
        indexes.append(
            AISearchIndexResource(
                project_connection_id=search_connection_id,
                index_name=inventory_index_name,
                query_type=AzureAISearchQueryType.SIMPLE,
                filter=SEARCH_FILTER,
            )
        )
    return AzureAISearchTool(
        azure_ai_search=AzureAISearchToolResource(indexes=indexes)
    )


def main() -> int:
    load_dotenv()

    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    model_name = os.getenv("FOUNDRY_MODEL_NAME", "gpt-4o")
    search_connection_id = os.getenv("AI_SEARCH_PROJECT_CONNECTION_ID")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "rio-claro-invoices")
    inventory_index_name = os.getenv(
        "AZURE_SEARCH_INVENTORY_INDEX_NAME", "inventario-index"
    )
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
        with DefaultAzureCredential() as credential:
            with AIProjectClient(endpoint=endpoint, credential=credential) as client:
                for role, instructions in AGENT_INSTRUCTIONS.items():
                    search_tool = build_search_tool(
                        search_connection_id,
                        index_name,
                        inventory_index_name,
                        role,
                    )
                    definition = PromptAgentDefinition(
                        model=model_name,
                        instructions=f"{instructions}\n\n{SEARCH_INSTRUCTIONS}",
                        tools=[search_tool],
                        structured_inputs={
                            "userFilter": StructuredInputDefinition(
                                description="Rol operativo autorizado.",
                                required=True,
                                schema={"type": "string"},
                            ),
                            "branchFilter": StructuredInputDefinition(
                                description=(
                                    "Lista separada por comas de sucursales "
                                    "seleccionadas y validadas por el backend."
                                ),
                                required=True,
                                schema={"type": "string"},
                            ),
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
