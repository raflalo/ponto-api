"""Rotas do registro e histórico de jornada."""

import re
from datetime import date

from flask import Blueprint, g, jsonify, request
from sqlalchemy import select, text

from ..auth import require_auth
from ..errors import ApiError
from ..extensions import db
from ..models import Punch, User, utc_now
from ..validation import expected_revision, json_object
from ..services.punch_service import (
    TIME_ZONE,
    delete_last_punch,
    local_day_bounds,
    register_next_punch,
    today_snapshot,
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
      200: {description: Histórico e estado atual, schema: {$ref: '#/definitions/HistoryResponse'}}
      400: {description: Mês inválido, schema: {$ref: '#/definitions/Error'}}
      401: {description: Token ausente, inválido ou expirado, schema: {$ref: '#/definitions/Error'}}
      500: {description: Erro interno, schema: {$ref: '#/definitions/Error'}}
    """

    now = utc_now()
    local_today = now.astimezone(TIME_ZONE).date()
    month_value = request.args.get("month") or local_today.strftime("%Y-%m")
    if not MONTH_PATTERN.fullmatch(month_value):
        raise ApiError("Informe o mês no formato YYYY-MM.", 400, "invalid_month")
    year, month = map(int, month_value.split("-"))
    if year < 1 or (year == 9999 and month == 12):
        raise ApiError("Informe um mês entre 0001-01 e 9999-11.", 400, "invalid_month")
    month_start = date(year, month, 1)
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    start_utc, _ = local_day_bounds(month_start)
    end_utc, _ = local_day_bounds(next_month)
    # Um snapshot de leitura mantém registros e revisão consistentes.
    user_id = g.current_user.id
    db.session.rollback()
    db.session.execute(text("BEGIN"))
    user = db.session.get(User, user_id)
    statement = (
        select(Punch)
        .where(
            Punch.user_id == user_id,
            Punch.occurred_at >= start_utc,
            Punch.occurred_at < end_utc,
        )
        .order_by(Punch.occurred_at.asc(), Punch.id.asc())
    )
    punches = list(db.session.scalars(statement))
    return jsonify(
        {
            "month": month_value,
            "punches": [punch.to_dict() for punch in punches],
            "today": today_snapshot(user, now),
            "server_time": now.isoformat(),
        }
    )


@punches_blueprint.post("")
@require_auth
def create_punch():
    """Registra automaticamente a próxima batida do dia.
    ---
    tags: [Batidas]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        required: false
        schema:
          type: object
          properties:
            expected_revision: {type: integer, minimum: 0, description: Revisão recebida na última consulta da jornada.}
            expected_date: {type: string, format: date, description: Data da jornada exibida pela interface.}
    responses:
      201: {description: Batida registrada e jornada atualizada, schema: {$ref: '#/definitions/PunchResponse'}}
      400: {description: Corpo ou revisão inválidos, schema: {$ref: '#/definitions/Error'}}
      401: {description: Token ausente, inválido ou expirado, schema: {$ref: '#/definitions/Error'}}
      409: {description: Jornada encerrada ou desatualizada, schema: {$ref: '#/definitions/Error'}}
      500: {description: Erro interno, schema: {$ref: '#/definitions/Error'}}
    """

    payload = json_object(optional=True)
    expected_date = payload.get("expected_date")
    if expected_date is not None:
        try:
            if not isinstance(expected_date, str) or date.fromisoformat(expected_date).isoformat() != expected_date:
                raise ValueError
        except ValueError:
            raise ApiError("Data da jornada inválida.", 400, "invalid_date") from None
    response = register_next_punch(g.current_user, revision=expected_revision(payload.get("expected_revision")),
                                   expected_date=expected_date)
    return jsonify(response), 201


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
      - in: query
        name: expected_revision
        type: integer
        minimum: 0
        required: false
        description: Revisão recebida na última consulta da jornada.
    responses:
      204: {description: Batida removida}
      400: {description: Revisão inválida, schema: {$ref: '#/definitions/Error'}}
      401: {description: Token ausente, inválido ou expirado, schema: {$ref: '#/definitions/Error'}}
      403: {description: Batida pertence a outro usuário, schema: {$ref: '#/definitions/Error'}}
      404: {description: Batida não encontrada, schema: {$ref: '#/definitions/Error'}}
      409: {description: Jornada desatualizada ou batida não é a última ou prazo expirou, schema: {$ref: '#/definitions/Error'}}
      500: {description: Erro interno, schema: {$ref: '#/definitions/Error'}}
    """

    raw_revision = request.args.get("expected_revision")
    if raw_revision is not None and not re.fullmatch(r"[0-9]{1,16}", raw_revision):
        raise ApiError("Revisão inválida.", 400, "invalid_revision")
    revision = expected_revision(int(raw_revision)) if raw_revision is not None else None
    delete_last_punch(g.current_user, punch_id, revision=revision)
    return "", 204
