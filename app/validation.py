"""Validações compartilhadas dos contratos de entrada da API."""

import re

from flask import request

from .errors import ApiError

EMAIL_PATTERN = re.compile(r"[^\s@]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", re.I)


def json_object(optional: bool = False) -> dict:
    """Rejeita JSON inválido ou que não represente um objeto."""

    if optional and not request.get_data():
        return {}
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError("Envie um objeto JSON válido.", 400, "invalid_body")
    return payload


def required_text(payload: dict, field: str, label: str, *, trim: bool = True) -> str:
    """Normaliza textos, preservando exatamente os caracteres das senhas."""

    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f"Informe {label}.", 400, f"invalid_{field}")
    return value.strip() if trim else value


def expected_revision(value) -> int | None:
    """Valida a revisão opcional para impedir ações sobre uma jornada desatualizada."""

    if value is not None and (type(value) is not int or value < 0):
        raise ApiError("A revisão da jornada deve ser um inteiro não negativo.", 400, "invalid_revision")
    return value
