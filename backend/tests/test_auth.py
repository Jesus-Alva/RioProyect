import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.app import main
from backend.app.branches import BRANCHES
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

    def register(
        self, email="staff@example.com", role="analista", branch="guadalajara"
    ):
        return self.client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "Valid-password-123!",
                "role": role,
                "branch": branch,
            },
        )

    def create_user(
        self,
        email,
        role,
        status="active",
        is_active=True,
        branch="guadalajara",
    ):
        with Session(get_engine(str(get_database_path()))) as session:
            user = User(
                email=email,
                password_hash=hash_password("valid-password-123"),
                requested_role=None,
                requested_branches=None,
                role=role,
                branches=(
                    None
                    if branch is None
                    else list(BRANCHES)
                    if branch == "all"
                    else branch
                    if isinstance(branch, list)
                    else [branch]
                ),
                status=status,
                is_active=is_active,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user.id

    def login(self, email, password="valid-password-123"):
        return self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
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
        self.assertEqual(payload["user"]["requested_branches"], ["guadalajara"])
        self.assertEqual(payload["user"]["branches"], [])
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
        self.assertEqual(
            self.login(
                "staff@example.com", password="Valid-password-123!"
            ).status_code,
            403,
        )

        response = self.client.patch(
            f"/api/auth/admin/users/{user_id}",
            headers=self.admin_headers(),
            json={
                "role": "analista",
                "branches": ["guadalajara"],
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        login = self.login("staff@example.com", password="Valid-password-123!")
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["user"]["role"], "analista")
        self.assertEqual(login.json()["user"]["branches"], ["guadalajara"])

    def test_registration_cannot_request_all_branches(self):
        response = self.register(branch="all")
        self.assertEqual(response.status_code, 422)

    def test_active_legacy_user_without_branch_cannot_login(self):
        self.create_user(
            "legacy@example.com",
            "analista",
            branch=None,
        )
        response = self.login("legacy@example.com")
        self.assertEqual(response.status_code, 403)
        self.assertIn("asignar una sucursal", response.json()["detail"])

    def test_admin_must_assign_branch_before_activating_a_legacy_user(self):
        user_id = self.create_user(
            "legacy@example.com",
            "analista",
            status="pending",
            is_active=False,
            branch=None,
        )
        headers = self.admin_headers()
        missing_branch = self.client.patch(
            f"/api/auth/admin/users/{user_id}",
            headers=headers,
            json={"role": "bodega", "is_active": True},
        )
        self.assertEqual(missing_branch.status_code, 422)

        assigned = self.client.patch(
            f"/api/auth/admin/users/{user_id}",
            headers=headers,
            json={"role": "bodega", "branches": list(BRANCHES), "is_active": True},
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.json()["user"]["branches"], list(BRANCHES))
        self.assertEqual(self.login("legacy@example.com").status_code, 200)

    def test_admin_can_assign_multiple_branches_to_operational_accounts(self):
        headers = self.admin_headers()
        for role in ("directivo", "analista", "gerente", "bodega", "ti"):
            user_id = self.create_user(
                f"{role}@example.com",
                role,
                status="pending",
                is_active=False,
                branch=None,
            )
            assigned = self.client.patch(
                f"/api/auth/admin/users/{user_id}",
                headers=headers,
                json={
                    "role": role,
                    "branches": ["leon", "guadalajara"],
                    "is_active": True,
                },
            )
            self.assertEqual(assigned.status_code, 200)
            self.assertEqual(
                assigned.json()["user"]["branches"], ["guadalajara", "leon"]
            )

    def test_branch_change_invalidates_the_previous_token(self):
        user_id = self.create_user("staff@example.com", "bodega", branch="leon")
        login = self.login("staff@example.com")
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        current_user = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(current_user.status_code, 200, current_user.text)
        response = self.client.patch(
            f"/api/auth/admin/users/{user_id}",
            headers=self.admin_headers(),
            json={"branches": ["zapopan"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.get(
                "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
            ).status_code,
            401,
        )
        renewed = self.login("staff@example.com")
        self.assertEqual(renewed.status_code, 200)
        self.assertEqual(renewed.json()["user"]["branches"], ["zapopan"])

    def test_old_jwt_without_branch_and_forged_branch_are_rejected(self):
        user_id = self.create_user("staff@example.com", "analista", branch="leon")
        now = datetime.now(timezone.utc)
        claims = {
            "sub": str(user_id),
            "role": "analista",
            "iat": now,
            "exp": now + timedelta(minutes=10),
            "iss": "test-api",
            "aud": "test-web",
        }
        old_token = jwt.encode(claims, os.environ["JWT_SECRET"], algorithm="HS256")
        old_response = self.client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}
        )
        self.assertEqual(old_response.status_code, 401)

        claims["branch"] = "all"
        forged_token = jwt.encode(claims, os.environ["JWT_SECRET"], algorithm="HS256")
        forged_response = self.client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {forged_token}"}
        )
        self.assertEqual(forged_response.status_code, 401)

    def test_inventory_query_uses_verified_branch_and_operational_filter(self):
        self.create_user(
            "warehouse@example.com", "bodega", branch=["leon", "zapopan"]
        )
        token = self.login("warehouse@example.com").json()["access_token"]
        credential = SimpleNamespace(close=lambda: None)
        search_client = Mock()
        search_client.search.return_value = [
            {"producto": "Arroz", "cantidad": 12, "branch": "leon"},
            {"producto": "Frijol", "cantidad": 8, "branch": "zapopan"},
        ]
        with (
            patch.dict(os.environ, {"AZURE_SEARCH_ENDPOINT": "https://search.invalid"}),
            patch.object(main, "DefaultAzureCredential", return_value=credential),
            patch.object(main, "SearchClient", return_value=search_client) as factory,
        ):
            response = self.client.get(
                "/api/inventory",
                headers={"Authorization": f"Bearer {token}"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["branches"], ["zapopan", "leon"])
        self.assertEqual(response.json()["items"][0]["branch"], "leon")
        self.assertEqual(response.json()["items"][1]["branch"], "zapopan")
        self.assertEqual(factory.call_args.kwargs["index_name"], "inventario-index")
        self.assertEqual(
            search_client.search.call_args.kwargs["filter"],
            "security_id/any(g: search.in(g, 'bodega')) and "
            "search.in(branch, 'zapopan,leon', ',')",
        )
        self.assertEqual(
            search_client.search.call_args.kwargs["select"],
            ["producto", "cantidad", "branch"],
        )

    def test_non_bodega_cannot_read_inventory(self):
        self.create_user("analyst@example.com", "analista", branch="leon")
        token = self.login("analyst@example.com").json()["access_token"]
        response = self.client.get(
            "/api/inventory",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 403)

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
        login = self.login("staff@example.com")
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        response = self.client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "message": "consulta",
                "agent_role": "bodega",
                "branches": ["guadalajara"],
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_chat_accepts_assigned_branch_lists_and_passes_only_selected_scope(self):
        self.create_user(
            "staff@example.com", "analista", branch=["zapopan", "leon"]
        )
        login = self.login("staff@example.com")
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        current_user = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(current_user.status_code, 200, current_user.text)
        created = []
        requests = []
        openai_client = SimpleNamespace(
            conversations=SimpleNamespace(
                create=lambda items, metadata: (
                    created.append(metadata)
                    or SimpleNamespace(id=f"conversation-{len(created)}")
                ),
                retrieve=lambda _conversation_id: None,
                items=SimpleNamespace(create=lambda **_kwargs: None),
            ),
            responses=SimpleNamespace(
                create=lambda **kwargs: (
                    requests.append(kwargs)
                    or SimpleNamespace(output_text="Respuesta de prueba")
                )
            ),
        )

        with patch.object(main, "get_openai_client", return_value=openai_client):
            assigned = self.client.post(
                "/api/chat",
                headers={"Authorization": f"Bearer {token}"},
                json={"message": "consulta", "branches": ["leon", "zapopan"]},
            )
            subset = self.client.post(
                "/api/chat",
                headers={"Authorization": f"Bearer {token}"},
                json={"message": "solo León", "branches": ["leon"]},
            )

        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.json()["branches"], ["zapopan", "leon"])
        self.assertEqual(subset.status_code, 200)
        self.assertEqual(subset.json()["branches"], ["leon"])
        self.assertEqual(created[0]["branches"], ["zapopan", "leon"])
        self.assertEqual(created[1]["branches"], ["leon"])
        self.assertEqual(
            [
                request["extra_body"]["structured_inputs"]["branchFilter"]
                for request in requests
            ],
            ["zapopan,leon", "leon"],
        )

    def test_chat_rejects_missing_empty_malformed_and_unassigned_branches(self):
        self.create_user(
            "staff@example.com", "analista", branch=["guadalajara", "zapopan"]
        )
        login = self.login("staff@example.com")
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        missing = self.client.post(
            "/api/chat", headers=headers, json={"message": "consulta"}
        )
        empty = self.client.post(
            "/api/chat",
            headers=headers,
            json={"message": "consulta", "branches": []},
        )
        malformed = self.client.post(
            "/api/chat",
            headers=headers,
            json={"message": "consulta", "branches": "guadalajara"},
        )
        unassigned = self.client.post(
            "/api/chat",
            headers=headers,
            json={"message": "consulta", "branches": ["leon"]},
        )
        self.assertEqual(missing.status_code, 422)
        self.assertEqual(empty.status_code, 422)
        self.assertEqual(malformed.status_code, 422)
        self.assertEqual(unassigned.status_code, 403)

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
                    json={
                        "message": "consulta",
                        "agent_role": role,
                        "branches": ["zapopan", "guadalajara"],
                    },
                )
                self.assertEqual(response.status_code, 200)

        self.assertEqual(len({entry[0] for entry in created_conversations}), 5)
        self.assertEqual(
            [request["extra_body"]["structured_inputs"]["userFilter"] for request in requests],
            ["directivo", "analista", "gerente", "bodega", "ti"],
        )
        self.assertEqual(
            [request["extra_body"]["structured_inputs"]["branchFilter"] for request in requests],
            ["guadalajara,zapopan"] * 5,
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
