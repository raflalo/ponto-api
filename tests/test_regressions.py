"""Regressões de segurança, concorrência, migração e contrato público."""

import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime, timedelta
from threading import Barrier
from unittest.mock import patch

import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest

from app import create_app
from app.configuration import jwt_secret
from app.extensions import db
from app.models import Punch, User


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/auth/register"), ("POST", "/api/auth/login"), ("PATCH", "/api/profile"),
    ("POST", "/api/punches"),
])
@pytest.mark.parametrize("payload", [["texto"], "texto", 42, True, None])
def test_non_object_json_is_bad_request(client, registered_user, method, path, payload):
    _, headers = registered_user
    response = client.open(path, method=method, data=json.dumps(payload), content_type="application/json", headers=headers)
    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_body"


@pytest.mark.parametrize("month", ["0000-01", "9999-12", "2026-00", "2026-13", "2026-09-extra"])
def test_invalid_month_boundaries(client, registered_user, month):
    assert client.get("/api/punches?month=" + month, headers=registered_user[1]).status_code == 400


@pytest.mark.parametrize("email", ["pessoa@@example.com", "pessoa com espaco@example.com", "pessoa@.com", "a@-host.com", "a@host-.com"])
def test_email_validation_matches_frontend(client, email):
    payload = {"name": "Teste", "email": email, "password": "123456"}
    assert client.post("/api/auth/register", json=payload).status_code == 400
    assert client.post("/api/auth/login", json=payload).status_code == 400


def test_password_characters_are_not_trimmed(client):
    client.post("/api/auth/register", json={"name": "Teste", "email": "spaces@example.com", "password": "  segredo  "})
    assert client.post("/api/auth/login", json={"email": "spaces@example.com", "password": "segredo"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "spaces@example.com", "password": "  segredo  "}).status_code == 200


@pytest.mark.parametrize("payload", [{"name": "A" * 121}, {"daily_goal_minutes": 0}, {"daily_goal_minutes": 1440},
                                     {"daily_goal_minutes": True}, {"daily_goal_minutes": "480"}, {}, {"email": "new@example.com"}])
def test_profile_boundaries(client, registered_user, payload):
    assert client.patch("/api/profile", json=payload, headers=registered_user[1]).status_code == 400


def test_goal_persists_and_is_isolated(client, registered_user):
    body, headers = registered_user
    response = client.patch("/api/profile", json={"daily_goal_minutes": 360}, headers=headers)
    assert response.json["user"]["daily_goal_minutes"] == 360
    assert client.get("/api/profile", headers=headers).json["user"]["daily_goal_minutes"] == 360
    other = client.post("/api/auth/register", json={"name": "Outra", "email": "other@example.com", "password": "123456"}).json
    assert other["user"]["daily_goal_minutes"] == 480
    assert client.post("/api/auth/login", json={"email": body["user"]["email"], "password": "segredo123"}).json["user"]["daily_goal_minutes"] == 360


