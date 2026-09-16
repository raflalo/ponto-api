"""Fábrica da aplicação Flask do Ponto+."""

import os
from pathlib import Path

from flasgger import Swagger
from flask import Flask, jsonify
from flask_cors import CORS

from .errors import register_error_handlers
from .configuration import jwt_secret
from .extensions import db
from .migrations import upgrade_database
from .openapi import DEFINITIONS
from .routes.auth import auth_blueprint
from .routes.profile import profile_blueprint
from .routes.punches import punches_blueprint


def create_app(test_config: dict | None = None) -> Flask:
    """Cria uma instância configurada da API e inicializa suas extensões."""

    app = Flask(__name__, instance_relative_config=True,
                instance_path=(test_config or {}).get("INSTANCE_PATH"))
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    default_database = Path(app.instance_path) / "ponto_plus.db"
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", f"sqlite:///{default_database}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY"),
        JWT_EXPIRES_HOURS=24,
        SWAGGER={"title": "Ponto+ API", "uiversion": 3},
    )
    if test_config:
        app.config.update(test_config)
    app.config["JWT_SECRET_KEY"] = jwt_secret(app.instance_path, app.config["JWT_SECRET_KEY"])

    db.init_app(app)
    CORS(
        app,
        resources={r"/api/*": {"origins": ["null", r"https?://(localhost|127\.0\.0\.1)(:\d+)?"]}},
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    )
    Swagger(
        app,
        template={
            "swagger": "2.0",
            "consumes": ["application/json"],
            "produces": ["application/json"],
            "definitions": DEFINITIONS,
            "info": {
                "title": "Ponto+ API",
                "description": "API para autenticação, perfil e registro pessoal de jornada.",
                "version": "1.0.0",
            },
            "securityDefinitions": {
                "Bearer": {
                    "type": "apiKey",
                    "name": "Authorization",
                    "in": "header",
                    "description": "Use: Bearer <token>",
                }
            },
        },
    )
    register_error_handlers(app)
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(profile_blueprint)
    app.register_blueprint(punches_blueprint)

    @app.get("/api/health")
    def health():
        """Confirma que o processo da API está disponível.
        ---
        tags: [Sistema]
        responses:
          200: {description: API disponível, schema: {$ref: '#/definitions/Health'}}
          500: {description: Erro interno, schema: {$ref: '#/definitions/Error'}}
        """

        return jsonify({"status": "ok"})

    with app.app_context():
        db.create_all()
        upgrade_database()

    return app
