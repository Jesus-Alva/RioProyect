import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from backend.app.branches import BRANCHES
from backend.scripts import create_agents, seed_inventory, setup_search_index


class SeedInventoryTests(unittest.TestCase):
    def test_inventory_index_definition_has_required_filterable_fields(self):
        index = setup_search_index.build_inventory_index("inventario-index")
        fields = {field.name: field for field in index.fields}
        shared_index = setup_search_index.build_index("invoices", "synonyms")
        shared_fields = {field.name: field for field in shared_index.fields}

        self.assertEqual(index.name, "inventario-index")
        self.assertTrue(fields["id"].key)
        self.assertEqual(fields["producto"].type, "Edm.String")
        self.assertTrue(fields["producto"].searchable)
        self.assertTrue(fields["sku"].filterable)
        self.assertTrue(fields["categoria"].filterable)
        self.assertEqual(fields["cantidad"].type, "Edm.Double")
        self.assertEqual(fields["branch"].type, "Edm.String")
        self.assertTrue(fields["branch"].filterable)
        self.assertEqual(fields["security_id"].type, "Collection(Edm.String)")
        self.assertTrue(fields["security_id"].filterable)
        self.assertTrue(shared_fields["producto"].searchable)
        self.assertTrue(shared_fields["producto"].retrievable)
        self.assertTrue(shared_fields["sku"].filterable)
        self.assertTrue(shared_fields["categoria"].filterable)
        self.assertEqual(shared_fields["cantidad"].type, "Edm.Double")
        self.assertTrue(shared_fields["cantidad"].retrievable)

    def test_catalog_covers_five_branches_with_stable_classified_secure_documents(self):
        documents = seed_inventory.build_inventory_documents()
        repeated_documents = seed_inventory.build_inventory_documents()
        products = seed_inventory.load_inventory_catalog()
        expected_branches = set(BRANCHES)

        self.assertEqual(len(expected_branches), 5)
        self.assertEqual({document["branch"] for document in documents}, expected_branches)
        self.assertEqual(documents, repeated_documents)
        self.assertEqual(len({document["id"] for document in documents}), len(documents))
        self.assertEqual(len(documents), len(products) * 5)
        self.assertEqual(
            {product["sku"] for product in products},
            {f"PROD-{number:03d}" for number in range(1, len(products) + 1)},
        )
        self.assertEqual(
            {product["categoria"] for product in products},
            {"limpieza", "higiene"},
        )

        for document in documents:
            self.assertEqual(
                set(document),
                {
                    "id",
                    "sku",
                    "categoria",
                    "producto",
                    "cantidad",
                    "branch",
                    "security_id",
                },
            )
            self.assertIsInstance(document["branch"], str)
            self.assertIsInstance(document["cantidad"], int)
            self.assertEqual(document["security_id"], ["bodega"])
            self.assertTrue(document["id"].startswith(f"{document['branch']}-"))

    def test_catalog_contains_only_cleaning_and_hygiene_supplies(self):
        catalog = seed_inventory.load_inventory_catalog()
        self.assertTrue(
            all(
                product["categoria"] in {"limpieza", "higiene"}
                for product in catalog
            )
        )
        self.assertTrue(
            all(
                set(product["cantidad_por_sucursal"]) == set(BRANCHES)
                and all(
                    isinstance(quantity, int) and quantity >= 0
                    for quantity in product["cantidad_por_sucursal"].values()
                )
                for product in catalog
            )
        )

    def test_shared_index_documents_include_inventory_quantity_as_text(self):
        documents = seed_inventory.build_shared_inventory_documents()
        by_id = {document["id"]: document for document in documents}

        content = by_id["guadalajara-prod-001"]["invoice_content"]
        self.assertIn("PROD-001", content)
        self.assertIn("Cloro 1 L", content)
        self.assertIn("cantidad 48", content)
        self.assertIn(
            "sucursal guadalajara",
            content,
        )

    def test_seed_loads_catalog_and_closes_mocked_resources(self):
        credential = Mock()
        index_client = Mock()
        invoice_search_client = Mock()
        inventory_search_client = Mock()
        documents = seed_inventory.build_inventory_documents()
        upload_results = [
            Mock(succeeded=True, key=document["id"], error_message=None)
            for document in documents
        ]
        invoice_search_client.merge_or_upload_documents.return_value = upload_results
        inventory_search_client.merge_or_upload_documents.return_value = upload_results

        with (
            patch.dict(
                os.environ,
                {
                    "AZURE_SEARCH_ENDPOINT": "https://search.mock",
                    "AZURE_SEARCH_INVENTORY_INDEX_NAME": "test-inventory",
                    "AZURE_SEARCH_INDEX_NAME": "test-invoices",
                },
            ),
            patch.object(
                seed_inventory,
                "DefaultAzureCredential",
                return_value=credential,
            ),
            patch.object(
                seed_inventory,
                "SearchIndexClient",
                return_value=index_client,
            ) as index_factory,
            patch.object(
                seed_inventory,
                "SearchClient",
                side_effect=[invoice_search_client, inventory_search_client],
            ) as search_factory,
        ):
            self.assertEqual(seed_inventory.main(), 0)

        index_factory.assert_called_once_with(
            endpoint="https://search.mock",
            credential=credential,
        )
        self.assertEqual(index_client.create_or_update_index.call_count, 2)
        self.assertEqual(
            [
                call.args[0].name
                for call in index_client.create_or_update_index.call_args_list
            ],
            ["test-invoices", "test-inventory"],
        )
        self.assertEqual(
            search_factory.call_args_list[0].kwargs,
            {
                "endpoint": "https://search.mock",
                "index_name": "test-invoices",
                "credential": credential,
            },
        )
        self.assertEqual(
            search_factory.call_args_list[1].kwargs["index_name"],
            "test-inventory",
        )
        invoice_search_client.merge_or_upload_documents.assert_called_once_with(
            documents=seed_inventory.build_shared_inventory_documents()
        )
        inventory_search_client.merge_or_upload_documents.assert_called_once_with(
            documents=documents
        )
        invoice_search_client.close.assert_called_once()
        inventory_search_client.close.assert_called_once()
        index_client.close.assert_called_once()
        credential.close.assert_called_once()

    def test_seed_returns_failure_for_unsuccessful_upload_and_closes_resources(self):
        credential = Mock()
        index_client = Mock()
        invoice_search_client = Mock()
        inventory_search_client = Mock()
        invoice_search_client.merge_or_upload_documents.return_value = [
            Mock(succeeded=True, key="guadalajara-prod-001", error_message=None)
        ]
        inventory_search_client.merge_or_upload_documents.return_value = [
            Mock(succeeded=False, key="guadalajara-prod-001", error_message="failed")
        ]

        with (
            patch.dict(
                os.environ,
                {"AZURE_SEARCH_ENDPOINT": "https://search.mock"},
            ),
            patch.object(
                seed_inventory,
                "DefaultAzureCredential",
                return_value=credential,
            ),
            patch.object(
                seed_inventory,
                "SearchIndexClient",
                return_value=index_client,
            ),
            patch.object(
                seed_inventory,
                "SearchClient",
                side_effect=[invoice_search_client, inventory_search_client],
            ),
        ):
            self.assertEqual(seed_inventory.main(), 1)

        invoice_search_client.close.assert_called_once()
        inventory_search_client.close.assert_called_once()
        index_client.close.assert_called_once()
        credential.close.assert_called_once()


