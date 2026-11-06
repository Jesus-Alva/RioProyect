import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from azure.core.exceptions import AzureError
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from backend.app import main
from backend.app.database import (
    InvoiceUpload,
    User,
    get_database_path,
    get_engine,
    initialize_database,
)
from backend.app.invoice_upload import generate_invoice_filename
from backend.app.security import hash_password


def analyzed_invoice(vendor="Proveedor de prueba", confidence=0.95):
    fields = {
        "VendorName": SimpleNamespace(content=vendor, confidence=confidence),
        "InvoiceDate": SimpleNamespace(content="2026-11-06", confidence=0.99),
        "InvoiceTotal": SimpleNamespace(content="123.45", confidence=confidence),
    }
    return SimpleNamespace(fields=fields)


class InvoiceUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.database_path = Path(cls.temp_directory.name) / "invoices.db"
        cls.environment = patch.dict(
            os.environ,
            {
                "JWT_SECRET": "test-key-not-used-outside-tests-123456789",
                "JWT_ISSUER": "test-api",
                "JWT_AUDIENCE": "test-web",
                "AUTH_DATABASE_PATH": str(cls.database_path),
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://document.invalid",
                "AZURE_SEARCH_ENDPOINT": "https://search.invalid",
                "AZURE_STORAGE_BLOB_URL": "https://storage.invalid",
            },
        )
        cls.environment.start()
        cls.client = TestClient(main.app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        get_engine(str(cls.database_path)).dispose()
        get_engine.cache_clear()
        cls.environment.stop()
        cls.temp_directory.cleanup()

    def setUp(self):
        with Session(get_engine(str(get_database_path()))) as session:
            session.execute(delete(InvoiceUpload))
            session.execute(delete(User))
            session.commit()

    def test_blob_lifecycle_policy_targets_invoice_prefix_for_90_days(self):
        policy_path = (
            Path(__file__).parents[2]
            / "backend"
            / "config"
            / "blob-lifecycle-policy.example.json"
        )
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        rule = policy["rules"][0]["definition"]

        self.assertEqual(
            rule["filters"]["prefixMatch"], ["facturas-raw/invoices/"]
        )
        self.assertEqual(
            rule["actions"]["baseBlob"]["delete"][
                "daysAfterModificationGreaterThan"
            ],
            90,
        )
        self.assertNotIn("blobIndexMatch", rule["filters"])

    def create_user(self, role="analista", branches=("guadalajara",)):
        with Session(get_engine(str(get_database_path()))) as session:
            user = User(
                username=f"{role}_user",
                email=f"{role}@example.com",
                password_hash=hash_password("valid-password-123"),
                role=role,
                branches=list(branches),
                status="active",
                is_active=True,
            )
            session.add(user)
            session.commit()
            return user.id

    def token_for(self, role="analista", branches=("guadalajara",)):
        self.create_user(role, branches)
        response = self.client.post(
            "/api/auth/login",
            json={
                "email": f"{role}@example.com",
                "password": "valid-password-123",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def create_review(
        self,
        branch="guadalajara",
        blob_name="invoices/test.pdf",
        uploaded_by=None,
    ):
        if uploaded_by is None:
            with Session(get_engine(str(get_database_path()))) as session:
                user = session.scalar(
                    select(User).where(User.email == "analista@example.com")
                )
            uploaded_by = (
                user.id if user else self.create_user(branches=(branch,))
            )
        with Session(get_engine(str(get_database_path()))) as session:
            upload = InvoiceUpload(
                document_hash="c" * 64,
                original_filename="test.pdf",
                generated_filename=f"FACTURA_{branch}_test.pdf",
                content_type="application/pdf",
                branch=branch,
                status="needs_review",
                uploaded_by=uploaded_by,
                review_reasons='["Requiere revisión"]',
                blob_name=blob_name,
            )
            session.add(upload)
            session.commit()
            return upload.id

    def azure_mocks(self, document, exact_matches=(), probable_matches=()):
        credential = SimpleNamespace(close=Mock())
        document_client = Mock()
        document_client.begin_analyze_document.return_value.result.return_value = (
            SimpleNamespace(documents=[document], content="Texto OCR de prueba")
        )
        search_client = Mock()
        search_client.search.side_effect = [exact_matches, probable_matches]
        search_client.upload_documents.return_value = [
            SimpleNamespace(succeeded=True)
        ]
        container = Mock()
        container.exists.return_value = True
        blob_service = Mock()
        blob_service.get_container_client.return_value = container
        return (
            credential,
            document_client,
            search_client,
            blob_service,
            container,
        )

    def post_invoice(self, token, branch="guadalajara", content=b"%PDF-1.7 invoice"):
        return self.client.post(
            "/api/invoices/upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"branch": branch},
            files={"file": ("invoice.pdf", content, "application/pdf")},
        )

    def test_confident_invoice_is_stored_and_indexed_with_verified_branch(self):
        token = self.token_for(branches=("guadalajara", "leon"))
        (
            credential,
            document_client,
            search_client,
            blob_service,
            container,
        ) = self.azure_mocks(analyzed_invoice())

        with (
            patch(
                "backend.app.invoice_upload.DefaultAzureCredential",
                return_value=credential,
            ),
            patch(
                "backend.app.invoice_upload.DocumentIntelligenceClient",
                return_value=document_client,
            ),
            patch(
                "backend.app.invoice_upload.SearchClient",
                return_value=search_client,
            ),
            patch(
                "backend.app.invoice_upload.BlobServiceClient",
                return_value=blob_service,
            ),
        ):
            response = self.post_invoice(token, branch="leon")

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["status"], "indexed")
        self.assertEqual(response.json()["branch"], "leon")
        generated_filename = (
            f"FACTURA_leon_20261106_proveedor-de-prueba_"
            f"{search_client.upload_documents.call_args.kwargs['documents'][0]['document_hash']}.pdf"
        )
        self.assertEqual(response.json()["filename"], generated_filename)
        self.assertEqual(response.json()["original_filename"], "invoice.pdf")
        document = search_client.upload_documents.call_args.kwargs["documents"][0]
        self.assertEqual(document["document_filename"], generated_filename)
        self.assertEqual(document["branch"], "leon")
        self.assertEqual(
            document["security_id"], ["analista", "directivo", "gerente"]
        )
        self.assertEqual(len(document["document_hash"]), 64)
        blob_service.get_container_client.assert_called_once_with("facturas-raw")
        container.exists.assert_called_once_with()
        container.create_container.assert_not_called()
        blob_upload = container.get_blob_client.return_value.upload_blob
        blob_upload.assert_called_once()
        self.assertEqual(
            blob_upload.call_args.kwargs["metadata"],
            {
                "sha256": document["document_hash"],
                "retention_days": "90",
            },
        )
        self.assertNotIn("tags", blob_upload.call_args.kwargs)
        blob_service.get_container_client.return_value.get_blob_client.assert_called_once_with(
            f"invoices/leon/{generated_filename}"
        )
        self.assertEqual(document_client.begin_analyze_document.call_args.args[0], "prebuilt-invoice")
        repeated = self.post_invoice(token, branch="leon")
        self.assertEqual(repeated.status_code, 409)
        document_client.begin_analyze_document.assert_called_once()

    def test_low_confidence_invoice_is_persisted_for_manual_review(self):
        token = self.token_for()
        mocks = self.azure_mocks(analyzed_invoice(confidence=0.79))
        credential, document_client, search_client, blob_service, _ = mocks

        with (
            patch(
                "backend.app.invoice_upload.DefaultAzureCredential",
                return_value=credential,
            ),
            patch(
                "backend.app.invoice_upload.DocumentIntelligenceClient",
                return_value=document_client,
            ),
            patch(
                "backend.app.invoice_upload.SearchClient",
                return_value=search_client,
            ),
            patch(
                "backend.app.invoice_upload.BlobServiceClient",
                return_value=blob_service,
            ),
        ):
            response = self.post_invoice(token)
            reviews = self.client.get(
                "/api/invoices/reviews",
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()["status"], "needs_review")
        self.assertEqual(
            response.json()["filename"],
            "FACTURA_guadalajara_20261106_proveedor-pendiente_"
            f"{response.json()['filename'].split('_')[-1]}",
        )
        self.assertEqual(reviews.status_code, 200, reviews.text)
        self.assertEqual(len(reviews.json()["items"]), 1)
        self.assertEqual(
            reviews.json()["items"][0]["filename"], response.json()["filename"]
        )
        self.assertEqual(
            reviews.json()["items"][0]["original_filename"], "invoice.pdf"
        )
        self.assertEqual(reviews.json()["items"][0]["branch"], "guadalajara")
        self.assertIn("VendorName", reviews.json()["items"][0]["reasons"][0])
        search_client.upload_documents.assert_not_called()

    def test_exact_hash_duplicate_returns_conflict_without_ocr(self):
        token = self.token_for()
        mocks = self.azure_mocks(analyzed_invoice(), exact_matches=[{"id": "existing"}])
        credential, document_client, search_client, blob_service, _ = mocks

        with (
            patch(
                "backend.app.invoice_upload.DefaultAzureCredential",
                return_value=credential,
            ),
            patch(
                "backend.app.invoice_upload.DocumentIntelligenceClient",
                return_value=document_client,
            ),
            patch(
                "backend.app.invoice_upload.SearchClient",
                return_value=search_client,
            ),
            patch(
                "backend.app.invoice_upload.BlobServiceClient",
                return_value=blob_service,
            ),
        ):
            response = self.post_invoice(token)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Factura duplicada.")
        document_client.begin_analyze_document.assert_not_called()
        blob_service.get_container_client.assert_not_called()

    def test_external_service_failures_return_generic_502_and_release_reservation(self):
        token = self.token_for()
        mocks = self.azure_mocks(analyzed_invoice())
        credential, document_client, search_client, blob_service, _ = mocks
        azure_error = AzureError("backend endpoint details")
        azure_error.status_code = 403
        azure_error.error_code = "Forbidden"
        search_client.search.side_effect = azure_error

        with self.assertLogs("backend.app.invoice_upload", level="ERROR") as logs:
            with (
                patch(
                    "backend.app.invoice_upload.DefaultAzureCredential",
                    return_value=credential,
                ),
                patch(
                    "backend.app.invoice_upload.DocumentIntelligenceClient",
                    return_value=document_client,
                ),
                patch(
                    "backend.app.invoice_upload.SearchClient",
                    return_value=search_client,
                ),
                patch(
                    "backend.app.invoice_upload.BlobServiceClient",
                    return_value=blob_service,
                ),
            ):
                response = self.post_invoice(token)

        self.assertEqual(response.status_code, 502)
        self.assertIn("operation=verificar duplicado en Azure AI Search", logs.output[0])
        self.assertIn("status_code=403", logs.output[0])
        self.assertIn("error_code=Forbidden", logs.output[0])
        self.assertEqual(
            response.json()["detail"],
            "No fue posible procesar o guardar la factura.",
        )
        self.assertNotIn("backend endpoint details", response.text)
        credential.close.assert_called_once()
        search_client.close.assert_called_once()
        with Session(get_engine(str(get_database_path()))) as session:
            upload = session.scalar(select(InvoiceUpload))
            self.assertEqual(upload.status, "failed")

    def test_blob_permission_failure_returns_actionable_configuration_error(self):
        token = self.token_for()
        mocks = self.azure_mocks(analyzed_invoice())
        credential, document_client, search_client, blob_service, container = mocks
        azure_error = AzureError("permission denied")
        azure_error.status_code = 403
        azure_error.error_code = "AuthorizationPermissionMismatch"
        container.get_blob_client.return_value.upload_blob.side_effect = azure_error

        with (
            patch(
                "backend.app.invoice_upload.DefaultAzureCredential",
                return_value=credential,
            ),
            patch(
                "backend.app.invoice_upload.DocumentIntelligenceClient",
                return_value=document_client,
            ),
            patch(
                "backend.app.invoice_upload.SearchClient",
                return_value=search_client,
            ),
            patch(
                "backend.app.invoice_upload.BlobServiceClient",
                return_value=blob_service,
            ),
        ):
            response = self.post_invoice(token)

        self.assertEqual(response.status_code, 503)
        self.assertIn("Storage Blob Data Contributor", response.json()["detail"])
        self.assertNotIn("permission denied", response.text)
        with Session(get_engine(str(get_database_path()))) as session:
            upload = session.scalar(select(InvoiceUpload))
            self.assertEqual(upload.status, "failed")

    def test_probable_duplicate_is_routed_to_review_not_rejected(self):
        token = self.token_for()
        mocks = self.azure_mocks(
            analyzed_invoice(),
            probable_matches=[
                {
                    "vendor_name": "  PROVEEDOR DE PRUEBA ",
                    "invoice_date": "2026-11-06",
                    "invoice_total": 123.45,
                    "branch": "zapopan",
                }
            ],
        )
        credential, document_client, search_client, blob_service, _ = mocks

        with (
            patch(
                "backend.app.invoice_upload.DefaultAzureCredential",
                return_value=credential,
            ),
            patch(
                "backend.app.invoice_upload.DocumentIntelligenceClient",
                return_value=document_client,
            ),
            patch(
                "backend.app.invoice_upload.SearchClient",
                return_value=search_client,
            ),
            patch(
                "backend.app.invoice_upload.BlobServiceClient",
                return_value=blob_service,
            ),
        ):
            response = self.post_invoice(token)
            reviews = self.client.get(
                "/api/invoices/reviews",
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(response.status_code, 202, response.text)
        self.assertTrue(response.json()["possible_duplicate"])
        self.assertEqual(reviews.status_code, 200)
        self.assertTrue(
            any(
                "coincidencia posible" in reason.lower()
                for reason in reviews.json()["items"][0]["reasons"]
            )
        )
        search_client.upload_documents.assert_not_called()

    def test_unassigned_branch_is_forbidden_and_other_roles_cannot_upload(self):
        analyst_token = self.token_for(branches=("guadalajara",))
        wrong_branch = self.post_invoice(analyst_token, branch="leon")
        self.assertEqual(wrong_branch.status_code, 403)

        manager_token = self.token_for(role="gerente")
        forbidden_role = self.post_invoice(manager_token)
        self.assertEqual(forbidden_role.status_code, 403)

    def test_rejects_unsupported_and_oversized_files(self):
        token = self.token_for()
        unsupported = self.client.post(
            "/api/invoices/upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"branch": "guadalajara"},
            files={"file": ("invoice.txt", b"not an invoice", "text/plain")},
        )
        self.assertEqual(unsupported.status_code, 415)

        oversized = self.client.post(
            "/api/invoices/upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"branch": "guadalajara"},
            files={
                "file": (
                    "invoice.pdf",
                    b"%PDF-" + b"0" * (20 * 1024 * 1024),
                    "application/pdf",
                )
            },
        )
        self.assertEqual(oversized.status_code, 413)

    def test_review_endpoint_is_limited_to_analyst_and_admin(self):
        token = self.token_for(role="gerente")
        response = self.client.get(
            "/api/invoices/reviews",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 403)

    def test_director_sales_report_aggregates_only_approved_invoice_amounts_by_branch(self):
        token = self.token_for(
            role="directivo",
            branches=("guadalajara", "leon"),
        )
        with Session(get_engine(str(get_database_path()))) as session:
            session.add_all(
                [
                    InvoiceUpload(
                        document_hash="1" * 64,
                        original_filename="gdl-indexed.pdf",
                        content_type="application/pdf",
                        branch="guadalajara",
                        status="indexed",
                        uploaded_by=1,
                        invoice_total=123.45,
                        review_reasons="[]",
                    ),
                    InvoiceUpload(
                        document_hash="2" * 64,
                        original_filename="gdl-approved.pdf",
                        content_type="application/pdf",
                        branch="guadalajara",
                        status="approved",
                        uploaded_by=1,
                        invoice_total=50,
                        review_reasons="[]",
                    ),
                    InvoiceUpload(
                        document_hash="3" * 64,
                        original_filename="gdl-no-total.pdf",
                        content_type="application/pdf",
                        branch="guadalajara",
                        status="approved",
                        uploaded_by=1,
                        invoice_total=None,
                        review_reasons="[]",
                    ),
                    InvoiceUpload(
                        document_hash="4" * 64,
                        original_filename="zapopan-approved.pdf",
                        content_type="application/pdf",
                        branch="zapopan",
                        status="approved",
                        uploaded_by=1,
                        invoice_total=999,
                        review_reasons="[]",
                    ),
                    InvoiceUpload(
                        document_hash="5" * 64,
                        original_filename="leon-review.pdf",
                        content_type="application/pdf",
                        branch="leon",
                        status="needs_review",
                        uploaded_by=1,
                        invoice_total=800,
                        review_reasons="[]",
                    ),
                    InvoiceUpload(
                        document_hash="6" * 64,
                        original_filename="leon-declined.pdf",
                        content_type="application/pdf",
                        branch="leon",
                        status="declined",
                        uploaded_by=1,
                        invoice_total=700,
                        review_reasons="[]",
                    ),
                ]
            )
            session.commit()

        response = self.client.get(
            "/api/director/sales-report",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        report = response.json()
        self.assertEqual(report["currency"], "MXN")
        self.assertEqual(report["period"], "all_time")
        self.assertEqual(report["included_statuses"], ["indexed", "approved"])
        self.assertEqual(
            report["branches"],
            [
                {
                    "branch": "guadalajara",
                    "invoice_count": 3,
                    "invoices_with_total": 2,
                    "total": 173.45,
                },
                {
                    "branch": "leon",
                    "invoice_count": 0,
                    "invoices_with_total": 0,
                    "total": 0,
                },
            ],
        )

    def test_sales_report_is_restricted_to_director_role(self):
        token = self.token_for(role="gerente")
        response = self.client.get(
            "/api/director/sales-report",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 403)

    def test_approval_verifies_blob_hash_and_records_reviewer(self):
        token = self.token_for()
        review_id = self.create_review()
        credential = SimpleNamespace(close=Mock())
        blob_service = Mock()
        blob = blob_service.get_container_client.return_value.get_blob_client.return_value
        blob.get_blob_properties.return_value = SimpleNamespace(
            metadata={"sha256": "c" * 64}
        )

        with (
            patch(
                "backend.app.invoice_upload.DefaultAzureCredential",
                return_value=credential,
            ),
            patch(
                "backend.app.invoice_upload.BlobServiceClient",
                return_value=blob_service,
            ),
        ):
            response = self.client.patch(
                f"/api/invoices/reviews/{review_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"decision": "approve"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "approved")
        self.assertIn("Blob Storage", response.json()["detail"])
        blob_service.get_container_client.assert_called_once_with("facturas-raw")
        blob.get_blob_properties.assert_called_once_with()
        blob_service.close.assert_called_once_with()
        credential.close.assert_called_once_with()
        with Session(get_engine(str(get_database_path()))) as session:
            upload = session.get(InvoiceUpload, review_id)
            self.assertEqual(upload.status, "approved")
            self.assertEqual(upload.reviewed_by, 1)
            self.assertIsNotNone(upload.reviewed_at)

    def test_approval_is_rejected_if_blob_missing_or_hash_does_not_match(self):
        token = self.token_for()
        review_id = self.create_review()
        credential = SimpleNamespace(close=Mock())
        blob_service = Mock()
        blob = blob_service.get_container_client.return_value.get_blob_client.return_value
        blob.get_blob_properties.return_value = SimpleNamespace(
            metadata={"sha256": "d" * 64}
        )

        with (
            patch(
                "backend.app.invoice_upload.DefaultAzureCredential",
                return_value=credential,
            ),
            patch(
                "backend.app.invoice_upload.BlobServiceClient",
                return_value=blob_service,
            ),
        ):
            response = self.client.patch(
                f"/api/invoices/reviews/{review_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"decision": "approve"},
            )

        self.assertEqual(response.status_code, 409)
        with Session(get_engine(str(get_database_path()))) as session:
            self.assertEqual(
                session.get(InvoiceUpload, review_id).status,
                "needs_review",
            )

    def test_decline_records_reviewer_without_accessing_blob_storage(self):
        token = self.token_for()
        review_id = self.create_review()

        with (
            patch("backend.app.invoice_upload.DefaultAzureCredential") as credential,
            patch("backend.app.invoice_upload.BlobServiceClient") as blob_service,
        ):
            response = self.client.patch(
                f"/api/invoices/reviews/{review_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"decision": "decline"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "declined")
        credential.assert_not_called()
        blob_service.assert_not_called()
        with Session(get_engine(str(get_database_path()))) as session:
            upload = session.get(InvoiceUpload, review_id)
            self.assertEqual(upload.status, "declined")
            self.assertEqual(upload.reviewed_by, 1)
            self.assertIsNotNone(upload.reviewed_at)

    def test_preview_streams_only_the_authorized_pending_invoice(self):
        token = self.token_for()
        review_id = self.create_review()
        credential = SimpleNamespace(close=Mock())
        blob_service = Mock()
        blob = blob_service.get_container_client.return_value.get_blob_client.return_value
        blob.get_blob_properties.return_value = SimpleNamespace(
            metadata={"sha256": "c" * 64},
            size=11,
        )
        blob.download_blob.return_value.readall.return_value = b"%PDF-1.7\n"

        with (
            patch(
                "backend.app.invoice_upload.DefaultAzureCredential",
                return_value=credential,
            ),
            patch(
                "backend.app.invoice_upload.BlobServiceClient",
                return_value=blob_service,
            ),
        ):
            response = self.client.get(
                f"/api/invoices/reviews/{review_id}/preview",
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, b"%PDF-1.7\n")
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn("inline;", response.headers["content-disposition"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        blob.download_blob.assert_called_once_with()

    def test_review_decisions_require_analyst_or_admin_and_assigned_branch(self):
        analyst_token = self.token_for(role="analista", branches=("zapopan",))
        manager_token = self.token_for(role="gerente")
        with Session(get_engine(str(get_database_path()))) as session:
            analyst_id = session.scalar(
                select(User.id).where(User.email == "analista@example.com")
            )
        review_id = self.create_review(uploaded_by=analyst_id)
        forbidden_role = self.client.patch(
            f"/api/invoices/reviews/{review_id}",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={"decision": "decline"},
        )
        self.assertEqual(forbidden_role.status_code, 403)

        unassigned_branch = self.client.patch(
            f"/api/invoices/reviews/{review_id}",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={"decision": "decline"},
        )
        self.assertEqual(unassigned_branch.status_code, 404)
        with Session(get_engine(str(get_database_path()))) as session:
            self.assertEqual(
                session.get(InvoiceUpload, review_id).status,
                "needs_review",
            )

    def test_generated_invoice_filename_sanitizes_supplier_and_keeps_source_extension(self):
        filename = generate_invoice_filename(
            "my-invoice.JPEG",
            "queretaro",
            "2026-03-09",
            "Compañía / Proveedor, S.A. de C.V.",
            0.9,
            "abcdef1234567890",
        )
        self.assertEqual(
            filename,
            "FACTURA_queretaro_20260309_compania-proveedor-s-a-de-c-v_"
            "abcdef1234567890.jpeg",
        )

        pending_vendor = generate_invoice_filename(
            "invoice.pdf",
            "leon",
            None,
            "Proveedor inventado por OCR",
            0.79,
            "1234567890abcdef",
        )
        self.assertEqual(
            pending_vendor,
            "FACTURA_leon_"
            f"{pending_vendor.split('_')[2]}_proveedor-pendiente_"
            "1234567890abcdef.pdf",
        )
        second_document = generate_invoice_filename(
            "my-invoice.JPEG",
            "queretaro",
            "2026-03-09",
            "Compañía / Proveedor, S.A. de C.V.",
            0.9,
            "abcdef1234567890",
            document_number=2,
        )
        self.assertNotEqual(filename, second_document)

    def test_existing_database_migrates_generated_filename_idempotently(self):
        database_path = Path(self.temp_directory.name) / "legacy-invoices.db"
        with closing(sqlite3.connect(database_path)) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE invoice_uploads (
                        id INTEGER PRIMARY KEY,
                        document_hash VARCHAR(64) NOT NULL,
                        original_filename VARCHAR(255) NOT NULL,
                        content_type VARCHAR(100) NOT NULL,
                        branch VARCHAR(32) NOT NULL,
                        status VARCHAR(24) NOT NULL,
                        uploaded_by INTEGER NOT NULL,
                        vendor_name VARCHAR(255),
                        invoice_date VARCHAR(32),
                        invoice_total FLOAT,
                        vendor_confidence FLOAT,
                        total_confidence FLOAT,
                        review_reasons TEXT NOT NULL,
                        blob_name VARCHAR(128),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
        database_key = str(database_path.resolve())
        with patch.dict(os.environ, {"AUTH_DATABASE_PATH": database_key}):
            initialize_database()
            initialize_database()
        migration_engine = get_engine(database_key)
        with migration_engine.connect() as connection:
            columns = {
                column["name"]
                for column in inspect(connection).get_columns("invoice_uploads")
            }
        self.assertIn("generated_filename", columns)
        self.assertIn("reviewed_by", columns)
        self.assertIn("reviewed_at", columns)
        migration_engine.dispose()

    def test_analyst_reviews_are_branch_scoped_and_admin_sees_all(self):
        self.create_user(role="analista", branches=("guadalajara",))
        with Session(get_engine(str(get_database_path()))) as session:
            session.add_all(
                [
                    InvoiceUpload(
                        document_hash="a" * 64,
                        original_filename="gdl.pdf",
                        content_type="application/pdf",
                        branch="guadalajara",
                        status="needs_review",
                        uploaded_by=1,
                        review_reasons='["revisar"]',
                    ),
                    InvoiceUpload(
                        document_hash="b" * 64,
                        original_filename="zapopan.pdf",
                        content_type="application/pdf",
                        branch="zapopan",
                        status="needs_review",
                        uploaded_by=1,
                        review_reasons='["revisar"]',
                    ),
                ]
            )
            session.commit()

        analyst_login = self.client.post(
            "/api/auth/login",
            json={
                "email": "analista@example.com",
                "password": "valid-password-123",
            },
        )
        analyst_reviews = self.client.get(
            "/api/invoices/reviews",
            headers={
                "Authorization": f"Bearer {analyst_login.json()['access_token']}"
            },
        )
        self.assertEqual(analyst_reviews.status_code, 200)
        self.assertEqual(
            [item["branch"] for item in analyst_reviews.json()["items"]],
            ["guadalajara"],
        )

        admin_token = self.token_for(role="admin")
        admin_reviews = self.client.get(
            "/api/invoices/reviews",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(admin_reviews.status_code, 200)
        self.assertEqual(len(admin_reviews.json()["items"]), 2)
