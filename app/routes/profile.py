"""Consulta e atualização do perfil autenticado."""

from flask import Blueprint, g, jsonify, request

from ..auth import require_auth
from ..errors import ApiError
from ..extensions import db

profile_blueprint = Blueprint("profile", __name__, url_prefix="/api/profile")


@profile_blueprint.get("")
@require_auth
def get_profile():
    """Retorna o perfil da sessão atual.
    ---
    tags: [Perfil]
    security: [{Bearer: []}]
    responses:
      200: {description: Perfil encontrado}
      401: {description: Token ausente, inválido ou expirado}
    """

    return jsonify({"user": g.current_user.to_dict()})


@profile_blueprint.patch("")
@require_auth
def update_profile():
    """Atualiza o nome do usuário autenticado.
    ---
    tags: [Perfil]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [name]
          properties:
            name: {type: string, minLength: 2}
    responses:
      200: {description: Perfil atualizado}
      400: {description: Nome inválido}
      401: {description: Token ausente, inválido ou expirado}
    """

    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    if not isinstance(name, str) or len(name.strip()) < 2:
        raise ApiError("O nome deve ter pelo menos 2 caracteres.", 400, "invalid_name")
    g.current_user.name = name.strip()
    db.session.commit()
    return jsonify({"user": g.current_user.to_dict()})
