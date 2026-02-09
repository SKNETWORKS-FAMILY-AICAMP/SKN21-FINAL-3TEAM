"""
미들웨어 (팀원 A 관리)
- 에러 핸들링
- 요청 로깅
"""
from fastapi import Request
from fastapi.responses import JSONResponse


async def error_handler(request: Request, exc: Exception):
    """글로벌 에러 핸들러"""
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
