@echo off
REM FastAPI 서버 실행 스크립트
REM 사용법: backend\run.bat

cd /d "%~dp0"
call .venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
