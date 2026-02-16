"""
Intent 분류 및 오케스트레이터 설정 상수

하드코딩된 임계값들을 한 곳에 모아 실험적 튜닝을 용이하게 합니다.
"""

# ── Intent 분류 임계값 ──
INTENT_CONFIDENCE_THRESHOLD = 0.7    # 이하면 clarify (top-3 후보 제시)
INTENT_FALLBACK_THRESHOLD = 0.5      # 이하면 general 강제 (임베딩 fallback)

# ── 복합 질문 감지 ──
COMPLEXITY_GAP_THRESHOLD = 0.3       # top-2 confidence gap (이하면 복합 신호)

# ── 오케스트레이터 ──
MAX_SUB_QUERIES = 3                  # 복합 질문 최대 서브쿼리 수
CONTEXT_HISTORY_TURNS = 5            # 맥락 해석 시 참조할 대화 턴 수
