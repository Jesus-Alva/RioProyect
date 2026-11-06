import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from backend.app import main


class FakeJwksClient:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, _token):
        return SimpleNamespace(key=self.public_key)


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        cls.private_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        cls.public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "ENTRA_TENANT_ID": "tenant-for-tests",
                "ENTRA_CLIENT_ID": "api-client-for-tests",
            },
        )
        self.environment.start()
        self.jwks = patch.object(
            main,
            "get_jwks_client",
            return_value=FakeJwksClient(self.public_key),
        )
        self.jwks.start()

    def tearDown(self):
        self.jwks.stop()
        self.environment.stop()

    def make_token(
        self,
        roles=None,
        audience="api-client-for-tests",
        issuer="https://login.microsoftonline.com/tenant-for-tests/v2.0",
        signing_key=None,
    ):
        claims = {
            "iss": issuer,
            "aud": audience,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "oid": "user-for-tests",
        }
        if roles is not None:
            claims["roles"] = roles
        token = jwt.encode(
            claims,
            signing_key or self.private_key,
            algorithm="RS256",
        )
        return HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token,
        )

    def test_requires_bearer_token(self):
        with self.assertRaises(HTTPException) as raised:
            main.authenticate_user(None)
        self.assertEqual(raised.exception.status_code, 401)

    def test_validates_signature_audience_issuer_and_single_role(self):
        user = main.authenticate_user(self.make_token(["analista"]))
        self.assertEqual(user, {"oid": "user-for-tests", "role": "analista"})

    def test_rejects_missing_multiple_and_invalid_roles(self):
        for roles in (None, [], ["analista", "gerente"], ["otro"]):
            with self.subTest(roles=roles):
                with self.assertRaises(HTTPException) as raised:
                    main.authenticate_user(self.make_token(roles))
                self.assertEqual(raised.exception.status_code, 403)

    def test_rejects_a_token_for_a_different_api_audience(self):
        with self.assertRaises(HTTPException) as raised:
            main.authenticate_user(
                self.make_token(["analista"], audience="another-api")
            )
        self.assertEqual(raised.exception.status_code, 401)

    def test_rejects_a_token_from_a_different_issuer(self):
        with self.assertRaises(HTTPException) as raised:
            main.authenticate_user(
                self.make_token(
                    ["analista"],
                    issuer="https://login.microsoftonline.com/other-tenant/v2.0",
                )
            )
        self.assertEqual(raised.exception.status_code, 401)

    def test_rejects_a_token_signed_by_an_untrusted_key(self):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        wrong_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        with self.assertRaises(HTTPException) as raised:
            main.authenticate_user(
                self.make_token(["analista"], signing_key=wrong_key)
            )
        self.assertEqual(raised.exception.status_code, 401)

    def test_request_does_not_accept_a_client_supplied_role(self):
        with self.assertRaises(ValidationError):
            main.ChatRequest.model_validate(
                {"message": "Consulta", "role": "directivo"}
            )

    def test_conversation_remains_bound_to_its_owner_and_role(self):
        openai_client = SimpleNamespace(
            conversations=SimpleNamespace(
                retrieve=lambda _conversation_id: SimpleNamespace(
                    metadata={"owner": "user-for-tests", "role": "analista"}
                ),
                items=SimpleNamespace(create=lambda **_kwargs: None),
            ),
            responses=SimpleNamespace(
                create=lambda **_kwargs: SimpleNamespace(output_text="Respuesta")
            ),
        )
        with patch.object(main, "get_openai_client", return_value=openai_client):
            response = main.chat(
                main.ChatRequest(
                    message="Consulta",
                    conversation_id="conversation-for-tests",
                ),
                {"oid": "user-for-tests", "role": "analista"},
            )
        self.assertEqual(response["conversation_id"], "conversation-for-tests")

        unowned_conversation = SimpleNamespace(
            conversations=SimpleNamespace(
                retrieve=lambda _conversation_id: SimpleNamespace(
                    metadata={"owner": "another-user", "role": "analista"}
                ),
                items=SimpleNamespace(create=lambda **_kwargs: self.fail()),
            ),
        )
        with patch.object(
            main,
            "get_openai_client",
            return_value=unowned_conversation,
        ):
            with self.assertRaises(HTTPException) as raised:
                main.chat(
                    main.ChatRequest(
                        message="Consulta",
                        conversation_id="conversation-for-tests",
                    ),
                    {"oid": "user-for-tests", "role": "analista"},
                )
        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
