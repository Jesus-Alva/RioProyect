import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.app import main
from backend.app.database import User, get_database_path, get_engine
from backend.app.security import hash_password
from backend.scripts import create_admin


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.database_path = Path(cls.temp_directory.name) / "users.db"
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
            session.execute(delete(User))
            session.commit()

    def register(self, email="staff@example.com", role="analista"):
        return self.client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "Valid-password-123!",
                "role": role,
            },
        )

    def create_user(self, email, role, status="active", is_active=True):
        with Session(get_engine(str(get_database_path()))) as session:
            user = User(
                email=email,
                password_hash=hash_password("valid-password-123"),
                requested_role=None,
                role=role,
                status=status,
                is_active=is_active,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user.id

    def login(self, email):
        return self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "valid-password-123"},
        )

    def admin_headers(self):
        self.create_user("admin@example.com", "admin")
        result = self.login("admin@example.com")
        self.assertEqual(result.status_code, 200)
        return {"Authorization": f"Bearer {result.json()['access_token']}"}

    def test_registration_hashes_password_and_keeps_role_pending(self):
        response = self.register(email="  STAFF@Example.com ")

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertNotIn("access_token", payload)
        self.assertEqual(payload["user"]["email"], "staff@example.com")
        self.assertEqual(payload["user"]["requested_role"], "analista")
        self.assertIsNone(payload["user"]["role"])
        self.assertEqual(payload["user"]["status"], "pending")
        with Session(get_engine(str(get_database_path()))) as session:
            user = session.get(User, payload["user"]["id"])
            self.assertNotEqual(user.password_hash, "Valid-password-123!")

    def test_bootstrap_command_creates_an_admin_without_public_registration(self):
        with (
            patch("builtins.input", return_value="first-admin@example.com"),
            patch(
                "getpass.getpass",
                side_effect=["admin-password-123", "admin-password-123"],
            ),
        ):
            self.assertEqual(create_admin.main(), 0)

        login = self.client.post(
            "/api/auth/login",
            json={
                "email": "first-admin@example.com",
                "password": "admin-password-123",
            },
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["user"]["role"], "admin")

    def test_public_registration_rejects_admin_and_duplicate_email(self):
        self.assertEqual(self.register(role="admin").status_code, 422)
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register().status_code, 409)

    def test_pending_user_cannot_login_until_admin_assigns_role(self):
        registration = self.register()
        user_id = registration.json()["user"]["id"]
        self.assertEqual(self.login("staff@example.com").status_code, 403)

        response = self.client.patch(
            f"/api/auth/admin/users/{user_id}",
            headers=self.admin_headers(),
            json={"role": "analista", "is_active": True},
        )
        self.assertEqual(response.status_code, 200)
        login = self.login("staff@example.com")
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["user"]["role"], "analista")

    def test_login_rejects_invalid_password_and_suspended_accounts(self):
        user_id = self.create_user("staff@example.com", "analista")
        bad_password = self.client.post(
            "/api/auth/login",
            json={"email": "staff@example.com", "password": "incorrect"},
        )
        self.assertEqual(bad_password.status_code, 401)

        self.client.patch(
            f"/api/auth/admin/users/{user_id}",
            headers=self.admin_headers(),
            json={"is_active": False},
        )
        self.assertEqual(self.login("staff@example.com").status_code, 403)

    def test_jwt_authentication_and_role_changes_invalidate_old_tokens(self):
        user_id = self.create_user("staff@example.com", "bodega")
        login = self.login("staff@example.com")
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).json()["role"], "bodega")

        update = self.client.patch(
            f"/api/auth/admin/users/{user_id}",
            headers=self.admin_headers(),
            json={"role": "ti"},
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)

    def test_expired_and_tampered_tokens_are_rejected(self):
        user_id = self.create_user("staff@example.com", "analista")
        login = self.login("staff@example.com")
        token = login.json()["access_token"]
        tampered_token = f"{token[:-1]}{'A' if token[-1] != 'A' else 'B'}"
        self.assertEqual(
            self.client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {tampered_token}"},
            ).status_code,
            401,
        )

        expired_token = jwt.encode(
            {
                "sub": str(user_id),
                "role": "analista",
                "iat": datetime.now(timezone.utc) - timedelta(hours=2),
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "iss": "test-api",
                "aud": "test-web",
            },
            os.environ["JWT_SECRET"],
            algorithm="HS256",
        )
        self.assertEqual(
            self.client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {expired_token}"},
            ).status_code,
            401,
        )

    def test_admin_can_manage_users_but_regular_users_cannot(self):
        pending = self.register()
        user_id = pending.json()["user"]["id"]
        self.create_user("staff2@example.com", "gerente")
        regular_login = self.client.patch(
            f"/api/auth/admin/users/{user_id}",
            headers={
                "Authorization": (
                    f"Bearer {self.login('staff2@example.com').json()['access_token']}"
                )
            },
            json={"role": "ti"},
        )
        self.assertEqual(regular_login.status_code, 403)

        headers = self.admin_headers()
        listing = self.client.get("/api/auth/admin/users", headers=headers)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()["users"]), 3)
        self.assertNotIn("password_hash", listing.text)

        admin_id = next(
            user["id"]
            for user in listing.json()["users"]
            if user["role"] == "admin"
        )
        self.assertEqual(
            self.client.patch(
                f"/api/auth/admin/users/{admin_id}",
                headers=headers,
                json={"role": "ti"},
            ).status_code,
            404,
        )

    def test_regular_user_cannot_select_another_agent(self):
        self.create_user("staff@example.com", "directivo")
        token = self.login("staff@example.com").json()["access_token"]
        response = self.client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "consulta", "agent_role": "bodega"},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_chat_with_each_agent_in_separate_conversations(self):
        headers = self.admin_headers()
        created_conversations = []
        requests = []

        def create_conversation(items, metadata):
            conversation_id = f"conversation-{len(created_conversations)}"
            created_conversations.append((conversation_id, metadata))
            return SimpleNamespace(id=conversation_id, metadata=metadata)

        def create_response(**kwargs):
            requests.append(kwargs)
            return SimpleNamespace(output_text="Respuesta de prueba")

        client = SimpleNamespace(
            conversations=SimpleNamespace(
                create=create_conversation,
                retrieve=lambda conversation_id: SimpleNamespace(
                    metadata=dict(
                        next(
                            metadata
                            for existing_id, metadata in created_conversations
                            if existing_id == conversation_id
                        )
                    )
                ),
                items=SimpleNamespace(create=lambda **_kwargs: None),
            ),
            responses=SimpleNamespace(create=create_response),
        )

        with patch.object(main, "get_openai_client", return_value=client):
            for role in ("directivo", "analista", "gerente", "bodega", "ti"):
                response = self.client.post(
                    "/api/chat",
                    headers=headers,
                    json={"message": "consulta", "agent_role": role},
                )
                self.assertEqual(response.status_code, 200)

        self.assertEqual(len({entry[0] for entry in created_conversations}), 5)
        self.assertEqual(
            [request["extra_body"]["structured_inputs"]["userFilter"] for request in requests],
            ["directivo", "analista", "gerente", "bodega", "ti"],
        )
        self.assertNotIn("admin", [metadata["role"] for _, metadata in created_conversations])

    def test_cors_preflight_allows_admin_permission_updates(self):
        response = self.client.options(
            "/api/auth/admin/users/1",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("PATCH", response.headers["access-control-allow-methods"])


if __name__ == "__main__":
    unittest.main()
