"""Fixtures compartilhadas pelos testes da API."""

import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    """Cria uma aplicação isolada com SQLite em memória."""

    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret-with-at-least-32-bytes",
        }
    )
    yield application
    with application.app_context():
        engine = db.engine
        db.session.remove()
        db.drop_all()
        engine.dispose()


@pytest.fixture()
def client(app):
    """Disponibiliza o cliente HTTP de testes do Flask."""

    return app.test_client()


@pytest.fixture()
def registered_user(client):
    """Cadastra um usuário e retorna corpo e cabeçalho autenticado."""

    response = client.post(
        "/api/auth/register",
        json={
            "name": "Rafael Ferreira",
            "email": "rafael@example.com",
            "password": "segredo123",
        },
    )
    body = response.get_json()
    return body, {"Authorization": f"Bearer {body['token']}"}
