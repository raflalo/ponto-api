"""Modelos públicos de requisição e resposta utilizados pelo Swagger."""

DEFINITIONS = {
    "Error": {
        "type": "object", "required": ["error"],
        "properties": {"error": {"type": "object", "required": ["code", "message"], "properties": {
            "code": {"type": "string", "example": "invalid_body"},
            "message": {"type": "string", "example": "Envie um objeto JSON válido."},
        }}},
    },
    "User": {
        "type": "object", "required": ["id", "name", "email", "created_at", "daily_goal_minutes"],
        "properties": {
            "id": {"type": "integer"}, "name": {"type": "string"},
            "email": {"type": "string", "format": "email"},
            "created_at": {"type": "string", "format": "date-time"},
            "daily_goal_minutes": {"type": "integer", "minimum": 1, "maximum": 1439, "example": 480},
        },
    },
    "ProfileResponse": {"type": "object", "required": ["user"], "properties": {"user": {"$ref": "#/definitions/User"}}},
    "AuthResponse": {"type": "object", "required": ["token", "user"], "properties": {
        "token": {"type": "string", "description": "JWT com validade de 24 horas."},
        "user": {"$ref": "#/definitions/User"},
    }},
    "Punch": {"type": "object", "required": ["id", "type", "occurred_at"], "properties": {
        "id": {"type": "integer"},
        "type": {"type": "string", "enum": ["clock_in", "break_start", "break_end", "clock_out"]},
        "occurred_at": {"type": "string", "format": "date-time", "description": "Horário UTC atribuído pelo servidor."},
    }},
    "Today": {"type": "object", "required": ["date", "punches", "revision", "status", "next_action", "next_action_label", "worked_seconds", "can_punch"], "properties": {
        "date": {"type": "string", "format": "date", "description": "Data em America/Sao_Paulo."},
        "punches": {"type": "array", "items": {"$ref": "#/definitions/Punch"}},
        "revision": {"type": "integer", "minimum": 0},
        "status": {"type": "string", "enum": ["not_started", "working", "on_break", "finished"]},
        "next_action": {"type": "string", "x-nullable": True, "description": "Próximo tipo de batida ou null quando encerrada."},
        "next_action_label": {"type": "string"},
        "worked_seconds": {"type": "integer", "minimum": 0},
        "can_punch": {"type": "boolean"},
    }},
    "HistoryResponse": {"type": "object", "required": ["month", "punches", "today", "server_time"], "properties": {
        "month": {"type": "string", "example": "2026-09"},
        "punches": {"type": "array", "items": {"$ref": "#/definitions/Punch"}},
        "today": {"$ref": "#/definitions/Today"},
        "server_time": {"type": "string", "format": "date-time"},
    }},
    "PunchResponse": {"type": "object", "required": ["punch", "today", "server_time"], "properties": {
        "punch": {"$ref": "#/definitions/Punch"}, "today": {"$ref": "#/definitions/Today"},
        "server_time": {"type": "string", "format": "date-time"},
    }},
    "Health": {"type": "object", "required": ["status"], "properties": {"status": {"type": "string", "enum": ["ok"]}}},
}