class AgentSearchToolTests(unittest.TestCase):
    def test_serialized_bodega_definition_uses_single_shared_search_index(self):
        definition = create_agents.build_agent_definition(
            role="Bodega",
            model_name="gpt-4o",
            search_connection_id="search-connection",
            index_name="invoices",
        )
        serialized = definition.as_dict()
        tools = serialized["tools"]

        self.assertEqual(len(tools), 1)
        self.assertEqual(
            tools[0]["azure_ai_search"]["indexes"][0]["index_name"],
            "invoices",
        )
        for tool in tools:
            indexes = tool["azure_ai_search"]["indexes"]
            self.assertEqual(len(indexes), 1)
            self.assertEqual(
                indexes[0]["filter"],
                create_agents.SEARCH_FILTER,
            )
            self.assertEqual(
                indexes[0]["project_connection_id"],
                "search-connection",
            )
        self.assertTrue(
            serialized["structured_inputs"]["userFilter"]["required"]
        )
        self.assertTrue(
            serialized["structured_inputs"]["branchFilter"]["required"]
        )

    def test_non_bodega_agent_receives_only_invoice_tool(self):
        definition = create_agents.build_agent_definition(
            role="Analista",
            model_name="gpt-4o",
            search_connection_id="search-connection",
            index_name="invoices",
        )
        tools = definition.as_dict()["tools"]

        self.assertEqual(len(tools), 1)
        indexes = tools[0]["azure_ai_search"]["indexes"]
        self.assertEqual(len(indexes), 1)
        self.assertEqual(indexes[0]["index_name"], "invoices")

    def test_create_agents_uses_shared_index_for_bodega_with_mocked_foundry(self):
        credential = MagicMock()
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.agents.list_versions.return_value = []
        client.agents.create_version.side_effect = lambda **kwargs: Mock(
            name=kwargs["agent_name"],
            version=1,
        )

        with (
            patch.dict(
                os.environ,
                {
                    "FOUNDRY_PROJECT_ENDPOINT": "https://foundry.mock",
                    "AI_SEARCH_PROJECT_CONNECTION_ID": "search-connection",
                },
                clear=True,
            ),
            patch.object(
                create_agents,
                "DefaultAzureCredential",
                return_value=credential,
            ),
            patch.object(create_agents, "load_dotenv"),
            patch.object(
                create_agents,
                "AIProjectClient",
                return_value=client,
            ),
        ):
            self.assertEqual(create_agents.main(), 0)

        self.assertEqual(client.agents.create_version.call_count, 5)
        definitions = {
            call.kwargs["agent_name"]: call.kwargs["definition"].as_dict()
            for call in client.agents.create_version.call_args_list
        }
        bodega_tools = definitions["rio-bodega"]["tools"]
        self.assertEqual(len(bodega_tools), 1)
        self.assertEqual(
            bodega_tools[0]["azure_ai_search"]["indexes"][0]["index_name"],
            "rio-claro-invoices",
        )
        for tool in bodega_tools:
            self.assertEqual(len(tool["azure_ai_search"]["indexes"]), 1)
        self.assertTrue(
            all(
                len(definition["tools"]) == 1
                and definition["tools"][0]["azure_ai_search"]["indexes"][0][
                    "index_name"
                ]
                == "rio-claro-invoices"
                for agent_name, definition in definitions.items()
                if agent_name != "rio-bodega"
            )
        )
        client.__exit__.assert_called_once()
        credential.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
