import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy.orm import Session

from backend.app.database import User, get_engine, initialize_database
from backend.scripts import create_agents, seed_data, setup_search_index


class MultiBranchDataTests(unittest.TestCase):
    def test_existing_database_migration_expands_legacy_branches_idempotently(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "legacy-users.db"
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        email VARCHAR(254) NOT NULL UNIQUE,
                        password_hash VARCHAR(255) NOT NULL,
                        requested_role VARCHAR(32),
                        requested_branch VARCHAR(32),
                        role VARCHAR(32),
                        branch VARCHAR(32),
                        status VARCHAR(16) NOT NULL,
                        is_active BOOLEAN NOT NULL,
                        created_at DATETIME
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO users
                        (id, email, password_hash, requested_branch, branch,
                         status, is_active)
                    VALUES (1, 'legacy@example.com', 'hash', 'all', 'leon',
                            'active', 1)
                    """
                )
            connection.close()

            get_engine.cache_clear()
            with patch.dict(os.environ, {"AUTH_DATABASE_PATH": str(database_path)}):
                initialize_database()
                initialize_database()
                engine = get_engine(str(database_path))
                with Session(engine) as session:
                    user = session.get(User, 1)
                    self.assertEqual(user.branches, ["leon"])
                    self.assertEqual(user.requested_branches, list(seed_data.BRANCHES))
                with engine.connect() as connection:
                    columns = {
                        row[1]
                        for row in connection.exec_driver_sql(
                            "PRAGMA table_info(users)"
                        )
                    }
                self.assertIn("branches", columns)
                self.assertIn("requested_branches", columns)
                self.assertIn("username", columns)
                self.assertIsNone(user.username)
                engine.dispose()
            get_engine.cache_clear()

    def test_invoice_manifest_requires_an_operational_role_and_specific_branch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "invoice-access.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "invoice.pdf": {
                            "roles": ["analista", "bodega", "analista"],
                            "branch": "leon",
                        }
                    }
                ),
                encoding="utf-8",
            )
            manifest = seed_data.load_access_manifest(manifest_path)
            self.assertEqual(
                manifest["invoice.pdf"],
                {"roles": ["analista", "bodega"], "branch": "leon"},
            )

            for branch, roles in (
                ("all", ["bodega"]),
                ("leon", ["admin"]),
                ("leon", []),
            ):
                manifest_path.write_text(
                    json.dumps(
                        {
                            "invoice.pdf": {
                                "roles": roles,
                                "branch": branch,
                            }
                        }
                    ),
                    encoding="utf-8",
                )
                with self.assertRaises(ValueError):
                    seed_data.load_access_manifest(manifest_path)

    def test_inventory_ingestion_requires_branch_and_bodega_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            inventory_path = Path(temp_dir) / "inventory.json"
            inventory_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "sku-1",
                            "producto": "Arroz",
                            "cantidad": 20,
                            "branch": "zapopan",
                            "roles": ["bodega"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                seed_data.load_inventory_data(inventory_path),
                [
                    {
                        "id": "sku-1",
                        "producto": "Arroz",
                        "cantidad": 20.0,
                        "branch": "zapopan",
                        "security_id": ["bodega"],
                    }
                ],
            )
            inventory_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "sku-1",
                            "producto": "Arroz",
                            "cantidad": 20,
                            "branch": "all",
                            "roles": ["analista"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                seed_data.load_inventory_data(inventory_path)

    def test_invoice_search_document_contains_explicit_branch(self):
        from types import SimpleNamespace

        document = SimpleNamespace(
            fields={
                "VendorName": SimpleNamespace(
                    confidence=0.95, content="Proveedor", value_currency=None
                ),
                "InvoiceTotal": SimpleNamespace(
                    confidence=0.95,
                    content=SimpleNamespace(amount=10.5),
                    value_currency=None,
                ),
            }
        )
        indexed, reasons = seed_data.invoice_to_search_document(
            document,
            "factura.pdf",
            "contenido",
            "hash",
            1,
            ["analista"],
            "queretaro",
        )
        self.assertEqual(reasons, [])
        self.assertEqual(indexed["branch"], "queretaro")
        self.assertEqual(indexed["security_id"], ["analista"])

    def test_seed_script_uploads_invoice_with_manifest_branch_using_azure_mocks(self):
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "invoices"
            input_dir.mkdir()
            (input_dir / "factura.pdf").write_bytes(b"mock invoice")
            manifest_path = root / "invoice-access.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "factura.pdf": {
                            "roles": ["analista"],
                            "branch": "zapopan",
                        }
                    }
                ),
                encoding="utf-8",
            )
            fields = {
                "VendorName": SimpleNamespace(
                    confidence=0.9,
                    content="Proveedor",
                    value_currency=None,
                ),
                "InvoiceTotal": SimpleNamespace(
                    confidence=0.9,
                    content=SimpleNamespace(amount=44),
                    value_currency=None,
                ),
            }
            analyzed_document = SimpleNamespace(fields=fields)
            document_client = Mock()
            document_client.begin_analyze_document.return_value.result.return_value = (
                SimpleNamespace(
                    documents=[analyzed_document],
                    content="mock OCR",
                )
            )
            search_client = Mock()
            search_client.upload_documents.return_value = [
                SimpleNamespace(succeeded=True)
            ]
            credential = Mock()

            environment = {
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://di.invalid",
                "AZURE_SEARCH_ENDPOINT": "https://search.invalid",
                "AZURE_SEARCH_INDEX_NAME": "test-invoices",
                "INVOICE_INPUT_DIR": str(input_dir),
                "INVOICE_ACCESS_MANIFEST_PATH": str(manifest_path),
                "NEEDS_REVIEW_REPORT_PATH": str(root / "needs-review.jsonl"),
            }
            with (
                patch.dict(os.environ, environment),
                patch.object(seed_data, "DefaultAzureCredential", return_value=credential),
                patch.object(
                    seed_data,
                    "DocumentIntelligenceClient",
                    return_value=document_client,
                ),
                patch.object(
                    seed_data,
                    "SearchClient",
                    return_value=search_client,
                ) as search_factory,
            ):
                self.assertEqual(seed_data.main(), 0)

            uploaded = search_client.upload_documents.call_args.kwargs["documents"][0]
            self.assertEqual(uploaded["branch"], "zapopan")
            self.assertEqual(uploaded["security_id"], ["analista"])
            self.assertEqual(
                search_factory.call_args.kwargs["index_name"], "test-invoices"
            )
            credential.close.assert_called_once()

    def test_invoice_below_eighty_percent_confidence_requires_review(self):
        from types import SimpleNamespace

        fields = {
            "VendorName": SimpleNamespace(
                confidence=0.79, content="Proveedor", value_currency=None
            ),
            "InvoiceTotal": SimpleNamespace(
                confidence=0.8,
                content=SimpleNamespace(amount=44),
                value_currency=None,
            ),
        }
        reasons = seed_data.get_review_reasons(fields)
        self.assertEqual(len(reasons), 1)
        self.assertIn("0.79", reasons[0])

    def test_invoice_and_inventory_indexes_are_filterable_by_branch(self):
        invoice_index = setup_search_index.build_index("invoices", "synonyms")
        inventory_index = setup_search_index.build_inventory_index("inventario-index")
        invoice_fields = {field.name: field for field in invoice_index.fields}
        inventory_fields = {field.name: field for field in inventory_index.fields}
        self.assertTrue(invoice_fields["branch"].filterable)
        self.assertTrue(inventory_fields["branch"].filterable)
        self.assertIn("producto", inventory_fields)
        self.assertIn("cantidad", inventory_fields)
        self.assertIn("security_id", inventory_fields)

    def test_setup_search_index_uses_mocks_without_remote_azure_calls(self):
        credential = Mock()
        client = Mock()
        with (
            patch.dict(
                os.environ,
                {
                    "AZURE_SEARCH_ENDPOINT": "https://search.mock",
                    "AZURE_SEARCH_INDEX_NAME": "test-invoices",
                    "AZURE_SEARCH_INVENTORY_INDEX_NAME": "test-inventory",
                },
            ),
            patch.object(
                setup_search_index,
                "DefaultAzureCredential",
                return_value=credential,
            ),
            patch.object(
                setup_search_index,
                "SearchIndexClient",
                return_value=client,
            ) as factory,
        ):
            self.assertEqual(setup_search_index.main(), 0)

        factory.assert_called_once_with(
            endpoint="https://search.mock",
            credential=credential,
        )
        self.assertEqual(client.create_or_update_index.call_count, 2)
        credential.close.assert_called_once()

    def test_agents_use_exact_composite_filter_and_inventory_only_for_bodega(self):
        self.assertEqual(
            create_agents.SEARCH_FILTER,
            "security_id/any(g: search.in(g, '{{userFilter}}')) and "
            "search.in(branch, '{{branchFilter}}', ',')",
        )
        bodega_tool = create_agents.build_search_tool(
            "connection", "invoices", "inventario-index", "Bodega"
        )
        analyst_tool = create_agents.build_search_tool(
            "connection", "invoices", "inventario-index", "Analista"
        )
        self.assertEqual(
            [index.index_name for index in bodega_tool.azure_ai_search.indexes],
            ["inventario-index"],
        )
        self.assertEqual(
            [index.index_name for index in analyst_tool.azure_ai_search.indexes],
            ["invoices"],
        )
        self.assertTrue(
            all(
                index.filter == create_agents.SEARCH_FILTER
                for index in bodega_tool.azure_ai_search.indexes
            )
        )


if __name__ == "__main__":
    unittest.main()
