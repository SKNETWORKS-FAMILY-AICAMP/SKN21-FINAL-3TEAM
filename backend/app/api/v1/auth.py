"""
인증 API (팀원 D 담당)
- JWT 로그인/회원가입/토큰 갱신
- 비밀번호 재설정
- Google OAuth 2.0 소셜 로그인
"""
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
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
    ChangePasswordRequest,
)
from app.config import get_settings
from app.db.session import get_db
from app.models.oauth_token import OAuthToken
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token, encrypt_data
from app.api.deps import get_current_user
from app.services.google_base_service import GOOGLE_SCOPES

settings = get_settings()
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
        team=request.team,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return RegisterResponse(id=user.id, email=user.email, name=user.name, team=user.team)


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
        "team": current_user.team,
        "is_admin": current_user.is_admin,
    }


@router.get("/team-members")
async def get_team_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 로그인한 사용자의 소속 팀원 목록 조회"""
    if not current_user.team:
        return []
    
    result = await db.execute(select(User).where(User.team == current_user.team))
    team_members = result.scalars().all()
    
    return [
        {
            "id": member.id,
            "email": member.email,
            "name": member.name,
            "team": member.team,
            "phone": member.phone,
            "address": member.address,
            "avatar": member.avatar,
            "role": member.role,
            "is_active": member.is_active,
        }
        for member in team_members if member.is_active
    ]


@router.get("/all-members")
async def get_all_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """전체 활성 사용자 목록 (Pipeline 담당자 선택용)"""
    result = await db.execute(select(User).where(User.is_active == True).order_by(User.name))
    members = result.scalars().all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "team": m.team,
            "avatar": m.avatar,
        }
        for m in members
    ]


# ── 비밀번호 변경 (로그인 상태에서) ──


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비밀번호 변경 — 현재 비밀번호 확인 후 새 비밀번호로 변경"""
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 올바르지 않습니다",
        )
    if len(request.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="새 비밀번호는 6자 이상이어야 합니다",
        )

    current_user.hashed_password = hash_password(request.new_password)
    await db.commit()
    return {"message": "비밀번호가 변경되었습니다"}


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
    # token(인증 코드)으로 이메일 역조회
    target_email = None
    for email, code in _reset_codes.items():
        if code == request.token:
            target_email = email
            break

    if target_email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="인증 코드가 유효하지 않습니다",
        )

    result = await db.execute(select(User).where(User.email == target_email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다",
        )

    user.hashed_password = hash_password(request.new_password)
    del _reset_codes[target_email]

    return PasswordResetResponse(success=True, message="비밀번호가 변경되었습니다")


# ── Google 소셜 로그인 ──




@router.get("/google")
async def google_login():
    """Google 소셜 로그인 — Google 동의 화면으로 리다이렉트 (서비스 스코프 포함)"""
    # 로그인 기본 스코프 + 서비스 스코프(calendar, tasks, gmail, sheets)를 한번에 요청
    scope_parts = ["openid", "email", "profile"] + list(GOOGLE_SCOPES.values())
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_LOGIN_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scope_parts),
        "access_type": "offline",
        "prompt": "consent",
    }
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@router.get("/google/callback")
async def google_login_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Google 소셜 로그인 콜백 — code → 유저 정보 → JWT 발급"""
    # 1. authorization code → access_token 교환
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_LOGIN_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=google_token_failed")

    token_data = token_resp.json()
    access_token = token_data.get("access_token")

    # 2. access_token → Google 유저 정보 조회
    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_resp.status_code != 200:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=google_userinfo_failed")

    google_user = userinfo_resp.json()
    email = google_user.get("email")
    name = google_user.get("name", email.split("@")[0])

    # 3. DB에서 유저 찾기 (없으면 자동 생성)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        # Google 로그인으로 자동 회원가입 (비밀번호는 랜덤 — 소셜 전용)
        user = User(
            email=email,
            hashed_password=hash_password(secrets.token_hex(16)),
            name=name,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

    if not user.is_active:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=inactive_account")

    # 4. OAuthToken 저장 (Google 서비스 자동 연동)
    google_access_token = token_data.get("access_token")
    google_refresh_token = token_data.get("refresh_token")

    expires_at = None
    if "expires_in" in token_data:
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            seconds=token_data["expires_in"]
        )

    all_scope_keys = sorted(GOOGLE_SCOPES.keys())  # calendar, gmail_send, sheets, tasks
    scopes_str = ",".join(all_scope_keys)

    result_token = await db.execute(
        select(OAuthToken).where(OAuthToken.user_id == user.id)
    )
    existing_token = result_token.scalar_one_or_none()

    if existing_token:
        existing_token.access_token = encrypt_data(google_access_token)
        if google_refresh_token:
            existing_token.refresh_token = encrypt_data(google_refresh_token)
        existing_token.expires_at = expires_at
        # 기존 스코프와 병합
        existing_scopes = set(existing_token.scopes.split(",")) if existing_token.scopes else set()
        merged_scopes = existing_scopes | set(all_scope_keys)
        existing_token.scopes = ",".join(sorted(merged_scopes))
    else:
        oauth_token = OAuthToken(
            user_id=user.id,
            provider="google",
            access_token=encrypt_data(google_access_token),
            refresh_token=encrypt_data(google_refresh_token) if google_refresh_token else None,
            expires_at=expires_at,
            scopes=scopes_str,
        )
        db.add(oauth_token)

    await db.flush()

    # 5. JWT 발급 → 프론트엔드로 리다이렉트 (토큰을 URL에 포함)
    jwt_token = create_access_token(data={"sub": str(user.id)})
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/login?token={jwt_token}&user_name={name}"
    )
