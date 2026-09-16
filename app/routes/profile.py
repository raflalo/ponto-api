"""Consulta e atualização do perfil autenticado."""

from flask import Blueprint, g, jsonify

from ..auth import require_auth
from ..errors import ApiError
from ..extensions import db
from ..validation import json_object

profile_blueprint = Blueprint("profile", __name__, url_prefix="/api/profile")


@profile_blueprint.get("")
@require_auth
def get_profile():
    """Retorna o perfil da sessão atual.
    ---
    tags: [Perfil]
    security: [{Bearer: []}]
    responses:
      200: {description: Perfil encontrado, schema: {$ref: '#/definitions/ProfileResponse'}}
      401: {description: Token ausente, inválido ou expirado, schema: {$ref: '#/definitions/Error'}}
      500: {description: Erro interno, schema: {$ref: '#/definitions/Error'}}
    """

    return jsonify({"user": g.current_user.to_dict()})


@profile_blueprint.patch("")
@require_auth
def update_profile():
    """Atualiza nome e meta diária do usuário autenticado.
    ---
    tags: [Perfil]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          minProperties: 1
          properties:
            name: {type: string, minLength: 2, maxLength: 120}
            daily_goal_minutes: {type: integer, minimum: 1, maximum: 1439}
    responses:
      200: {description: Perfil atualizado, schema: {$ref: '#/definitions/ProfileResponse'}}
      400: {description: Nome ou meta inválidos, schema: {$ref: '#/definitions/Error'}}
      401: {description: Token ausente, inválido ou expirado, schema: {$ref: '#/definitions/Error'}}
      500: {description: Erro interno, schema: {$ref: '#/definitions/Error'}}
    """

    payload = json_object()
    if not payload or not set(payload) <= {"name", "daily_goal_minutes"}:
        raise ApiError("Informe nome e/ou meta diária.", 400, "invalid_profile")
    if "name" in payload:
        name = payload["name"]
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 120:
            raise ApiError("O nome deve ter entre 2 e 120 caracteres.", 400, "invalid_name")
        g.current_user.name = name.strip()
    if "daily_goal_minutes" in payload:
        goal = payload["daily_goal_minutes"]
        if type(goal) is not int or not 1 <= goal <= 1439:
            raise ApiError("A meta deve ser um inteiro entre 1 e 1439 minutos.", 400, "invalid_goal")
        g.current_user.daily_goal_minutes = goal
    db.session.commit()
    return jsonify({"user": g.current_user.to_dict()})
