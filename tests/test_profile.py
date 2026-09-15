"""Testes das operações protegidas do perfil."""


def test_profile_requires_token(client):
    response = client.get("/api/profile")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "missing_token"


def test_get_and_update_profile(client, registered_user):
    _body, headers = registered_user
    current = client.get("/api/profile", headers=headers)
    updated = client.patch("/api/profile", headers=headers, json={"name": "Rafael Aflalo"})
    assert current.status_code == 200
    assert current.get_json()["user"]["name"] == "Rafael Ferreira"
    assert updated.status_code == 200
    assert updated.get_json()["user"]["name"] == "Rafael Aflalo"


def test_update_profile_rejects_short_name(client, registered_user):
    _body, headers = registered_user
    response = client.patch("/api/profile", headers=headers, json={"name": "R"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_name"
