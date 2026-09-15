"""Criação e validação de tokens JWT da API."""

from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from .errors import ApiError
from .extensions import db
from .models import User


def create_access_token(user_id: int) -> str:
    """Cria um token com validade configurável, de 24 horas por padrão."""

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=current_app.config["JWT_EXPIRES_HOURS"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def require_auth(view):
    """Protege uma rota e disponibiliza o usuário autenticado em ``g``."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise ApiError("Token de acesso não informado.", 401, "missing_token")
        token = authorization.removeprefix("Bearer ").strip()
        try:
            payload = jwt.decode(
                token,
                current_app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"],
            )
            user_id = int(payload["sub"])
        except jwt.ExpiredSignatureError as error:
            raise ApiError("Sua sessão expirou. Entre novamente.", 401, "expired_token") from error
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
            raise ApiError("Token de acesso inválido.", 401, "invalid_token") from error

        user = db.session.get(User, user_id)
        if user is None:
            raise ApiError("Usuário da sessão não foi encontrado.", 401, "invalid_session")
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped
