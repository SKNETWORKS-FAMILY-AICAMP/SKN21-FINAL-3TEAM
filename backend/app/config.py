"""
앱 설정 (팀원 A 관리)
환경변수 기반 설정 관리
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "WorkFlow Agent API"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database (팀원 D)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/workflow_agent"

    # JWT (팀원 D)
    JWT_SECRET_KEY: str = "change-this-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Google OAuth (팀원 D)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # LLM API (공통 모듈)
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # vLLM (팀원 B — 4단계)
    VLLM_BASE_URL: str = "http://localhost:8080/v1"
    VLLM_MODEL_NAME: str = "Qwen/Qwen3-8B"

    # ChromaDB (팀원 B)
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # Redis (Task Queue)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Encryption (팀원 D)
    ENCRYPTION_KEY: str = "change-this-encryption-key"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
