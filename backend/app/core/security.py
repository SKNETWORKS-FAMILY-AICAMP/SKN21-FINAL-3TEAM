"""
보안 유틸리티 (팀원 D 담당)
- JWT 토큰 생성/검증
- 비밀번호 해싱 (bcrypt)
- 데이터 암호화 (AES-256, OAuth 토큰 저장용)
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import base64

import jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet

from app.config import get_settings

settings = get_settings()

# bcrypt 해싱
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# AES 암호화 키 (Fernet은 32바이트 base64 키 필요)
_fernet_key = base64.urlsafe_b64encode(settings.ENCRYPTION_KEY.ljust(32)[:32].encode())
fernet = Fernet(_fernet_key)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT 액세스 토큰 생성"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """JWT 토큰 검증 — 유효하면 payload 반환, 아니면 None"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def hash_password(password: str) -> str:
    """비밀번호 해싱 (bcrypt)"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)


def encrypt_data(data: str) -> str:
    """AES-256 암호화 (OAuth 토큰 저장용)"""
    return fernet.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    """AES-256 복호화"""
    return fernet.decrypt(encrypted_data.encode()).decode()
