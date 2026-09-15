"""Rotas do registro e histórico de jornada."""

import re
from datetime import UTC, date, datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy import select

from ..auth import require_auth
from ..errors import ApiError
from ..extensions import db
from ..models import Punch, utc_now
from ..services.punch_service import (
    TIME_ZONE,
    delete_last_punch,
    journey_state,
    local_day_bounds,
    punches_for_day,
    register_next_punch,
)

punches_blueprint = Blueprint("punches", __name__, url_prefix="/api/punches")
MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@punches_blueprint.get("")
@require_auth
def list_punches():
    """Lista as batidas do mês e o estado da jornada atual.
    ---
    tags: [Batidas]
    security: [{Bearer: []}]
    parameters:
      - in: query
        name: month
        type: string
        pattern: '^\\d{4}-(0[1-9]|1[0-2])$'
        description: Mês no formato YYYY-MM; o atual é usado quando omitido.
    responses:
      200: {description: Histórico e estado atual}
      400: {description: Mês inválido}
      401: {description: Token ausente, inválido ou expirado}
    """

    now = utc_now()
    local_today = now.astimezone(TIME_ZONE).date()
    month_value = request.args.get("month") or local_today.strftime("%Y-%m")
    if not MONTH_PATTERN.fullmatch(month_value):
        raise ApiError("Informe o mês no formato YYYY-MM.", 400, "invalid_month")
    year, month = map(int, month_value.split("-"))
    month_start = date(year, month, 1)
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    start_utc, _ = local_day_bounds(month_start)
    end_utc, _ = local_day_bounds(next_month)
    statement = (
        select(Punch)
        .where(
            Punch.user_id == g.current_user.id,
            Punch.occurred_at >= start_utc,
            Punch.occurred_at < end_utc,
        )
        .order_by(Punch.occurred_at.asc(), Punch.id.asc())
    )
    punches = list(db.session.scalars(statement))
    today_punches = punches_for_day(g.current_user.id, local_today)
    return jsonify(
        {
            "month": month_value,
            "punches": [punch.to_dict() for punch in punches],
            "today": {
                "date": local_today.isoformat(),
                "punches": [punch.to_dict() for punch in today_punches],
                **journey_state(today_punches, now),
            },
        }
    )


@punches_blueprint.post("")
@require_auth
def create_punch():
    """Registra automaticamente a próxima batida do dia.
    ---
    tags: [Batidas]
    security: [{Bearer: []}]
    responses:
      201: {description: Batida registrada}
      401: {description: Token ausente, inválido ou expirado}
      409: {description: Jornada já encerrada}
    """

    punch = register_next_punch(g.current_user)
    today_punches = punches_for_day(g.current_user.id, utc_now().astimezone(TIME_ZONE).date())
    return jsonify({"punch": punch.to_dict(), "today": journey_state(today_punches)}), 201


@punches_blueprint.delete("/<int:punch_id>")
@require_auth
def delete_punch(punch_id: int):
    """Desfaz a última batida dentro de cinco segundos.
    ---
    tags: [Batidas]
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: punch_id
        type: integer
        required: true
    responses:
      204: {description: Batida removida}
      403: {description: Batida pertence a outro usuário}
      404: {description: Batida não encontrada}
      409: {description: Batida não é a última ou o prazo expirou}
    """

    delete_last_punch(g.current_user, punch_id)
    return "", 204
