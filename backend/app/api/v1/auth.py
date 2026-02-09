"""
인증 API (팀원 D 담당)
- JWT 로그인/회원가입/토큰 갱신
- Google OAuth 2.0
"""
from fastapi import APIRouter, Depends

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    TokenRefreshRequest,
)
from app.db.session import get_db

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest, db=Depends(get_db)):
    """회원가입"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db=Depends(get_db)):
    """로그인 (JWT 발급)"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(request: TokenRefreshRequest):
    """토큰 갱신"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.get("/google")
async def google_login():
    """Google OAuth 로그인 시작"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


@router.get("/google/callback")
async def google_callback(code: str, db=Depends(get_db)):
    """Google OAuth 콜백"""
    # TODO: 팀원 D 구현
    raise NotImplementedError


# ── UI_UX.pdf 추가 엔드포인트 ──


@router.post("/password-reset/request")
async def request_password_reset(email: str, db=Depends(get_db)):
    """
    비밀번호 재설정 요청 (이메일 발송)

    UI_UX.pdf: "비밀번호 찾기"
    """
    # TODO: 팀원 D 구현
    # 1. 이메일로 사용자 확인
    # 2. 재설정 토큰 생성 + DB 저장
    # 3. 이메일 발송 (재설정 링크)
    raise NotImplementedError


@router.post("/password-reset/confirm")
async def confirm_password_reset(token: str, new_password: str, db=Depends(get_db)):
    """
    비밀번호 재설정 확인

    UI_UX.pdf: "비밀번호 변경"
    """
    # TODO: 팀원 D 구현
    # 1. 토큰 유효성 확인
    # 2. 새 비밀번호 해싱 + DB 업데이트
    raise NotImplementedError
