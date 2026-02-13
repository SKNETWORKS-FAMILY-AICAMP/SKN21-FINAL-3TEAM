"""
판단 Agent 수동 테스트 스크립트

테스트 항목:
  1. 단일 규정 판단
  2. 다중 규정 교차 판단
  3. confidence 보정
  4. 판단 이력 참조
"""
import asyncio
import json
import sys
import io
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트를 sys.path에 추가 (tests/ -> 프로젝트 루트)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows 콘솔 인코딩 문제 해결
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from ai.agents.judgment_agent import judgment_agent  # noqa: E402
from ai.rag.qdrant_pipeline import get_qdrant_pipeline  # noqa: E402


async def test_judgment_agent():
    print("\n" + "="*60)
    print("  판단 Agent 테스트")
    print("="*60)

    # 1. RAG 파이프라인 초기화 + 테스트 규정 추가
    print("\n[1] RAG 파이프라인 초기화 중...")
    pipeline = get_qdrant_pipeline()

    # 테스트용 규정 문서 추가
    test_docs = [
        "직원은 연간 15일의 유급 연차휴가를 사용할 수 있다. 입사 1년 미만인 경우 매월 1일의 유급휴가가 발생한다.",
        "야근 수당은 통상임금의 1.5배로 지급하며, 휴일근무 시 2배를 지급한다. 야근은 사전 승인이 필요하다.",
        "재택근무는 주 2회까지 허용되며, 사전에 팀장의 승인을 받아야 한다. 재택근무 시 업무 시작과 종료를 보고해야 한다.",
        "정보보안 규정에 따라 업무 자료는 회사 승인 없이 외부로 반출할 수 없다. 위반 시 징계 대상이 된다.",
        "출장비는 교통비, 숙박비, 식비를 실비로 지급하며, 일비는 1일 2만원을 정액 지급한다.",
    ]

    test_metas = [
        {"source": "취업규칙 제15조", "scope": "company"},
        {"source": "취업규칙 제22조", "scope": "company"},
        {"source": "재택근무 규정 제3조", "scope": "company"},
        {"source": "정보보안 규정 제10조", "scope": "company"},
        {"source": "출장비 규정 제5조", "scope": "company"},
    ]

    try:
        pipeline.add_documents(test_docs, test_metas)
        print("✓ 테스트 규정 5개 추가 완료")
    except Exception as e:
        print(f"✗ 규정 추가 실패: {e}")
        return

    # 2. 테스트 케이스
    test_cases = [
        {
            "name": "단일 규정 판단 (연차)",
            "state": {
                "user_input": "입사 6개월 차인데 연차를 사용할 수 있나요?",
                "user_id": 1,
                "chat_history": [],
            },
            "expected": "yes 또는 conditional",
        },
        {
            "name": "다중 규정 교차 판단 (재택근무+정보보안)",
            "state": {
                "user_input": "재택근무 중에 회사 자료를 집에서 출력해도 되나요?",
                "user_id": 1,
                "chat_history": [],
            },
            "expected": "no 또는 conditional (충돌 가능)",
        },
        {
            "name": "규정 없음 판단",
            "state": {
                "user_input": "사내 카페테리아 영업 시간이 언제인가요?",
                "user_id": 1,
                "chat_history": [],
            },
            "expected": "no_regulation",
        },
        {
            "name": "판단 이력 참조",
            "state": {
                "user_input": "그럼 주 3회는 안 되나요?",
                "user_id": 1,
                "chat_history": [
                    {"role": "user", "content": "재택근무는 주 몇 회까지 가능한가요?"},
                    {
                        "role": "assistant",
                        "content": json.dumps({
                            "type": "judgment",
                            "result": "yes",
                            "confidence": 0.95,
                            "reasoning": "재택근무 규정 제3조에 따르면 주 2회까지 허용됩니다.",
                            "regulations": [{"article": "재택근무 규정 제3조", "relevance": "높음", "content": "주 2회까지"}],
                        }, ensure_ascii=False),
                    },
                ],
            },
            "expected": "no (이전 판단 참조)",
        },
    ]

    # 3. 테스트 실행
    for i, tc in enumerate(test_cases, 1):
        print(f"\n{'─'*60}")
        print(f"[테스트 {i}] {tc['name']}")
        print(f"질문: {tc['state']['user_input']}")
        print(f"기대: {tc['expected']}")
        print(f"{'─'*60}")

        try:
            result = await judgment_agent(tc["state"])

            response = result.get("agent_response", {})
            print(f"\n✓ 판단 결과: {response.get('result', 'N/A')}")
            print(f"  Confidence: {response.get('confidence', 0):.3f}")
            print(f"  근거: {response.get('reasoning', 'N/A')[:150]}...")

            # 규정 그룹
            groups = response.get("regulation_groups", [])
            if groups:
                print(f"  규정 그룹: {', '.join(groups)}")

            # 교차 참조
            cross_refs = response.get("cross_references", [])
            if cross_refs:
                print(f"  교차 참조: {len(cross_refs)}건")
                for cr in cross_refs:
                    print(f"    - {cr.get('relationship', '?')}: {cr.get('articles', [])}")

            # RAG 컨텍스트
            context = result.get("context", [])
            print(f"  검색된 규정: {len(context)}건")
            if context:
                print(f"    Top 1: {context[0].get('source', 'N/A')} (score: {context[0].get('score', 0):.3f})")

        except Exception as e:
            print(f"\n✗ 테스트 실패: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("  테스트 완료")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(test_judgment_agent())
