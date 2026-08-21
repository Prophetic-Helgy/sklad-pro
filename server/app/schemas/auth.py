"""Схемы авторизации."""
from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    role: str
    active: bool

    model_config = {"from_attributes": True}


class MeOut(UserOut):
    """Текущий пользователь (для UI: меню, права)."""
