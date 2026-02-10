"""
인증 스키마 (팀원 D 정의)
"""
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class RegisterResponse(BaseModel):
    id: int
    email: str
    name: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str


# ── 비밀번호 재설정 ──


class PasswordResetRequest(BaseModel):
    """비밀번호 재설정 요청 — 이메일로 인증 코드 발송"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """비밀번호 재설정 확인 — 인증 코드 + 새 비밀번호"""
    email: EmailStr
    reset_code: str
    new_password: str


class PasswordResetResponse(BaseModel):
    """비밀번호 재설정 응답"""
    success: bool
    message: str
