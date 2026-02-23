"""
Intent 분류 및 오케스트레이터 설정 상수

하드코딩된 임계값들을 한 곳에 모아 실험적 튜닝을 용이하게 합니다.
"""

# ── Intent 분류 임계값 ──
INTENT_CONFIDENCE_THRESHOLD = 0.7    # 이하면 clarify (top-3 후보 제시)
INTENT_FALLBACK_THRESHOLD = 0.5      # 이하면 general 강제 (임베딩 fallback)
