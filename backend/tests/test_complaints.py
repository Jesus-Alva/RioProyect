import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from openai import OpenAIError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app import main
from backend.app.database import (
    Complaint,
    User,
    get_database_path,
    get_engine,
)
from backend.app.security import hash_password


class ComplaintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.database_path = Path(cls.temp_directory.name) / "complaints.db"
        cls.environment = patch.dict(
            os.environ,
            {
                "JWT_SECRET": "test-key-not-used-outside-tests-123456789",
                "JWT_ISSUER": "test-api",
                "JWT_AUDIENCE": "test-web",
                "AUTH_DATABASE_PATH": str(cls.database_path),
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
            session.execute(delete(Complaint))
            session.execute(delete(User))
            session.commit()

    def create_user(self, role, branches):
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
        login = self.client.post(
            "/api/auth/login",
            json={
                "email": f"{role}@example.com",
                "password": "valid-password-123",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def complaint_payload(self, **overrides):
        return {
            "nombre": "Cliente Río Claro",
            "correo": "cliente@example.com",
            "sucursal": "guadalajara",
            "mensaje": "El pedido llegó dos días después de la fecha acordada.",
            **overrides,
        }

    def test_public_submission_analyzes_with_manager_before_database_insert(self):
        response_body = {
            "summary": "El pedido se entregó dos días tarde.",
            "critical_point": "Retraso en la entrega acordada.",
            "category": "demora",
        }
        openai_client = Mock()
        openai_client.conversations.create.return_value = SimpleNamespace(
            id="complaint-analysis-conversation"
        )

        def analyze_before_insert(**kwargs):
            with Session(get_engine(str(get_database_path()))) as session:
                self.assertEqual(
                    session.scalar(select(Complaint.id).limit(1)),
                    None,
                )
            self.assertEqual(
                kwargs["extra_body"]["agent_reference"]["name"],
                "rio-gerente",
            )
            self.assertEqual(
                kwargs["extra_body"]["structured_inputs"],
                {"userFilter": "gerente", "branchFilter": "guadalajara"},
            )
            self.assertEqual(kwargs["timeout"], 30)
            self.assertEqual(
                kwargs["conversation"],
                "complaint-analysis-conversation",
            )
            prompt = json.dumps(
                openai_client.conversations.create.call_args.kwargs["items"],
                ensure_ascii=False,
            )
            self.assertIn("El pedido llegó dos días después", prompt)
            self.assertNotIn("cliente@example.com", prompt)
            return SimpleNamespace(
                output_text=json.dumps(response_body, ensure_ascii=False)
            )

        openai_client.responses.create.side_effect = analyze_before_insert
        with patch(
            "backend.app.main.get_openai_client",
            return_value=openai_client,
        ):
            response = self.client.post(
                "/api/complaints",
                json=self.complaint_payload(),
            )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["estado_analisis"], "completed")
        self.assertEqual(response.json()["resumen_ia"], response_body["summary"])
        self.assertEqual(
            response.json()["punto_critico"],
            response_body["critical_point"],
        )
        self.assertEqual(response.json()["categoria"], "demora")
        openai_client.conversations.create.assert_called_once_with(
            items=unittest.mock.ANY,
            metadata={"purpose": "complaint_analysis"},
        )
        openai_client.conversations.delete.assert_called_once_with(
            "complaint-analysis-conversation"
        )
        openai_client.responses.create.assert_called_once()
        with Session(get_engine(str(get_database_path()))) as session:
            complaint = session.get(Complaint, response.json()["id"])
            self.assertEqual(complaint.cliente_email, "cliente@example.com")
            self.assertEqual(complaint.sucursal, "guadalajara")
            self.assertEqual(complaint.estado, "received")

    def test_public_submission_is_saved_for_manual_triage_if_foundry_fails(self):
        openai_client = Mock()
        openai_client.responses.create.side_effect = RuntimeError(
            "sensitive endpoint details"
        )
        openai_client.conversations.delete.side_effect = OpenAIError(
            "temporary conversation cleanup failed"
        )
        with (
            patch(
                "backend.app.main.get_openai_client",
                return_value=openai_client,
            ),
            self.assertLogs("backend.app.main", level="ERROR"),
            self.assertLogs(
                "backend.app.complaint_analysis",
                level="ERROR",
            ),
        ):
            response = self.client.post(
                "/api/complaints",
                json=self.complaint_payload(),
            )

        openai_client.conversations.delete.assert_called_once()
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()["estado_analisis"], "failed")
        self.assertNotIn("sensitive endpoint details", response.text)
        self.assertEqual(
            response.json()["detail"],
            "Recibimos tu queja; el análisis automático no está disponible.",
        )
        with Session(get_engine(str(get_database_path()))) as session:
            complaint = session.get(Complaint, response.json()["id"])
            self.assertEqual(complaint.estado_analisis, "failed")
            self.assertIsNone(complaint.resumen_ia)
            self.assertIsNone(complaint.punto_critico)

    def test_public_submission_does_not_store_unvalidated_ai_analysis(self):
        openai_client = Mock()
        openai_client.responses.create.return_value.output_text = json.dumps(
            {
                "summary": "Resumen sin categoría válida.",
                "critical_point": "Punto crítico identificado.",
                "category": "unexpected",
            }
        )
        with (
            patch(
                "backend.app.main.get_openai_client",
                return_value=openai_client,
            ),
            self.assertLogs("backend.app.main", level="ERROR"),
        ):
            response = self.client.post(
                "/api/complaints",
                json=self.complaint_payload(),
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["estado_analisis"], "failed")
        self.assertIsNone(response.json()["resumen_ia"])
        with Session(get_engine(str(get_database_path()))) as session:
            complaint = session.get(Complaint, response.json()["id"])
            self.assertIsNone(complaint.categoria)
            self.assertIsNone(complaint.resumen_ia)

    def test_public_submission_validates_fields_before_calling_foundry(self):
        with patch("backend.app.main.get_openai_client") as get_client:
            response = self.client.post(
                "/api/complaints",
                json=self.complaint_payload(
                    correo="not-an-email",
                    sucursal="unknown",
                ),
            )

        self.assertEqual(response.status_code, 422)
        get_client.assert_not_called()
        with Session(get_engine(str(get_database_path()))) as session:
            self.assertIsNone(session.scalar(select(Complaint.id).limit(1)))

    def test_complaint_inbox_requires_gerente_and_limits_items_to_assigned_branches(self):
        manager_headers = self.create_user("gerente", ["guadalajara"])
        analyst_headers = self.create_user("analista", ["guadalajara"])
        with Session(get_engine(str(get_database_path()))) as session:
            session.add_all(
                [
                    Complaint(
                        cliente_nombre="Cliente uno",
                        cliente_email="one@example.com",
                        sucursal="guadalajara",
                        mensaje="Mensaje de Guadalajara",
                        categoria="demora",
                        resumen_ia="Resumen uno",
                        punto_critico="Punto crítico uno",
                        estado_analisis="completed",
                        estado="received",
                    ),
                    Complaint(
                        cliente_nombre="Cliente dos",
                        cliente_email="two@example.com",
                        sucursal="leon",
                        mensaje="Mensaje de León",
                        categoria="otro",
                        estado_analisis="failed",
                        estado="received",
                    ),
                ]
            )
            session.commit()

        unauthorized = self.client.get("/api/complaints")
        denied = self.client.get(
            "/api/complaints",
            headers=analyst_headers,
        )
        listed = self.client.get(
            "/api/complaints",
            headers=manager_headers,
        )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(len(listed.json()["items"]), 1)
        self.assertEqual(listed.json()["items"][0]["sucursal"], "guadalajara")

    def test_manager_can_update_status_only_for_assigned_branch(self):
        manager_headers = self.create_user("gerente", ["guadalajara"])
        analyst_headers = self.create_user("analista", ["guadalajara"])
        with Session(get_engine(str(get_database_path()))) as session:
            complaint = Complaint(
                cliente_nombre="Cliente",
                cliente_email="cliente@example.com",
                sucursal="guadalajara",
                mensaje="El pedido llegó tarde.",
                categoria="demora",
                estado_analisis="completed",
                estado="received",
            )
            other_branch = Complaint(
                cliente_nombre="Otro cliente",
                cliente_email="otro@example.com",
                sucursal="leon",
                mensaje="El pedido llegó tarde.",
                categoria="demora",
                estado_analisis="completed",
                estado="received",
            )
            session.add_all([complaint, other_branch])
            session.commit()
            complaint_id = complaint.id
            other_branch_id = other_branch.id

        updated = self.client.patch(
            f"/api/complaints/{complaint_id}",
            headers=manager_headers,
            json={"estado": "in_progress"},
        )
        hidden = self.client.patch(
            f"/api/complaints/{other_branch_id}",
            headers=manager_headers,
            json={"estado": "resolved"},
        )
        invalid = self.client.patch(
            f"/api/complaints/{complaint_id}",
            headers=manager_headers,
            json={"estado": "deleted"},
        )
        anonymous = self.client.patch(
            f"/api/complaints/{complaint_id}",
            json={"estado": "resolved"},
        )
        forbidden = self.client.patch(
            f"/api/complaints/{complaint_id}",
            headers=analyst_headers,
            json={"estado": "resolved"},
        )

        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["estado"], "in_progress")
        self.assertEqual(hidden.status_code, 404)
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(forbidden.status_code, 403)
        with Session(get_engine(str(get_database_path()))) as session:
            self.assertEqual(session.get(Complaint, complaint_id).estado, "in_progress")
            self.assertEqual(session.get(Complaint, other_branch_id).estado, "received")


if __name__ == "__main__":
    unittest.main()
