"""Atualizações aditivas do banco local, preservando usuários e batidas."""

from sqlalchemy import inspect

from .extensions import db


def upgrade_database() -> None:
    """Acrescenta preferências e revisão de jornada aos bancos anteriores."""

    with db.engine.begin() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("users")}
        if "daily_goal_minutes" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN daily_goal_minutes INTEGER NOT NULL DEFAULT 480 "
                "CHECK (daily_goal_minutes BETWEEN 1 AND 1439)"
            )
        if "punch_revision" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN punch_revision INTEGER NOT NULL DEFAULT 0"
            )
