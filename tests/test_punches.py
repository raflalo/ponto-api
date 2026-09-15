"""Testes da sequência, isolamento e janela de desfazer."""

from datetime import datetime, timedelta

from app.extensions import db
from app.models import Punch, utc_now
from app.services.punch_service import TIME_ZONE, calculate_worked_seconds


def test_complete_sequence_rejects_fifth_punch_and_allows_undo(client, registered_user):
    _body, headers = registered_user
    created = [client.post("/api/punches", headers=headers) for _ in range(4)]
    assert [response.status_code for response in created] == [201, 201, 201, 201]
    assert [response.get_json()["punch"]["type"] for response in created] == [
        "clock_in",
        "break_start",
        "break_end",
        "clock_out",
    ]
    fifth = client.post("/api/punches", headers=headers)
    assert fifth.status_code == 409
    last_id = created[-1].get_json()["punch"]["id"]
    assert client.delete(f"/api/punches/{last_id}", headers=headers).status_code == 204
    replacement = client.post("/api/punches", headers=headers)
    assert replacement.status_code == 201
    assert replacement.get_json()["punch"]["type"] == "clock_out"


def test_month_history_returns_today_state(client, registered_user):
    _body, headers = registered_user
    client.post("/api/punches", headers=headers)
    month = utc_now().astimezone(TIME_ZONE).strftime("%Y-%m")
    response = client.get(f"/api/punches?month={month}", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["punches"]) == 1
    assert body["today"]["status"] == "working"
    assert body["today"]["next_action"] == "break_start"


def test_cannot_delete_another_users_punch(client, registered_user):
    _body, first_headers = registered_user
    punch = client.post("/api/punches", headers=first_headers).get_json()["punch"]
    second = client.post(
        "/api/auth/register",
        json={"name": "Outra Pessoa", "email": "outra@example.com", "password": "123456"},
    ).get_json()
    second_headers = {"Authorization": f"Bearer {second['token']}"}
    response = client.delete(f"/api/punches/{punch['id']}", headers=second_headers)
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden_punch"


def test_undo_window_expires(client, registered_user, app):
    _body, headers = registered_user
    punch_id = client.post("/api/punches", headers=headers).get_json()["punch"]["id"]
    with app.app_context():
        punch = db.session.get(Punch, punch_id)
        punch.occurred_at = utc_now() - timedelta(seconds=6)
        db.session.commit()
    response = client.delete(f"/api/punches/{punch_id}", headers=headers)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "undo_window_expired"


def test_invalid_month_is_rejected(client, registered_user):
    _body, headers = registered_user
    response = client.get("/api/punches?month=09-2026", headers=headers)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_month"


def test_missing_punch_cannot_be_deleted(client, registered_user):
    _body, headers = registered_user
    response = client.delete("/api/punches/999", headers=headers)
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "punch_not_found"


def test_only_latest_punch_can_be_deleted(client, registered_user):
    _body, headers = registered_user
    first_id = client.post("/api/punches", headers=headers).get_json()["punch"]["id"]
    client.post("/api/punches", headers=headers)
    response = client.delete(f"/api/punches/{first_id}", headers=headers)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "not_last_punch"


def test_worked_seconds_accepts_naive_current_time():
    start = datetime(2026, 9, 15, 8, 0, 0)
    punch = Punch(user_id=1, type="clock_in", occurred_at=start)
    total = calculate_worked_seconds(
        [punch],
        now=datetime(2026, 9, 15, 9, 0, 0),
    )
    assert total == 3600
