"""
FastAPI 메인 앱 (팀원 A 관리)
"""
import sys
import os
import warnings
from pathlib import Path  # noqa: E402

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
from fastapi.staticfiles import StaticFiles  # noqa: E402

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

# 업로드 파일 정적 서빙 (/uploads/avatars/... 접근 가능)
_upload_dir = str(Path(__file__).resolve().parent.parent / "uploads")
os.makedirs(_upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_upload_dir), name="uploads")


@app.on_event("startup")
async def startup_db_migrations():
    """서버 시작 시 DB 마이그레이션 — 하나의 커넥션으로 모든 DDL 실행"""
    import asyncio

    try:
        from app.db.session import engine
        import app.models  # noqa: F401
        from app.db.base import Base
        from sqlalchemy import text

        await asyncio.wait_for(_run_migrations(engine, Base, text), timeout=30)
    except asyncio.TimeoutError:
        print("[Startup] DB 마이그레이션 타임아웃 (30초 초과, 건너뜀)")
    except Exception as _e:
        print(f"[Startup] DB 마이그레이션 실패 (무시하고 계속): {_e}")

    # 시스템 템플릿 시딩
    try:
        from app.db.session import async_session
        from app.services.template_service import ensure_system_templates
        async with async_session() as db:
            await ensure_system_templates(db)
        print("[Startup] 시스템 템플릿 시딩 완료")
    except Exception as _e:
        print(f"[Startup] 템플릿 시딩 실패 (무시하고 계속): {_e}")


async def _run_migrations(engine, Base, text):
    """단일 커넥션으로 모든 DDL을 실행하여 커넥션 점유 최소화"""
    async with engine.begin() as conn:
        # 테이블 생성
        await conn.run_sync(Base.metadata.create_all)
        print("[Startup] DB 테이블 확인/생성 완료")

        # documents 분석 컬럼
        await conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS category VARCHAR(50)"))
        await conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS tags JSON"))
        await conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary TEXT"))

        # users 컬럼
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS team VARCHAR(50)"))
        await conn.execute(text(
            "UPDATE users SET team = "
            "(ARRAY['개발','QA기획','UI/UX','영업','마케팅','CS'])"
            "[floor(random() * 6 + 1)::int] "
            "WHERE team IS NULL"
        ))
        await conn.execute(text("ALTER TABLE users ALTER COLUMN avatar TYPE TEXT"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS slack_enabled BOOLEAN DEFAULT FALSE"))

        # action_items
        await conn.execute(text(
            "ALTER TABLE action_items ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id)"
        ))
        await conn.execute(text("DELETE FROM action_items WHERE created_by IS NULL"))

        # pipeline_tasks
        await conn.execute(text("ALTER TABLE pipeline_tasks ADD COLUMN IF NOT EXISTS project VARCHAR(300)"))

        # approval_requests
        await conn.execute(text("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS file_path VARCHAR(1000)"))
        await conn.execute(text("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS file_name VARCHAR(500)"))

        print("[Startup] DB 마이그레이션 전체 완료")


@app.on_event("startup")
async def startup_slack_scheduler():
    """Slack 마감 알림 스케줄러 (매일 오전 9시 KST)"""
    import asyncio
    from datetime import datetime, timezone, timedelta

    KST = timezone(timedelta(hours=9))

    async def _scheduler():
        while True:
            now = datetime.now(KST)
            target = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            print(f"[Slack Scheduler] 다음 실행까지 {wait_seconds:.0f}초 대기 ({target.strftime('%Y-%m-%d %H:%M')} KST)")
            await asyncio.sleep(wait_seconds)

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
    """서버 시작 시 RAG 파이프라인 pre-loading — 백그라운드로 실행하여 서버 즉시 가동

    get_qdrant_pipeline() → initialize() 내부에서:
      1) 임베딩 모델 로드
      2) Qdrant 컬렉션 초기화
      3) BM25 인덱스 구축 (Qdrant에서 전체 문서 조회 → 토크나이징)
    를 모두 수행하므로, 별도 reindex_all_documents()는 불필요.
    (Qdrant는 영속 스토리지이므로 매 startup마다 임베딩 재생성/upsert 불필요)

    Note: reindex_all_documents()는 DB→Qdrant 재동기화가 필요한 경우에만
    관리자 API(POST /api/v1/documents/reindex-all)로 수동 실행.
    """
    import asyncio

    async def _background_preload():
        import time
        await asyncio.sleep(3)  # 서버가 먼저 요청을 받을 수 있도록 대기
        print("[Background] RAG 파이프라인 pre-loading 시작...")
        _t = time.time()

        try:
            from ai.rag.qdrant_pipeline import get_qdrant_pipeline
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, get_qdrant_pipeline),
                timeout=60
            )
            print(f"[Background] RAG 파이프라인 로드 완료 — 임베딩+Qdrant+BM25 ({time.time()-_t:.2f}s)")
        except asyncio.TimeoutError:
            print("[Background] RAG 파이프라인 로드 타임아웃 (60초 초과, 건너뜀)")
        except Exception as e:
            print(f"[Background] RAG 파이프라인 로드 실패 (서비스는 계속 가능): {e}")

    asyncio.create_task(_background_preload())
    print("[Startup] RAG pre-loading 백그라운드 등록 완료 (서버 즉시 가동)")

@app.on_event("shutdown")
async def shutdown_dispose_engine():
    """서버 종료 시 커넥션 풀 정리"""
    from app.db.session import engine
    await engine.dispose()
    print("[Shutdown] DB 커넥션 풀 정리 완료")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
