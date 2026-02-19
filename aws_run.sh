#!/bin/bash
# FastAPI 서버 실행 스크립트 (Linux/Mac)
# 사용법: bash run.sh

cd "$(dirname "$0")"

source .venv/bin/activate

export PYTHONPATH=$(pwd)/backend

uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
