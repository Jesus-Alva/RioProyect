import os
import sys
import unittest
from unittest.mock import Mock, patch

from azure.core.exceptions import ResourceNotFoundError

from backend.scripts import reset_search_indexes


class ResetSearchIndexesTests(unittest.TestCase):
    def test_reset_requires_explicit_confirmation_before_connecting(self):
        with (
            patch.object(sys, "argv", ["reset_search_indexes.py"]),
            patch.object(
                reset_search_indexes,
                "DefaultAzureCredential",
            ) as credential_factory,
        ):
            self.assertEqual(reset_search_indexes.main(), 1)

        credential_factory.assert_not_called()

    def test_reset_refuses_unexpected_index_names_before_connecting(self):
        with (
            patch.object(
                sys,
                "argv",
                ["reset_search_indexes.py", "--confirm-reset"],
            ),
            patch.dict(
                os.environ,
                {
                    "AZURE_SEARCH_ENDPOINT": "https://search.mock",
                    "AZURE_SEARCH_INDEX_NAME": "another-index",
                    "AZURE_SEARCH_INVENTORY_INDEX_NAME": "inventario-index",
                },
                clear=True,
            ),
            patch.object(reset_search_indexes, "load_dotenv"),
            patch.object(
                reset_search_indexes,
                "DefaultAzureCredential",
            ) as credential_factory,
        ):
            self.assertEqual(reset_search_indexes.main(), 1)

        credential_factory.assert_not_called()

    def test_reset_recreates_only_requested_indexes_and_verifies_empty(self):
        credential = Mock()
        index_client = Mock()
        search_clients = [Mock(), Mock()]
        verification_clients = [Mock(), Mock()]
        index_client.get_index.return_value = Mock()
        for search_client in (*search_clients, *verification_clients):
            search_client.get_document_count.return_value = 0

        with (
            patch.object(
                sys,
                "argv",
                ["reset_search_indexes.py", "--confirm-reset"],
            ),
            patch.dict(
                os.environ,
                {
                    "AZURE_SEARCH_ENDPOINT": "https://search.mock",
                    "AZURE_SEARCH_INDEX_NAME": "rioclaro-index",
                    "AZURE_SEARCH_INVENTORY_INDEX_NAME": "inventario-index",
                },
                clear=True,
            ),
            patch.object(reset_search_indexes, "load_dotenv"),
            patch.object(
                reset_search_indexes,
                "DefaultAzureCredential",
                return_value=credential,
            ),
            patch.object(
                reset_search_indexes,
                "SearchIndexClient",
                return_value=index_client,
            ),
            patch.object(
                reset_search_indexes,
                "SearchClient",
                side_effect=[*search_clients, *verification_clients],
            ),
        ):
            self.assertEqual(reset_search_indexes.main(), 0)

        index_client.get_synonym_map.assert_called_once_with("producto-sinonimos")
        self.assertEqual(
            [call.args[0] for call in index_client.delete_index.call_args_list],
            ["rioclaro-index", "inventario-index"],
        )
        self.assertEqual(
            [
                call.args[0].name
                for call in index_client.create_or_update_index.call_args_list
            ],
            ["rioclaro-index", "inventario-index"],
        )
        for search_client in (*search_clients, *verification_clients):
            self.assertEqual(search_client.get_document_count.call_count, 1)
            search_client.close.assert_called_once()
        index_client.close.assert_called_once()
        credential.close.assert_called_once()

    def test_missing_synonym_map_prevents_any_index_deletion(self):
        credential = Mock()
        index_client = Mock()
        index_client.get_synonym_map.side_effect = ResourceNotFoundError("missing")

        with (
            patch.object(
                sys,
                "argv",
                ["reset_search_indexes.py", "--confirm-reset"],
            ),
            patch.dict(
                os.environ,
                {
                    "AZURE_SEARCH_ENDPOINT": "https://search.mock",
                    "AZURE_SEARCH_INDEX_NAME": "rioclaro-index",
                    "AZURE_SEARCH_INVENTORY_INDEX_NAME": "inventario-index",
                },
                clear=True,
            ),
            patch.object(reset_search_indexes, "load_dotenv"),
            patch.object(
                reset_search_indexes,
                "DefaultAzureCredential",
                return_value=credential,
            ),
            patch.object(
                reset_search_indexes,
                "SearchIndexClient",
                return_value=index_client,
            ),
        ):
            self.assertEqual(reset_search_indexes.main(), 1)

        index_client.delete_index.assert_not_called()
        index_client.create_or_update_index.assert_not_called()
        index_client.close.assert_called_once()
        credential.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
