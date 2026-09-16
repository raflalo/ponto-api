"""Rotas públicas de cadastro e autenticação."""

from flask import Blueprint, jsonify
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..auth import create_access_token
from ..errors import ApiError
from ..extensions import db
from ..models import User
from ..validation import EMAIL_PATTERN, json_object, required_text

auth_blueprint = Blueprint("auth", __name__, url_prefix="/api/auth")


def valid_email(value: str) -> bool:
    """Executa a validação mínima adequada ao formulário do MVP."""

    return len(value) <= 255 and EMAIL_PATTERN.fullmatch(value) is not None


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
            name: {type: string, minLength: 2, maxLength: 120, example: Rafael Ferreira}
            email: {type: string, format: email, example: rafael@email.com}
            password: {type: string, format: password, minLength: 6, maxLength: 256}
    responses:
      201: {description: Usuário criado com sucesso, schema: {$ref: '#/definitions/AuthResponse'}}
      400: {description: Dados inválidos, schema: {$ref: '#/definitions/Error'}}
      409: {description: E-mail já cadastrado, schema: {$ref: '#/definitions/Error'}}
      500: {description: Erro interno, schema: {$ref: '#/definitions/Error'}}
    """

    payload = json_object()
    name = required_text(payload, "name", "seu nome")
    email = required_text(payload, "email", "seu e-mail").lower()
    password = required_text(payload, "password", "sua senha", trim=False)
    if not 2 <= len(name) <= 120:
        raise ApiError("O nome deve ter entre 2 e 120 caracteres.", 400, "invalid_name")
    if not valid_email(email):
        raise ApiError("Digite um e-mail válido.", 400, "invalid_email")
    if not 6 <= len(password) <= 256:
        raise ApiError("A senha deve ter entre 6 e 256 caracteres.", 400, "invalid_password")
    existing = db.session.scalar(select(User).where(func.lower(User.email) == email))
    if existing:
        raise ApiError("Este e-mail já está cadastrado.", 409, "email_in_use")
    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError("Este e-mail já está cadastrado.", 409, "email_in_use") from None
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
      200: {description: Login realizado, schema: {$ref: '#/definitions/AuthResponse'}}
      400: {description: Dados inválidos, schema: {$ref: '#/definitions/Error'}}
      401: {description: Credenciais incorretas, schema: {$ref: '#/definitions/Error'}}
      500: {description: Erro interno, schema: {$ref: '#/definitions/Error'}}
    """

    payload = json_object()
    email = required_text(payload, "email", "seu e-mail").lower()
    password = required_text(payload, "password", "sua senha", trim=False)
    if not valid_email(email) or len(password) > 256:
        raise ApiError("E-mail ou senha inválidos.", 400, "invalid_credentials")
    user = db.session.scalar(select(User).where(func.lower(User.email) == email))
    if user is None or not user.check_password(password):
        raise ApiError("E-mail ou senha incorretos.", 401, "invalid_credentials")
    return jsonify({"token": create_access_token(user.id), "user": user.to_dict()})
