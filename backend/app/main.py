"""
FastAPI 메인 앱 (팀원 A 관리)
"""
import sys
import os
import warnings
from pathlib import Path

# 경고 메시지 억제
warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"  # TensorFlow 경고 억제

# 프로젝트 루트를 PYTHONPATH에 추가 (ai 모듈 import를 위해)
project_root = Path(__file__).resolve().parents[2]

# .env 파일 로드 (os.getenv()로 접근하는 모든 모듈에서 사용 가능)
from dotenv import load_dotenv  # noqa: E402
load_dotenv(project_root / ".env")
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.api.v1.router import api_router  # noqa: E402

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.on_event("startup")
async def startup_ensure_tables():
    """서버 시작 시 누락된 테이블 자동 생성 (create_all은 기존 테이블 건드리지 않음)"""
    try:
        from app.db.session import engine
        import app.models  # noqa: F401 — 모든 모델 import (Alembic과 동일)
        from app.db.base import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[Startup] DB 테이블 확인/생성 완료")
    except Exception as _e:
        print(f"[Startup] DB 테이블 생성 실패 (무시하고 계속): {_e}")


@app.on_event("startup")
async def startup_migrate_team_column():
    """users.team 컬럼 추가 및 기존 사용자 랜덤 팀 배정"""
    try:
        from app.db.session import engine
        from sqlalchemy import text

        async with engine.begin() as conn:
            # 컬럼 없으면 추가 (PostgreSQL IF NOT EXISTS)
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS team VARCHAR(50)"
            ))
            # team이 NULL인 기존 사용자에게 랜덤 배정
            await conn.execute(text(
                "UPDATE users SET team = "
                "(ARRAY['개발','QA기획','UI/UX','영업','마케팅','CS'])"
                "[floor(random() * 6 + 1)::int] "
                "WHERE team IS NULL"
            ))
        print("[Startup] users.team 컬럼 추가 및 랜덤 배정 완료")
    except Exception as _e:
        print(f"[Startup] users.team 처리 실패 (무시하고 계속): {_e}")


@app.on_event("startup")
async def startup_migrate_slack_column():
    """users.slack_enabled 컬럼 추가"""
    try:
        from app.db.session import engine
        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS slack_enabled BOOLEAN DEFAULT FALSE"
            ))
        print("[Startup] users.slack_enabled 컬럼 확인/추가 완료")
    except Exception as _e:
        print(f"[Startup] slack_enabled 처리 실패 (무시하고 계속): {_e}")


@app.on_event("startup")
async def startup_slack_scheduler():
    """Slack 마감 알림 스케줄러 (매일 오전 9시 KST)"""
    import asyncio
    from datetime import datetime, timezone, timedelta

    KST = timezone(timedelta(hours=9))

    async def _scheduler():
        while True:
            now = datetime.now(KST)
            # 다음 오전 9시까지 대기
            target = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            print(f"[Slack Scheduler] 다음 실행까지 {wait_seconds:.0f}초 대기 ({target.strftime('%Y-%m-%d %H:%M')} KST)")
            await asyncio.sleep(wait_seconds)

            # 실행
            try:
                from app.db.session import async_session
                from app.services.slack_service import check_and_notify_deadlines

                async with async_session() as db:
                    await check_and_notify_deadlines(db)
                    await db.commit()
                print("[Slack Scheduler] 마감 알림 체크 완료")
            except Exception as e:
                print(f"[Slack Scheduler] 실행 실패: {e}")

    asyncio.create_task(_scheduler())
    print("[Startup] Slack 마감 알림 스케줄러 등록 완료")


@app.on_event("startup")
async def startup_preload():
    """서버 시작 시 모델 pre-loading (첫 요청 지연 방지)"""
    import time

    print("[Startup] 모델 pre-loading 시작...")
    _t = time.time()

    try:
        from ai.rag.qdrant_pipeline import get_qdrant_pipeline

        get_qdrant_pipeline()
        print(f"[Startup] RAG 파이프라인 로드 완료 ({time.time()-_t:.2f}s)")
    except Exception as e:
        print(f"[Startup] RAG 파이프라인 로드 실패 (서비스는 계속 가능): {e}")

    print(f"[Startup] 모델 pre-loading 완료 (총 {time.time()-_t:.2f}s)")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
