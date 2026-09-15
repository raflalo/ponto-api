"""Erros de domínio e respostas JSON padronizadas."""

from dataclasses import dataclass

from flask import Flask, jsonify
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db


@dataclass
class ApiError(Exception):
    """Representa uma falha esperada que pode ser mostrada ao cliente."""

    message: str
    status_code: int = 400
    code: str = "bad_request"


def error_payload(error: ApiError):
    """Converte um erro de domínio para o contrato público da API."""

    return jsonify({"error": {"code": error.code, "message": error.message}}), error.status_code


def register_error_handlers(app: Flask) -> None:
    """Registra os tratadores globais sem expor detalhes internos."""

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return error_payload(error)

    @app.errorhandler(404)
    def handle_not_found(_error):
        return error_payload(ApiError("Recurso não encontrado.", 404, "not_found"))

    @app.errorhandler(405)
    def handle_method_not_allowed(_error):
        return error_payload(ApiError("Método não permitido para esta rota.", 405, "method_not_allowed"))

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(_error):
        db.session.rollback()
        return error_payload(ApiError("Não foi possível acessar o banco de dados.", 500, "database_error"))

    @app.errorhandler(Exception)
    def handle_unexpected_error(_error):
        return error_payload(ApiError("Ocorreu um erro interno inesperado.", 500, "internal_error"))
