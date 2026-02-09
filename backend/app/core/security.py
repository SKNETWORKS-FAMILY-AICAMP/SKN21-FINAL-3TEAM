"""
보안 유틸리티 (팀원 D 담당)
- JWT 토큰 생성/검증
- 비밀번호 해싱
- 데이터 암호화 (AES-256)
"""
from datetime import datetime, timedelta
from typing import Optional

from app.config import get_settings

settings = get_settings()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT 액세스 토큰 생성"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


def verify_token(token: str) -> dict:
    """JWT 토큰 검증"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


def hash_password(password: str) -> str:
    """비밀번호 해싱"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


def encrypt_data(data: str) -> str:
    """AES-256 암호화"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


def decrypt_data(encrypted_data: str) -> str:
    """AES-256 복호화"""
    # TODO: 팀원 D 구현
    raise NotImplementedError