@pytest.mark.parametrize("missing", ["sub", "iat", "exp"])
def test_required_token_claims(client, registered_user, app, missing):
    payload = {"sub": str(registered_user[0]["user"]["id"]), "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(hours=1)}
    payload.pop(missing)
    token = jwt.encode(payload, app.config["JWT_SECRET_KEY"], algorithm="HS256")
    assert client.get("/api/profile", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_local_secret_is_private_persistent_and_not_public(tmp_path, monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    config = {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "INSTANCE_PATH": str(tmp_path)}
    first = create_app(config)
    second = create_app(config)
    assert first.config["JWT_SECRET_KEY"] == second.config["JWT_SECRET_KEY"]
    assert len(first.config["JWT_SECRET_KEY"]) >= 32
    assert os.stat(tmp_path / "jwt-secret").st_mode & 0o777 == 0o600
    response = first.test_client().post("/api/auth/register", json={"name": "QA", "email": "qa@example.com", "password": "123456"})
    forged = jwt.encode({"sub": str(response.json["user"]["id"]), "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(hours=1)},
                        "dev-only-change-this-secret-before-production", algorithm="HS256")
    assert first.test_client().get("/api/profile", headers={"Authorization": "Bearer " + forged}).status_code == 401
    for application in [first, second]:
        with application.app_context():
            db.session.remove()
            db.engine.dispose()


def test_fresh_install_includes_demo_and_preserves_existing_data(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config = {"TESTING": True, "INSTANCE_PATH": str(tmp_path)}
    first = create_app(config)
    client = first.test_client()
    login = client.post("/api/auth/login", json={"email": "teste@teste.com", "password": "Teste123!"})
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json["token"]}
    history = [client.get(f"/api/punches?month=2026-{month:02d}", headers=headers) for month in (7, 8, 9)]
    assert all(response.status_code == 200 for response in history)
    assert sum(len(response.json["punches"]) for response in history) == 236
    with first.app_context():
        assert db.session.query(User).count() == 1
        assert db.session.query(Punch).count() == 236

    assert client.post("/api/auth/register", json={
        "name": "Outra pessoa", "email": "outra@example.com", "password": "senha123",
    }).status_code == 201
    with first.app_context():
        db.session.remove()
        db.engine.dispose()

    second = create_app(config)
    with second.app_context():
        assert db.session.query(User).count() == 2
        assert db.session.query(Punch).count() == 236
        db.session.remove()
        db.engine.dispose()


@pytest.mark.parametrize("secret", ["short", "dev-only-change-this-secret-before-production", "troque-por-uma-chave-longa-e-aleatoria"])
def test_insecure_configured_secret_is_rejected(tmp_path, secret):
    with pytest.raises(ValueError):
        jwt_secret(str(tmp_path), secret)


def test_secret_concurrent_publication(tmp_path):
    original_link = os.link
    barrier = Barrier(2)
    def simultaneous_link(source, target):
        barrier.wait(timeout=5)
        original_link(source, target)
    with patch("app.configuration.os.link", simultaneous_link), ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(jwt_secret, str(tmp_path)) for _ in range(2)]
        values = [future.result(timeout=10) for future in futures]
    assert values[0] == values[1] == (tmp_path / "jwt-secret").read_text()


def test_additive_migration_preserves_legacy_data(tmp_path):
    database = tmp_path / "legacy.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE, password_hash VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL);
            CREATE TABLE punches (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, type VARCHAR(24) NOT NULL,
                occurred_at DATETIME NOT NULL, created_at DATETIME NOT NULL);
            INSERT INTO users VALUES (1, 'Usuário anterior', 'legacy@example.com', 'hash-preservado', '2026-09-15 12:00:00');
            INSERT INTO punches VALUES (1, 1, 'clock_in', '2026-09-15 12:00:00', '2026-09-15 12:00:00');
        """)
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(database), "JWT_SECRET_KEY": "isolated-test-key-with-at-least-32-characters"})
    with app.app_context():
        user = db.session.get(User, 1)
        assert user.name == "Usuário anterior" and user.password_hash == "hash-preservado"
        assert user.daily_goal_minutes == 480 and user.punch_revision == 0
        assert db.session.get(Punch, 1).type == "clock_in"
        db.session.remove()
        db.engine.dispose()


@pytest.mark.parametrize("initial,send_revision,expected_count,expected_statuses", [
    (0, False, 2, [201, 201]), (0, True, 1, [201, 409]), (3, False, 4, [201, 409]),
])
def test_simultaneous_punches_are_atomic(tmp_path, initial, send_revision, expected_count, expected_statuses):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "concurrent.db"),
                      "JWT_SECRET_KEY": "isolated-concurrency-key-at-least-32-bytes"})
    client = app.test_client()
    account = client.post("/api/auth/register", json={"name": "QA", "email": "qa@example.com", "password": "123456"}).json
    headers = {"Authorization": "Bearer " + account["token"]}
    for _ in range(initial):
        assert client.post("/api/punches", headers=headers).status_code == 201
    barrier = Barrier(2)
    def send():
        barrier.wait(timeout=5)
        return app.test_client().post("/api/punches", headers=headers, json={"expected_revision": initial} if send_revision else {}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(send) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]
    assert sorted(results) == expected_statuses
    with app.app_context():
        punches = list(db.session.scalars(select(Punch).order_by(Punch.occurred_at, Punch.id)))
        assert len(punches) == expected_count
        assert [item.type for item in punches] == ["clock_in", "break_start", "break_end", "clock_out"][:expected_count]
        db.session.remove()
        db.engine.dispose()


@pytest.mark.parametrize("value", [-1, "0", True, 1.5])
def test_invalid_revision_is_rejected(client, registered_user, value):
    assert client.post("/api/punches", headers=registered_user[1], json={"expected_revision": value}).status_code == 400


@pytest.mark.parametrize("value", ["abc", "-1", "0.5", "9" * 100])
def test_invalid_delete_revision(client, registered_user, value):
    assert client.delete("/api/punches/1?expected_revision=" + value, headers=registered_user[1]).status_code == 400


@pytest.mark.parametrize("value", ["invalid", False, "2026-02-30", "20260915"])
def test_invalid_expected_date(client, registered_user, value):
    assert client.post("/api/punches", headers=registered_user[1], json={"expected_date": value}).status_code == 400


def test_midnight_revision_and_server_owned_timestamps(client, registered_user):
    headers = registered_user[1]
    stamps = ["2026-09-15T11:00:00+00:00", "2026-09-15T15:00:00+00:00", "2026-09-15T16:00:00+00:00", "2026-09-15T20:00:00+00:00"]
    for revision, stamp in enumerate(stamps):
        now = datetime.fromisoformat(stamp)
        with patch("app.services.punch_service.utc_now", return_value=now):
            response = client.post("/api/punches", headers=headers, json={"expected_revision": revision, "expected_date": "2026-09-15",
                                                                          "type": "clock_out", "occurred_at": "2000-01-01T00:00:00Z"})
        assert response.status_code == 201
        assert len(response.json["today"]["punches"]) == revision + 1
        assert response.json["punch"]["occurred_at"] == stamp
    assert response.json["today"]["worked_seconds"] == 28800
    tomorrow = datetime(2026, 9, 16, 3, 0, 1, tzinfo=UTC)
    with patch("app.routes.punches.utc_now", return_value=tomorrow), patch("app.services.punch_service.utc_now", return_value=tomorrow):
        today = client.get("/api/punches?month=2026-09", headers=headers).json["today"]
        assert today["punches"] == [] and today["can_punch"] is True
        assert client.post("/api/punches", headers=headers, json={"expected_date": "2026-09-15"}).status_code == 409
        response = client.post("/api/punches", headers=headers, json={"expected_revision": 4, "expected_date": "2026-09-16"})
        assert response.status_code == 201 and response.json["today"]["revision"] == 5
        punch_id = response.json["punch"]["id"]
        assert client.delete(f"/api/punches/{punch_id}?expected_revision=4", headers=headers).status_code == 409
        assert client.delete(f"/api/punches/{punch_id}?expected_revision=5", headers=headers).status_code == 204


def test_swagger_has_complete_public_contract(client):
    specification = client.get("/apispec_1.json").json
    operations = [operation for methods in specification["paths"].values() for operation in methods.values()]
    assert len(operations) == 8
    for operation in operations:
        assert operation["summary"]
        for status, response in operation["responses"].items():
            assert response["description"]
            if str(status) != "204":
                assert "schema" in response
                assert response["schema"]["$ref"].split("/")[-1] in specification["definitions"]
    assert "401" in specification["paths"]["/api/punches/{punch_id}"]["delete"]["responses"]


def test_duplicate_race_is_conflict(client, registered_user):
    with patch("app.routes.auth.db.session.commit", side_effect=IntegrityError("insert", {}, Exception())):
        response = client.post("/api/auth/register", json={"name": "QA", "email": "new@example.com", "password": "123456"})
    assert response.status_code == 409


def test_http_bad_request_is_not_internal_error(app):
    app.add_url_rule("/api/bad-body", view_func=lambda: (_ for _ in ()).throw(BadRequest()))
    assert app.test_client().get("/api/bad-body").status_code == 400
