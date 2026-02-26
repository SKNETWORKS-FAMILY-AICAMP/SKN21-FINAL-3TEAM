
import sys
import os
import json
import logging
import asyncio
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트를 sys.path에 추가 (tests/ -> 프로젝트 루트)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.agents.document_agent import document_agent  # noqa: E402
from ai.agents.state import AgentState  # noqa: E402

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_document_agent():
    print("=== Testing Document Agent (MOCK State) ===\n")

    # 공통 기본 state 필드
    base_state = {
        "confidence": 0.95,
        "chat_history": [],
        "agent_response": {},
        "error": None,
        "template_id": None,
        "source_page": None,
        "template_fields": None,
        "extracted_text": None,
        "document_id": None,
        "document_content": None,
        "google_services_result": None,
    }

    # 1. doc_search 테스트
    print("[Test 1] doc_search ...")
    state1: AgentState = {
        **base_state,
        "intent": "doc_search",
        "user_input": "인사 규정에 대해 알려줘",
        "context": ["인사 규정 제3조: 연차는 15일 부여된다.", "보안 규정: USB 사용 금지"],
        "user_id": 1,
    }

    result1 = await document_agent(state1)
    print(f"Result: {json.dumps(result1['agent_response'], ensure_ascii=False, indent=2)}\n")


    # 2. doc_generate 테스트
    print("[Test 2] doc_generate ...")
    state2: AgentState = {
        **base_state,
        "intent": "doc_generate",
        "user_input": "프로젝트 진행 보고서를 작성해줘. 주요 내용은 3단계 Agent 개발 완료, 테스트 진행 중, 다음 주 통합 예정.",
        "context": [],
        "user_id": 1,
        "confidence": 0.92,
        "template_id": 1,
        "source_page": "document_page",
        "template_fields": ["title", "summary", "content"],
    }

    result2 = await document_agent(state2)
    print(f"Result: {json.dumps(result2['agent_response'], ensure_ascii=False, indent=2)}\n")


    # 3. doc_generate (meeting_minutes) 테스트 — 회의록은 doc_generate의 meeting_minutes 분기
    print("[Test 3] doc_generate (meeting_minutes) ...")
    state3: AgentState = {
        **base_state,
        "intent": "doc_generate",
        "user_input": "2월 12일 주간회의했고 김철수, 이영희 참석했어. DB 마이그레이션 이번주까지 끝내기로 했고, API 문서는 김철수가 쓰기로 함.",
        "context": [],
        "user_id": 1,
        "source_page": "meeting_page",
    }

    result3 = await document_agent(state3)
    print(f"Result: {json.dumps(result3['agent_response'], ensure_ascii=False, indent=2)}\n")


    # 4. doc_summary 테스트
    print("[Test 4] doc_summary ...")
    state4: AgentState = {
        **base_state,
        "intent": "doc_summary",
        "user_input": "이 문서 요약해줘",
        "context": [],
        "user_id": 1,
        "document_content": "이것은 테스트 문서입니다. 주요 내용은 프로젝트 진행 상황에 대한 것으로, 1단계 설계가 완료되었고 2단계 개발이 진행 중입니다. 핵심 이슈는 일정 지연 가능성입니다.",
    }

    result4 = await document_agent(state4)
    print(f"Result: {json.dumps(result4['agent_response'], ensure_ascii=False, indent=2)}\n")


    # 4-1. doc_summary (문서 없음) 테스트
    print("[Test 4-1] doc_summary (no content) ...")
    state4_1: AgentState = {
        **base_state,
        "intent": "doc_summary",
        "user_input": "이 문서 요약해줘",
        "context": [],
        "user_id": 1,
    }

    result4_1 = await document_agent(state4_1)
    print(f"Result: {json.dumps(result4_1['agent_response'], ensure_ascii=False, indent=2)}\n")


    # 4-2. doc_summary (extracted_text fallback) 테스트
    print("[Test 4-2] doc_summary (extracted_text fallback) ...")
    state4_2: AgentState = {
        **base_state,
        "intent": "doc_summary",
        "user_input": "핵심만 정리해줘",
        "context": [],
        "user_id": 1,
        "extracted_text": "업로드된 파일에서 추출된 텍스트입니다. 분기별 매출 보고서로, Q1 매출이 전년 대비 15% 증가했습니다.",
    }

    result4_2 = await document_agent(state4_2)
    print(f"Result: {json.dumps(result4_2['agent_response'], ensure_ascii=False, indent=2)}\n")


    # 5. doc_qa 테스트
    print("[Test 5] doc_qa ...")
    state5: AgentState = {
        **base_state,
        "intent": "doc_qa",
        "user_input": "지난 회의 결정사항이 뭐야?",
        "context": ["회의 결정사항: 1. API 스키마 확정 2. DB 설계 이번 주 완료", "회의 참석자: 김철수, 이영희"],
        "user_id": 1,
    }

    result5 = await document_agent(state5)
    print(f"Result: {json.dumps(result5['agent_response'], ensure_ascii=False, indent=2)}\n")


    # 6. risk_detect 테스트
    print("[Test 6] risk_detect ...")
    state6: AgentState = {
        **base_state,
        "intent": "risk_detect",
        "user_input": "이번 프로젝트에서 개인정보를 수집하고 제3자에게 제공할 예정입니다.",
        "context": ["개인정보보호법 제15조: 개인정보 수집 시 동의 필요", "개인정보보호법 제17조: 제3자 제공 시 별도 동의 필요"],
        "user_id": 1,
        "confidence": 0.88,
    }

    result6 = await document_agent(state6)
    print(f"Result: {json.dumps(result6['agent_response'], ensure_ascii=False, indent=2)}\n")

if __name__ == "__main__":
    # 실행 시 SOLAR_API_KEY 환경변수가 있어야 실제 API 호출됨
    # 없으면 Mock 응답 반환됨
    if not os.getenv("SOLAR_API_KEY"):
        print("WARNING: SOLAR_API_KEY not found in environment. Using MOCK responses.\n")

    asyncio.run(test_document_agent())
