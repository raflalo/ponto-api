"""Testes das rotas públicas e do ciclo de token."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_file_origin_is_allowed_by_cors(client):
    response = client.options(
        "/api/auth/login",
        headers={"Origin": "null", "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "null"


def test_register_normalizes_email_and_returns_token(client):
    response = client.post(
        "/api/auth/register",
        json={"name": "Ana Souza", "email": "ANA@EXAMPLE.COM", "password": "123456"},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["user"]["email"] == "ana@example.com"
    assert body["token"]


def test_register_rejects_duplicate_email_ignoring_case(client):
    payload = {"name": "Ana Souza", "email": "ana@example.com", "password": "123456"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    payload["email"] = "ANA@example.com"
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "email_in_use"


def test_login_accepts_valid_password_and_rejects_invalid_one(client):
    payload = {"name": "Ana Souza", "email": "ana@example.com", "password": "123456"}
    client.post("/api/auth/register", json=payload)
    valid = client.post("/api/auth/login", json={"email": payload["email"], "password": "123456"})
    invalid = client.post("/api/auth/login", json={"email": payload["email"], "password": "errada"})
    assert valid.status_code == 200
    assert invalid.status_code == 401
    assert invalid.get_json()["error"]["code"] == "invalid_credentials"


def test_expired_token_is_rejected(client, registered_user, app):
    body, _headers = registered_user
    token = jwt.encode(
        {
            "sub": str(body["user"]["id"]),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    response = client.get("/api/profile", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "expired_token"


def test_invalid_token_is_rejected(client):
    response = client.get(
        "/api/profile",
        headers={"Authorization": "Bearer token-invalido"},
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_token"


def test_token_for_missing_user_is_rejected(client, app):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "999", "iat": now, "exp": now + timedelta(hours=1)},
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    response = client.get(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_session"


def test_register_rejects_missing_fields(client):
    response = client.post("/api/auth/register", json={})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_name"


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({"name": "A", "email": "ana@example.com", "password": "123456"}, "invalid_name"),
        ({"name": "Ana", "email": "email-invalido", "password": "123456"}, "invalid_email"),
        ({"name": "Ana", "email": "ana@example.com", "password": "123"}, "invalid_password"),
    ],
)
def test_register_rejects_invalid_fields(client, payload, expected_code):
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == expected_code
