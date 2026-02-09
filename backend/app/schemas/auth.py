"""
인증 스키마 (팀원 D 정의)
"""
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class RegisterResponse(BaseModel):
    id: int
    email: str
    name: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str
