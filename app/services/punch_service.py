"""Regras da jornada e cálculos de tempo do Ponto+."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from ..errors import ApiError
from ..extensions import db
from ..models import Punch, User, utc_now

TIME_ZONE = ZoneInfo("America/Sao_Paulo")
PUNCH_TYPES = ("clock_in", "break_start", "break_end", "clock_out")
ACTION_LABELS = (
    "Registrar entrada",
    "Iniciar intervalo",
    "Retornar ao trabalho",
    "Encerrar jornada",
    "Jornada encerrada",
)
UNDO_WINDOW_SECONDS = 5


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    """Converte um dia de São Paulo para o intervalo UTC equivalente."""

    start_local = datetime.combine(day, time.min, tzinfo=TIME_ZONE)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def punches_for_day(user_id: int, day: date) -> list[Punch]:
    """Obtém as batidas do usuário no dia local, em ordem cronológica."""

    start_utc, end_utc = local_day_bounds(day)
    statement = (
        select(Punch)
        .where(
            Punch.user_id == user_id,
            Punch.occurred_at >= start_utc,
            Punch.occurred_at < end_utc,
        )
        .order_by(Punch.occurred_at.asc(), Punch.id.asc())
    )
    return list(db.session.scalars(statement))


def calculate_worked_seconds(punches: list[Punch], now: datetime | None = None) -> int:
    """Soma os dois períodos trabalhados, excluindo o intervalo."""

    now = now or utc_now()
    timestamps = []
    for punch in punches:
        value = punch.occurred_at
        timestamps.append(value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC))
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    total = timedelta()
    if len(timestamps) >= 1:
        total += max(timedelta(), (timestamps[1] if len(timestamps) >= 2 else now) - timestamps[0])
    if len(timestamps) >= 3:
        total += max(timedelta(), (timestamps[3] if len(timestamps) >= 4 else now) - timestamps[2])
    return int(total.total_seconds())


def journey_state(punches: list[Punch], now: datetime | None = None) -> dict:
    """Descreve a próxima ação e o total trabalhado para a interface."""

    count = min(len(punches), len(PUNCH_TYPES))
    return {
        "status": ("not_started", "working", "on_break", "working", "finished")[count],
        "next_action": PUNCH_TYPES[count] if count < len(PUNCH_TYPES) else None,
        "next_action_label": ACTION_LABELS[count],
        "worked_seconds": calculate_worked_seconds(punches, now),
        "can_punch": count < len(PUNCH_TYPES),
    }


def register_next_punch(user: User, now: datetime | None = None) -> Punch:
    """Registra somente a próxima batida válida, usando o relógio do servidor."""

    now = now or utc_now()
    local_day = now.astimezone(TIME_ZONE).date()
    punches = punches_for_day(user.id, local_day)
    if len(punches) >= len(PUNCH_TYPES):
        raise ApiError("A jornada de hoje já foi encerrada.", 409, "journey_finished")
    punch = Punch(user_id=user.id, type=PUNCH_TYPES[len(punches)], occurred_at=now)
    db.session.add(punch)
    db.session.commit()
    return punch


def delete_last_punch(user: User, punch_id: int, now: datetime | None = None) -> None:
    """Desfaz apenas a última batida, durante a janela de cinco segundos."""

    now = now or utc_now()
    punch = db.session.get(Punch, punch_id)
    if punch is None:
        raise ApiError("Batida não encontrada.", 404, "punch_not_found")
    if punch.user_id != user.id:
        raise ApiError("Você não pode alterar uma batida de outro usuário.", 403, "forbidden_punch")
    local_day = now.astimezone(TIME_ZONE).date()
    punches = punches_for_day(user.id, local_day)
    if not punches or punches[-1].id != punch.id:
        raise ApiError("Somente a última batida de hoje pode ser desfeita.", 409, "not_last_punch")
    occurred_at = punch.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    if (now.astimezone(UTC) - occurred_at.astimezone(UTC)).total_seconds() > UNDO_WINDOW_SECONDS:
        raise ApiError("O prazo de 5 segundos para desfazer terminou.", 409, "undo_window_expired")
    db.session.delete(punch)
    db.session.commit()
