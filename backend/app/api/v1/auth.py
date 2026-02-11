"""
인증 API (팀원 D 담당)
- JWT 로그인/회원가입/토큰 갱신
- 비밀번호 재설정
- Google OAuth 2.0
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordResetResponse,
)
from app.db.session import get_db
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token, verify_token
from app.api.deps import get_current_user

router = APIRouter()

# 임시 비밀번호 재설정 코드 저장 (추후 Redis로 교체)
_reset_codes: dict[str, str] = {}


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """회원가입"""
    # 이메일 중복 체크
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 등록된 이메일입니다",
        )

    user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
        name=request.name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return RegisterResponse(id=user.id, email=user.email, name=user.name)


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """로그인 (JWT 발급)"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다",
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_name=user.name,
    )


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """현재 로그인된 사용자 정보"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "is_admin": current_user.is_admin,
    }


# ── 비밀번호 재설정 ──


@router.post("/password-reset/request", response_model=PasswordResetResponse)
async def request_password_reset(
    request: PasswordResetRequest, db: AsyncSession = Depends(get_db)
):
    """비밀번호 재설정 요청 — 인증 코드 발급"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    # 사용자 존재 여부와 무관하게 동일 응답 (이메일 노출 방지)
    if user is None:
        return PasswordResetResponse(success=True, message="등록된 이메일이면 인증 코드가 발송됩니다")

    # 6자리 인증 코드 생성
    reset_code = secrets.token_hex(3).upper()  # 예: "A1B2C3"
    _reset_codes[request.email] = reset_code

    # TODO: Gmail API로 실제 이메일 발송 (3단계 Google Services 연동 시)
    # 현재는 로그로 출력
    print(f"[DEBUG] 비밀번호 재설정 코드: {request.email} → {reset_code}")

    return PasswordResetResponse(success=True, message="등록된 이메일이면 인증 코드가 발송됩니다")


@router.post("/password-reset/confirm", response_model=PasswordResetResponse)
async def confirm_password_reset(
    request: PasswordResetConfirm, db: AsyncSession = Depends(get_db)
):
    """비밀번호 재설정 확인 — 인증 코드 검증 + 비밀번호 변경"""
    stored_code = _reset_codes.get(request.email)
    if stored_code is None or stored_code != request.reset_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="인증 코드가 유효하지 않습니다",
        )

    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다",
        )

    user.hashed_password = hash_password(request.new_password)
    del _reset_codes[request.email]

    return PasswordResetResponse(success=True, message="비밀번호가 변경되었습니다")
