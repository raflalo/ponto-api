"""Configuração segura, sem uma chave de autenticação pública ou compartilhada."""

import os
import secrets
from pathlib import Path
from tempfile import NamedTemporaryFile


def jwt_secret(instance_path: str, configured: str | None = None) -> str:
    """Usa a chave informada ou cria uma chave local persistente e privada."""

    if configured is not None:
        if len(configured) < 32 or configured in {
            "dev-only-change-this-secret-before-production",
            "troque-por-uma-chave-longa-e-aleatoria",
        }:
            raise ValueError("JWT_SECRET_KEY deve ser uma chave própria, aleatória, com pelo menos 32 caracteres.")
        return configured
    path = Path(instance_path) / "jwt-secret"
    if path.exists():
        return jwt_secret(instance_path, path.read_text(encoding="utf-8").strip())
    # Publica somente o arquivo completo, evitando chaves diferentes entre workers.
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=instance_path, prefix=".jwt-secret-") as secret_file:
        value = secrets.token_urlsafe(48)
        secret_file.write(value)
        secret_file.flush()
        try:
            os.link(secret_file.name, path)
        except FileExistsError:
            return jwt_secret(instance_path, path.read_text(encoding="utf-8").strip())
    return value
