"""Authentication request and response schemas."""

from pydantic import BaseModel, Field


class TelegramAuthRequest(BaseModel):
    """Raw Telegram Mini App initData."""

    init_data: str = Field(min_length=1, max_length=8192)


class CustomerTokenResponse(BaseModel):
    """Short-lived customer access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminLoginRequest(BaseModel):
    """Admin username and password."""

    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class AdminLoginResponse(BaseModel):
    """Admin authentication status without exposing tokens in JSON."""

    authenticated: bool = True
    role: str
    username: str
