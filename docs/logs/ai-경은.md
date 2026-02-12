# 작업 로그 — 윤경은 (AI 서브)

> 세션 종료 시 Claude가 자동으로 업데이트합니다.

---

## 2026-02-11 (화)

**모델 벤치마크 테스트셋 + 스크립트 구현 (#7):**
- 벤치마크 테스트셋 70개 생성 (judgment 21, qa 16, meeting 16, summary 5, risk 5, korean 7)
- `run_benchmark.py` 전체 구현 (4-bit 추론 + 자동 평가 + 비교 리포트 생성)
- 평가 4축: 한국어, 규정해석, 판단형식, 속도
- RunPod 셋업/실행 스크립트 추가 (`runpod_setup.sh`, `runpod_run_all.sh`)
- 사내규정 PDF + 판단 1,000건 + 규정 Q&A 500건 데이터 추가

**벤치마크 테스트셋 QA (#7):**
- judgment 21개: input에 규정 조항 + 근거 텍스트 추가 (RAG 실서비스와 동일 형태)
- regulation_qa 16개: input에 관련 규정 조항명 추가
- 실서비스에서 RAG가 규정 원문을 붙여주는 것과 동일한 조건으로 평가하도록 수정

**벤치마크 스크립트 리팩토링 (미커밋):**
- `scripts/` 루트의 벤치마크 파일들을 `scripts/benchmark/` 패키지로 재구성
- `benchmark_config.yaml` → `config.yaml`, `run_benchmark.py` → `run.py`, `create_benchmark_testset.py` → `create_testset.py`
- `regulation_texts.py` 분리, `__init__.py` 추가
- `benchmark_testset.jsonl` 업데이트 (70 → 115건으로 확장)

**다음 할 일:**
- 벤치마크 리팩토링 커밋 및 push
- RunPod에서 모델 후보 벤치마크 실행 (Qwen3 / EXAONE / Tri-7B 등)
- 벤치마크 결과 기반 모델 최종 선정
- RAG 파이프라인 구현 시작 (#8)
