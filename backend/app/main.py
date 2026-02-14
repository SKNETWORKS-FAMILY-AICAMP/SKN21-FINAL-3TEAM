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
