"""Cria dados inteiramente fictícios para uma instalação demonstrativa nova."""

from datetime import date, datetime, time, timedelta, timezone

from .extensions import db
from .models import Punch, User


def seed_demo_history() -> None:
    """Cria a conta pública e 59 jornadas de exemplo, sem dados de pessoas reais."""

    user = User(
        name="Usuário Teste",
        email="teste@teste.com",
        daily_goal_minutes=480,
        created_at=datetime(2026, 6, 29, 12, tzinfo=timezone.utc),
    )
    user.set_password("Teste123!")
    db.session.add(user)
    db.session.flush()

    first_day = date(2026, 7, 1)
    workdays = [first_day + timedelta(days=offset) for offset in range(90)
                if (first_day + timedelta(days=offset)).weekday() < 5][:59]
    for index, day in enumerate(workdays):
        start = 12 * 60 + (index * 7) % 21
        break_start = 15 * 60 + (index * 11) % 19
        break_end = break_start + 55 + index % 11
        finish = 21 * 60 + (index * 13) % 27
        for punch_type, minutes in (
            ("clock_in", start),
            ("break_start", break_start),
            ("break_end", break_end),
            ("clock_out", finish),
        ):
            moment = datetime.combine(day, time(minutes // 60, minutes % 60, tzinfo=timezone.utc))
            db.session.add(Punch(user_id=user.id, type=punch_type, occurred_at=moment, created_at=moment))
    db.session.commit()
