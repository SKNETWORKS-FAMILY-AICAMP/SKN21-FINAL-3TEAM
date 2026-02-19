"""
RAG 기반 문서 검색 테스트
"""
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트를 sys.path에 추가 (tests/ -> 프로젝트 루트)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from ai.agents.document_agent import document_agent  # noqa: E402
from ai.agents.state import AgentState  # noqa: E402

async def test_rag_doc_search():
    """RAG 기반 문서 검색 테스트"""
    print("="*60)
    print("RAG 기반 문서 검색 테스트")
    print("="*60)

    # 테스트 질의
    test_queries = [
        "연차 휴가는 몇 일 받을 수 있나요?",
        "재택근무 규정에 대해 알려주세요",
        "출장비는 어떻게 지급되나요?",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n[Test {i}] 질의: '{query}'")
        print("-"*60)

        # State 생성
        state: AgentState = {
            "intent": "doc_search",
            "user_input": query,
            "context": [],  # 비어있음 → RAG 검색 수행
            "user_id": 1,
            "confidence": 0.95,
            "chat_history": [],
            "agent_response": {},
            "error": None,
            "template_id": None,
            "source_page": None,
            "template_fields": None,
            "extracted_text": None,
            "google_services_result": None
        }

        # Document Agent 실행
        result = await document_agent(state)
        response = result["agent_response"]

        # 결과 출력
        print("\n[답변]")
        print(response.get("answer", ""))

        print(f"\n[출처] ({len(response.get('sources', []))}개 문서)")
        for j, source in enumerate(response.get("sources", []), 1):
            print(f"  {j}. [{source['title']}] (유사도: {source['score']:.4f})")
            print(f"     출처: {source['source']}")
            print(f"     내용: {source['content']}")
            print()

    print("="*60)
    print("테스트 완료!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_rag_doc_search())
