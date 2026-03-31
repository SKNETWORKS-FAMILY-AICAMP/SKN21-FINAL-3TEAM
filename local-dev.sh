#!/bin/bash
# 로컬 개발용: SSH터널 + 백엔드 + 프론트 동시 실행
# 사용법: bash local-dev.sh
# 종료: Ctrl+C (전부 종료 + EC2 설정 자동 복원)
#
# 프론트: localhost:5173 → 백엔드: localhost:8000 (프록시)
# DB: SSH 터널 (localhost:5432 → EC2 → RDS)
# EC2 복원: bash local-dev.sh --ec2

cd "$(dirname "$0")"

ENV_LOCAL="frontend/.env.local"
ENV_FILE=".env"
SSH_KEY="/c/ssh/dudu_key.pem"
EC2_HOST="ubuntu@3.37.118.197"
RDS_HOST="dudu-db.c3kow4uoyb3s.ap-northeast-2.rds.amazonaws.com"

# sed 패턴용 (! 포함이라 작은따옴표 사용)
DB_PAT_EC2='postgresql+asyncpg://postgre:dudu123!@dudu-db.c3kow4uoyb3s.ap-northeast-2.rds.amazonaws.com:5432/workflow_agent?ssl=require'
DB_PAT_LOCAL='postgresql+asyncpg://postgre:dudu123!@localhost:5432/workflow_agent'

# ── EC2 모드 복원 ──
if [ "$1" = "--ec2" ]; then
  echo "=== EC2 모드로 복원 ==="
  sed -i 's|BACKEND_URL=http://localhost:8000|BACKEND_URL=http://3.37.118.197:8000|' "$ENV_LOCAL"
  sed -i "s|${DB_PAT_LOCAL}|${DB_PAT_EC2}|" "$ENV_FILE"
  sed -i '/^# DATABASE_URL=.*dudu-db/d' "$ENV_FILE"
  echo "BACKEND_URL → EC2 (3.37.118.197:8000)"
  echo "DATABASE_URL → RDS 직접 연결 복원"
  exit 0
fi

echo "=== 로컬 개발 모드 ==="

# ── cleanup: Ctrl+C 시 전부 종료 + EC2 복원 ──
cleanup() {
  echo ""
  echo "=== 종료 중... ==="
  [ -n "$BACKEND_PID" ]  && kill $BACKEND_PID 2>/dev/null
  [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null
  [ -n "$SSH_TUNNEL_PID" ] && kill $SSH_TUNNEL_PID 2>/dev/null && echo "SSH 터널 종료"

  # EC2 설정 복원
  sed -i 's|BACKEND_URL=http://localhost:8000|BACKEND_URL=http://3.37.118.197:8000|' "$ENV_LOCAL"
  sed -i "s|${DB_PAT_LOCAL}|${DB_PAT_EC2}|" "$ENV_FILE"
  echo "BACKEND_URL → EC2 복원"
  echo "DATABASE_URL → RDS 직접 연결 복원"
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 1. 포트 5432 충돌 체크
if netstat -ano 2>/dev/null | grep -q ":5432 .*LISTEN"; then
  echo "[경고] 포트 5432가 이미 사용 중입니다 (PostgreSQL 로컬 등)"
  echo "       SSH 터널을 건너뜁니다. DATABASE_URL이 이미 localhost:5432인지 확인하세요."
else
  echo "[1/5] SSH 터널 시작 (localhost:5432 → RDS)..."
  ssh -i "$SSH_KEY" -L 5432:${RDS_HOST}:5432 -N -f "$EC2_HOST"
  if [ $? -ne 0 ]; then
    echo "[에러] SSH 터널 실패. SSH 키 경로와 EC2 상태를 확인하세요."
    exit 1
  fi
  # PID 잡기: ssh -f 로 백그라운드 된 프로세스
  SSH_TUNNEL_PID=$(netstat -ano 2>/dev/null | grep ":5432 .*LISTEN" | awk '{print $5}' | head -1)
  echo "      SSH 터널 OK (PID: ${SSH_TUNNEL_PID:-?})"
fi

# 2. .env.local: 프론트 프록시를 localhost로 변경
sed -i 's|BACKEND_URL=http://3.37.118.197:8000|BACKEND_URL=http://localhost:8000|' "$ENV_LOCAL"
echo "[2/5] 프론트 프록시 → localhost:8000"

# 3. .env: DATABASE_URL을 로컬 터널용으로 변경
sed -i "s|${DB_PAT_EC2}|${DB_PAT_LOCAL}|" "$ENV_FILE"
sed -i '/^# DATABASE_URL=.*dudu-db/d' "$ENV_FILE"
echo "[3/5] DATABASE_URL → localhost:5432 (SSH 터널)"

# 4. 백엔드 시작 (가상환경 자동 감지)
echo "[4/5] 백엔드 시작 (uvicorn)..."
cd backend
if [ -f "../.venv/Scripts/python.exe" ]; then
  ../.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir . --reload-dir ../ai &
elif [ -f "../.venv/bin/python" ]; then
  ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir . --reload-dir ../ai &
else
  echo "[에러] 가상환경을 찾을 수 없습니다 (.venv)"
  exit 1
fi
BACKEND_PID=$!
cd ..

# 5. 프론트 시작
echo "[5/5] 프론트 시작 (vite)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "======================================"
echo "  백엔드:   http://localhost:8000"
echo "  프론트:   http://localhost:5173"
echo "  DB 터널:  localhost:5432 → RDS"
echo "  Ctrl+C로 전부 종료 + EC2 자동 복원"
echo "======================================"
echo ""

wait
