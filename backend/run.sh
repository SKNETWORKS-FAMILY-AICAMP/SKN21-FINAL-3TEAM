#!/bin/bash
# FastAPI 서버 실행 스크립트
# 사용법: ./run.sh

cd "$(dirname "$0")"
source ../.venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
