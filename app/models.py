"""Modelos persistidos no SQLite pela API Ponto+."""

from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utc_now() -> datetime:
    """Retorna o instante atual em UTC com informação de fuso."""

    return datetime.now(timezone.utc)


class User(db.Model):
    """Pessoa autenticada que registra a própria jornada."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    punches = db.relationship(
        "Punch",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def set_password(self, password: str) -> None:
        """Armazena somente o hash seguro da senha."""

        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Compara a senha informada com o hash persistido."""

        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        """Expõe apenas dados seguros do perfil."""

        created_at = self.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "created_at": created_at.astimezone(timezone.utc).isoformat(),
        }


class Punch(db.Model):
    """Uma batida imutável dentro da sequência diária de jornada."""

    __tablename__ = "punches"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    type = db.Column(db.String(24), nullable=False)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    user = db.relationship("User", back_populates="punches")

    def to_dict(self) -> dict:
        """Serializa a batida usando datas ISO 8601 em UTC."""

        occurred_at = self.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        return {
            "id": self.id,
            "type": self.type,
            "occurred_at": occurred_at.astimezone(timezone.utc).isoformat(),
        }
