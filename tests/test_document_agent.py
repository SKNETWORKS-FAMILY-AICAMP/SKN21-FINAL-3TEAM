
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

    # 1. doc_search 테스트
    print("[Test 1] doc_search ...")
    state1: AgentState = {
        "intent": "doc_search",
        "user_input": "인사 규정에 대해 알려줘",
        "context": ["인사 규정 제3조: 연차는 15일 부여된다.", "보안 규정: USB 사용 금지"],
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

    result1 = await document_agent(state1)
    print(f"Result: {json.dumps(result1['agent_response'], ensure_ascii=False, indent=2)}\n")


    # 2. doc_generate 테스트
    print("[Test 2] doc_generate ...")
    state2: AgentState = {
        "intent": "doc_generate",
        "user_input": "프로젝트 진행 보고서를 작성해줘. 주요 내용은 3단계 Agent 개발 완료, 테스트 진행 중, 다음 주 통합 예정.",
        "context": [],
        "user_id": 1,
        "confidence": 0.92,
        "chat_history": [],
        "agent_response": {},
        "error": None,
        "template_id": 1,
        "source_page": "document_page",
        "template_fields": ["title", "summary", "content"],
        "extracted_text": None,
        "google_services_result": None
    }

    result2 = await document_agent(state2)
    print(f"Result: {json.dumps(result2['agent_response'], ensure_ascii=False, indent=2)}\n")


    # 3. meeting_generate 테스트
    print("[Test 3] meeting_generate ...")
    state3: AgentState = {
        "intent": "meeting_generate",
        "user_input": "2월 12일 주간회의했고 김철수, 이영희 참석했어. DB 마이그레이션 이번주까지 끝내기로 했고, API 문서는 김철수가 쓰기로 함.",
        "context": [],
        "user_id": 1,
        "confidence": 0.95,
        "chat_history": [],
        "agent_response": {},
        "error": None,
        "template_id": None,
        "source_page": "meeting_page",
        "template_fields": None,
        "extracted_text": None,
        "google_services_result": None
    }

    result3 = await document_agent(state3)
    print(f"Result: {json.dumps(result3['agent_response'], ensure_ascii=False, indent=2)}\n")


    # 4. risk_detect 테스트
    print("[Test 4] risk_detect ...")
    state4: AgentState = {
        "intent": "risk_detect",
        "user_input": "이번 프로젝트에서 개인정보를 수집하고 제3자에게 제공할 예정입니다.",
        "context": ["개인정보보호법 제15조: 개인정보 수집 시 동의 필요", "개인정보보호법 제17조: 제3자 제공 시 별도 동의 필요"],
        "user_id": 1,
        "confidence": 0.88,
        "chat_history": [],
        "agent_response": {},
        "error": None,
        "template_id": None,
        "source_page": None,
        "template_fields": None,
        "extracted_text": None,
        "google_services_result": None
    }

    result4 = await document_agent(state4)
    print(f"Result: {json.dumps(result4['agent_response'], ensure_ascii=False, indent=2)}\n")

if __name__ == "__main__":
    # 실행 시 SOLAR_API_KEY 환경변수가 있어야 실제 API 호출됨
    # 없으면 Mock 응답 반환됨
    if not os.getenv("SOLAR_API_KEY"):
        print("WARNING: SOLAR_API_KEY not found in environment. Using MOCK responses.\n")

    asyncio.run(test_document_agent())
