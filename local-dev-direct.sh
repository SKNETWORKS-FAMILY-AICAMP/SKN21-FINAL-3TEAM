#!/bin/bash
# 로컬 개발용 (RDS 직접 연결 — SSH 터널 불필요)
# 사용법: bash local-dev-direct.sh
# 종료: Ctrl+C → 자동으로 EC2(SSH) 모드로 복원
#
# 전제: RDS 서브넷 라우팅 테이블에 IGW 경로 추가됨
#       RDS 보안 그룹에 현재 PC IP 등록됨

cd "$(dirname "$0")"

ENV_LOCAL="frontend/.env.local"
ENV_FILE=".env"

DB_PAT_EC2='postgresql+asyncpg://postgre:dudu123!@dudu-db.c3kow4uoyb3s.ap-northeast-2.rds.amazonaws.com:5432/workflow_agent?ssl=require'
DB_PAT_LOCAL='postgresql+asyncpg://postgre:dudu123!@localhost:5432/workflow_agent'

# ── EC2 모드 복원 ──
if [ "$1" = "--ec2" ]; then
  echo "=== EC2(SSH) 모드로 복원 ==="
  sed -i 's|BACKEND_URL=http://localhost:8000|BACKEND_URL=http://3.37.118.197:8000|' "$ENV_LOCAL"
  sed -i "s|${DB_PAT_LOCAL}|${DB_PAT_EC2}|" "$ENV_FILE"
  echo "BACKEND_URL → EC2 (3.37.118.197:8000)"
  echo "DATABASE_URL → RDS 직접 연결 복원"
  exit 0
fi

echo "=== 로컬 개발 모드 (RDS 직접) ==="

cleanup() {
  echo ""
  echo "=== 종료 + EC2(SSH) 모드 복원 ==="
  [ -n "$BACKEND_PID" ]  && kill $BACKEND_PID 2>/dev/null
  [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null

  # EC2 모드로 복원
  sed -i 's|BACKEND_URL=http://localhost:8000|BACKEND_URL=http://3.37.118.197:8000|' "$ENV_LOCAL"
  sed -i "s|${DB_PAT_LOCAL}|${DB_PAT_EC2}|" "$ENV_FILE"
  echo "BACKEND_URL → EC2 복원"
  echo "DATABASE_URL → RDS 직접 연결 복원"
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# .env.local: 프론트 → 로컬 백엔드
sed -i 's|BACKEND_URL=http://3.37.118.197:8000|BACKEND_URL=http://localhost:8000|' "$ENV_LOCAL"
echo "[1/3] 프론트 프록시 → localhost:8000"

# DATABASE_URL은 RDS 직접이므로 변경 불필요 (이미 RDS URL)
echo "[2/3] DATABASE_URL → RDS 직접 연결 (변경 없음)"

# 프론트 먼저 (백그라운드)
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# 백엔드 (포그라운드 — 로그가 터미널에 직접 출력)
export PYTHONUNBUFFERED=1
echo "[3/3] 백엔드 + 프론트 시작..."
cd backend
if [ -f "../.venv/Scripts/python.exe" ]; then
  PYTHONUNBUFFERED=1 ../.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
elif [ -f "../.venv/bin/python" ]; then
  PYTHONUNBUFFERED=1 ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
else
  PYTHONUNBUFFERED=1 python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
fi

echo ""
echo "======================================"
echo "  백엔드:  http://localhost:8000"
echo "  프론트:  http://localhost:5173"
echo "  DB:      RDS 직접 연결"
echo "  Ctrl+C → EC2(SSH) 모드 자동 복원"
echo "======================================"
echo ""

wait
