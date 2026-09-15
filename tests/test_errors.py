"""Testes dos tratadores globais de falhas HTTP e internas."""

from sqlalchemy.exc import SQLAlchemyError


def test_unknown_route_returns_standard_not_found(client):
    response = client.get("/api/rota-inexistente")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_unsupported_method_returns_standard_error(client):
    response = client.post("/api/health")
    assert response.status_code == 405
    assert response.get_json()["error"]["code"] == "method_not_allowed"


def test_database_error_is_hidden_from_client(app):
    def failing_database_route():
        raise SQLAlchemyError("detalhe interno")

    app.add_url_rule("/api/test-database-error", view_func=failing_database_route)
    response = app.test_client().get("/api/test-database-error")
    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == "database_error"
    assert "detalhe interno" not in response.get_data(as_text=True)


def test_unexpected_error_is_hidden_from_client(app):
    def failing_route():
        raise RuntimeError("detalhe interno")

    app.add_url_rule("/api/test-unexpected-error", view_func=failing_route)
    response = app.test_client().get("/api/test-unexpected-error")
    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == "internal_error"
    assert "detalhe interno" not in response.get_data(as_text=True)
