"""
Intent 분류 및 오케스트레이터 설정 상수

하드코딩된 임계값들을 한 곳에 모아 실험적 튜닝을 용이하게 합니다.
"""

# ── Intent 분류 임계값 ──
# Stage 6 (Label Smoothing 0.1 적용 후 조정)
# - 정답 confidence: 0.85~0.95 분포
# - 오답 confidence: 0.70~0.85 분포
# - 0.85 기준으로 분리 가능 (Stage 6 결과 확인 후 최종 확정)
INTENT_CONFIDENCE_THRESHOLD = 0.85   # 이하면 clarify (top-3 후보 제시)
INTENT_FALLBACK_THRESHOLD = 0.4      # 이하면 general 강제 (임베딩 fallback)

# ── 복합 질문 설정 ──
ENABLE_COMPLEX_QUERY = True          # 복합 질문 감지 활성화
