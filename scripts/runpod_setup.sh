#!/bin/bash
# =============================================================
# RunPod 벤치마크 환경 셋업 스크립트
# Pod 터미널에서 실행: bash scripts/runpod_setup.sh
# =============================================================

set -e
echo "============================================"
echo "  듀듀 벤치마크 환경 셋업 시작"
echo "============================================"

# 1. 기본 패키지 업데이트
echo ""
echo "[1/5] 시스템 패키지 업데이트..."
apt-get update -qq && apt-get install -y -qq git > /dev/null 2>&1
echo "  완료"

# 2. 프로젝트 클론 (또는 업로드된 경우 스킵)
echo ""
echo "[2/5] 프로젝트 확인..."
PROJECT_DIR="/workspace/SKN21-FINAL-3TEAM"

if [ -d "$PROJECT_DIR" ]; then
    echo "  프로젝트 폴더 이미 존재: $PROJECT_DIR"
    cd "$PROJECT_DIR"
    git pull origin develop 2>/dev/null || echo "  (git pull 스킵)"
else
    echo "  프로젝트 클론 중..."
    echo "  ※ 아래 URL을 실제 repo URL로 수정하세요"
    git clone https://github.com/YOUR_ORG/SKN21-FINAL-3TEAM.git "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# 3. Python 패키지 설치
echo ""
echo "[3/5] Python 패키지 설치..."
pip install --quiet --upgrade pip

# 핵심 패키지
pip install --quiet \
    torch \
    transformers==4.44.0 \
    accelerate==0.33.0 \
    bitsandbytes==0.43.3 \
    peft==0.12.0 \
    datasets==3.0.0 \
    rouge-score==0.1.2 \
    scikit-learn==1.5.2 \
    pyyaml==6.0.2 \
    tqdm==4.66.5 \
    pandas==2.2.2 \
    openpyxl

echo "  완료"

# 4. GPU 확인
echo ""
echo "[4/5] GPU 확인..."
python3 -c "
import torch
print(f'  PyTorch: {torch.__version__}')
print(f'  CUDA: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'  GPU: {torch.cuda.get_device_name(0)}')
    mem = torch.cuda.get_device_properties(0).total_mem / 1024**3
    print(f'  VRAM: {mem:.1f} GB')
"

# 5. 테스트셋 확인
echo ""
echo "[5/5] 테스트셋 확인..."
if [ -f "$PROJECT_DIR/data/evaluation/benchmark_testset.jsonl" ]; then
    COUNT=$(wc -l < "$PROJECT_DIR/data/evaluation/benchmark_testset.jsonl")
    echo "  benchmark_testset.jsonl: ${COUNT}개 항목"
else
    echo "  테스트셋 생성 중..."
    python3 scripts/create_benchmark_testset.py
fi

echo ""
echo "============================================"
echo "  셋업 완료!"
echo "============================================"
echo ""
echo "벤치마크 실행 명령어:"
echo ""
echo "  # 모델별 실행 (하나씩)"
echo "  python scripts/run_benchmark.py --model qwen3"
echo "  python scripts/run_benchmark.py --model kanana"
echo "  python scripts/run_benchmark.py --model exaone"
echo "  python scripts/run_benchmark.py --model tri7b"
echo ""
echo "  # 전체 한번에 실행"
echo "  bash scripts/runpod_run_all.sh"
echo ""
echo "  # 비교 리포트"
echo "  python scripts/run_benchmark.py --report"
echo ""
