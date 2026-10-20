"""Валидация входящих запросов до обращения к базе данных."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

Mode = Literal["words", "sentences", "text", "code", "symbols"]


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        local, separator, domain = value.partition("@")
        if not separator or not local or "." not in domain or "@" in domain or any(c.isspace() for c in value):
            raise ValueError("Введите корректный email")
        return value


class RegisterRequest(LoginRequest):
    password: str = Field(min_length=6, max_length=128)
    nickname: str | None = Field(default=None, min_length=3, max_length=20)

    @field_validator("nickname")
    @classmethod
    def normalize_nickname(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if len(value) < 3:
                raise ValueError("Никнейм должен содержать от 3 до 20 символов")
        return value


class SessionResult(BaseModel):
    speed_wpm: float = Field(ge=0, le=10000, allow_inf_nan=False)
    accuracy_pct: float = Field(ge=0, le=100, allow_inf_nan=False)
    max_combo: int = Field(default=0, ge=0, le=1000000)
    errors_json: dict[str, Annotated[int, Field(ge=0, le=1000000)]] = Field(default_factory=dict)
    mode: Mode = "words"
    duration_seconds: float = Field(default=0, ge=0, le=86400, allow_inf_nan=False)
