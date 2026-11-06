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
        "Consulta el índice autorizado de facturas e inventario. Los registros "
        "de inventario incluyen producto y cantidad en el texto del documento; "
        "usa esa cantidad como fuente de existencias y nunca deduzcas inventario "
        "actual a partir de facturas. "
        "Los registros de factura tienen proveedor, fecha y total y son una fuente "
        "distinta del inventario. Mantén cada resultado identificado por branch "
        "y no mezcles cantidades de sucursales distintas sin presentarlas por "
        "separado."
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
    "Para cualquier consulta sobre facturas, inventario o datos indexados, "
    "consulta primero Azure AI Search usando la herramienta correspondiente. "
    "Basa la respuesta únicamente en los documentos devueltos; conserva y muestra "
    "la sucursal branch de cada resultado, separando los hallazgos de sucursales "
    "distintas. No afirmes que no tienes acceso a un índice si la búsqueda no se "
    "ejecutó. Cuando estén disponibles, incluye el nombre del archivo, proveedor, "
    "fecha y total de cada factura. Si la búsqueda no devuelve documentos, "
    "indícalo claramente y no inventes datos."
)

SEARCH_FILTER = (
    "security_id/any(g: search.in(g, '{{userFilter}}')) and "
    "search.in(branch, '{{branchFilter}}', ',')"
)


def build_agent_instructions(role: str) -> str:
    return f"{AGENT_INSTRUCTIONS[role]}\n\n{SEARCH_INSTRUCTIONS}"


def build_search_tool(
    search_connection_id: str,
    index_name: str,
) -> AzureAISearchTool:
    return AzureAISearchTool(
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


def build_search_tools(
    search_connection_id: str,
    index_name: str,
) -> list[AzureAISearchTool]:
    return [build_search_tool(search_connection_id, index_name)]


def build_agent_definition(
    role: str,
    model_name: str,
    search_connection_id: str,
    index_name: str,
) -> PromptAgentDefinition:
    return PromptAgentDefinition(
        model=model_name,
        instructions=build_agent_instructions(role),
        tools=build_search_tools(
            search_connection_id,
            index_name,
        ),
        structured_inputs={
            "userFilter": StructuredInputDefinition(
                description="Rol operativo autorizado.",
                required=True,
                schema={"type": "string"},
            ),
            "branchFilter": StructuredInputDefinition(
                description=(
                    "Lista separada por comas de sucursales seleccionadas "
                    "y validadas por el backend."
                ),
                required=True,
                schema={"type": "string"},
            ),
        },
    )


def has_required_inputs(
    client: AIProjectClient,
    agent_name: str,
    required_index_names: list[str] | None = None,
    required_instructions: str | None = None,
) -> bool:
    versions = iter(client.agents.list_versions(agent_name=agent_name))
    latest = next(versions, None)
    if latest is None:
        return False
    details = client.agents.get_version(
        agent_name=agent_name,
        agent_version=str(latest.version),
    )
    definition = details.definition
    if (
        required_instructions is not None
        and getattr(definition, "instructions", None) != required_instructions
    ):
        return False
    inputs = getattr(definition, "structured_inputs", None) or {}
    if not {"userFilter", "branchFilter"}.issubset(inputs):
        return False
    if required_index_names is None:
        return True

    tools = getattr(definition, "tools", None) or []
    if len(tools) != 1:
        return False
    configured_indexes = []
    for tool in tools:
        search_resource = getattr(tool, "azure_ai_search", None)
        if search_resource is None and isinstance(tool, dict):
            search_resource = tool.get("azure_ai_search")
        indexes = (
            getattr(search_resource, "indexes", None)
            if search_resource is not None
            else None
        )
        if indexes is None and isinstance(search_resource, dict):
            indexes = search_resource.get("indexes")
        if not indexes:
            return False
        for index in indexes:
            index_name = getattr(index, "index_name", None)
            if index_name is None and isinstance(index, dict):
                index_name = index.get("index_name")
            if not index_name:
                return False
            configured_indexes.append(index_name)
    return configured_indexes == required_index_names


def main() -> int:
    load_dotenv()

    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    model_name = os.getenv("FOUNDRY_MODEL_NAME", "gpt-4o")
    search_connection_id = os.getenv("AI_SEARCH_PROJECT_CONNECTION_ID")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "rio-claro-invoices")
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

    failed = False
    try:
        with DefaultAzureCredential() as credential:
            with AIProjectClient(endpoint=endpoint, credential=credential) as client:
                for role in AGENT_INSTRUCTIONS:
                    agent_name = AGENT_NAMES[role]
                    try:
                        if has_required_inputs(
                            client,
                            agent_name,
                            [index_name],
                            build_agent_instructions(role),
                        ):
                            print(f"Agente vigente, sin cambios: {agent_name}.")
                            continue
                        definition = build_agent_definition(
                            role=role,
                            model_name=model_name,
                            search_connection_id=search_connection_id,
                            index_name=index_name,
                        )
                        agent = client.agents.create_version(
                            agent_name=agent_name,
                            definition=definition,
                            description=f"Agente de Río Claro para el rol {role}.",
                        )
                        print(
                            f"Agente creado: {role} "
                            f"({agent.name}, versión {agent.version})."
                        )
                    except Exception as error:
                        failed = True
                        print(
                            f"Error al actualizar {agent_name}: "
                            f"{type(error).__name__}: {error}",
                            file=sys.stderr,
                        )
    except Exception:
        print(
            "Error: no fue posible conectar con Azure AI Foundry.",
            file=sys.stderr,
        )
        return 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
