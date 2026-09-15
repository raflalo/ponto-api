"""Rotas públicas de cadastro e autenticação."""

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from ..auth import create_access_token
from ..errors import ApiError
from ..extensions import db
from ..models import User

auth_blueprint = Blueprint("auth", __name__, url_prefix="/api/auth")


def required_text(payload: dict, field: str, label: str) -> str:
    """Lê e normaliza um campo textual obrigatório."""

    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f"Informe {label}.", 400, f"invalid_{field}")
    return value.strip()


def valid_email(value: str) -> bool:
    """Executa a validação mínima adequada ao formulário do MVP."""

    local, separator, domain = value.partition("@")
    return bool(local and separator and "." in domain and not value.endswith("."))


@auth_blueprint.post("/register")
def register():
    """Cadastra um usuário e devolve sua primeira sessão.
    ---
    tags: [Autenticação]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [name, email, password]
          properties:
            name: {type: string, example: Rafael Ferreira}
            email: {type: string, format: email, example: rafael@email.com}
            password: {type: string, format: password, minLength: 6}
    responses:
      201: {description: Usuário criado com sucesso}
      400: {description: Dados inválidos}
      409: {description: E-mail já cadastrado}
    """

    payload = request.get_json(silent=True) or {}
    name = required_text(payload, "name", "seu nome")
    email = required_text(payload, "email", "seu e-mail").lower()
    password = required_text(payload, "password", "sua senha")
    if len(name) < 2:
        raise ApiError("O nome deve ter pelo menos 2 caracteres.", 400, "invalid_name")
    if not valid_email(email):
        raise ApiError("Digite um e-mail válido.", 400, "invalid_email")
    if len(password) < 6:
        raise ApiError("A senha deve ter pelo menos 6 caracteres.", 400, "invalid_password")
    existing = db.session.scalar(select(User).where(func.lower(User.email) == email))
    if existing:
        raise ApiError("Este e-mail já está cadastrado.", 409, "email_in_use")
    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"token": create_access_token(user.id), "user": user.to_dict()}), 201


@auth_blueprint.post("/login")
def login():
    """Autentica um usuário cadastrado.
    ---
    tags: [Autenticação]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [email, password]
          properties:
            email: {type: string, format: email}
            password: {type: string, format: password}
    responses:
      200: {description: Login realizado}
      400: {description: Dados inválidos}
      401: {description: Credenciais incorretas}
    """

    payload = request.get_json(silent=True) or {}
    email = required_text(payload, "email", "seu e-mail").lower()
    password = required_text(payload, "password", "sua senha")
    user = db.session.scalar(select(User).where(func.lower(User.email) == email))
    if user is None or not user.check_password(password):
        raise ApiError("E-mail ou senha incorretos.", 401, "invalid_credentials")
    return jsonify({"token": create_access_token(user.id), "user": user.to_dict()})
