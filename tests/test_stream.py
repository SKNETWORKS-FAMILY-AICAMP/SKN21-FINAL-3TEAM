"""백엔드 스트리밍 직접 테스트 (로그인 불필요)

테스트 순서:
  1) Solar API 스트리밍이 되는지 확인
  2) orchestrator 파이프라인 확인
"""
import sys
import os
import asyncio
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")


async def test_1_llm_streaming():
    """[테스트 1] Solar API 스트리밍 직접 확인"""
    print("=" * 50)
    print("[테스트 1] Solar API 스트리밍 직접 확인")
    print("=" * 50)

    api_key = os.getenv("SOLAR_API_KEY")
    base_url = "https://api.upstage.ai/v1/solar"
    model = "solar-1-mini-chat"

    print(f"  모델: {model}")
    print(f"  base_url: {base_url}")
    print(f"  API 키: {'있음' if api_key else '없음!'}")

    if not api_key:
        print("  [실패] SOLAR_API_KEY가 없습니다.")
        return False

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    print(f"\n  스트리밍 호출 중...")
    print(f"  ─────────────────────────────────")

    token_count = 0
    stream = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "한국어로 짧게 답변하세요."},
            {"role": "user", "content": "안녕하세요"},
        ],
        temperature=0.7,
        max_tokens=100,
        stream=True,
    )

    async for chunk in stream:
        if chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            token_count += 1
            sys.stdout.write(token)
            sys.stdout.flush()

    print(f"\n  ─────────────────────────────────")
    print(f"  토큰 {token_count}개 수신 완료")

    if token_count > 1:
        print(f"  [성공] Solar API 스트리밍 정상!")
        return True
    else:
        print(f"  [실패] 토큰이 1개 이하 — 스트리밍 안 됨")
        return False


async def test_2_doc_search_stream():
    """[테스트 2] doc_search 스트리밍 (orchestrator + Solar API)"""
    print("\n" + "=" * 50)
    print("[테스트 2] doc_search 스트리밍 테스트")
    print("=" * 50)

    from ai.agents.orchestrator import get_graph
    from openai import AsyncOpenAI

    graph = get_graph()

    initial_state = {
        "user_input": "코드리뷰 속도 개선 회의에서 어떤 내용이 논의되었나요?",
        "user_id": 1,
        "intent": "",
        "confidence": 0.0,
        "context": [],
        "agent_response": {},
        "chat_history": [],
        "error": None,
        "template_id": None,
        "source_page": None,
        "template_fields": None,
        "extracted_text": None,
        "google_services_result": None,
        "stream_mode": True,
    }

    print(f"  질문: {initial_state['user_input']}")
    print(f"  stream_mode: True")
    print(f"  ─────────────────────────────────")

    async for event in graph.astream(initial_state):
        for node_name, node_output in event.items():
            print(f"\n  [{node_name}]")

            if node_name == "classify_intent":
                print(f"    intent: {node_output.get('intent')}")
                print(f"    confidence: {node_output.get('confidence')}")

            elif node_name == "general_response":
                resp = node_output.get("agent_response", {})
                stream_pending = resp.get("stream_pending", False)
                print(f"    stream_pending: {stream_pending}")
                if stream_pending:
                    print(f"    [성공] LLM 건너뜀 → 스트리밍 대기")

            elif node_name == "document_agent":
                resp = node_output.get("agent_response", {})
                stream_pending = resp.get("stream_pending", False)
                print(f"    type: {resp.get('type')}")
                print(f"    stream_pending: {stream_pending}")
                print(f"    sources: {len(resp.get('sources', []))}개")

                if stream_pending:
                    print(f"    [성공] RAG 검색 완료, LLM 건너뜀!")
                    print(f"\n  === Solar API 스트리밍 시작 ===")

                    solar_key = os.getenv("SOLAR_API_KEY")
                    client = AsyncOpenAI(
                        api_key=solar_key,
                        base_url="https://api.upstage.ai/v1/solar",
                    )

                    stream = await client.chat.completions.create(
                        model="solar-1-mini-chat",
                        messages=[
                            {"role": "system", "content": resp["sys_prompt"]},
                            {"role": "user", "content": resp["user_prompt"]},
                        ],
                        temperature=0.7,
                        max_tokens=1024,
                        stream=True,
                    )

                    token_count = 0
                    async for chunk in stream:
                        if chunk.choices[0].delta.content:
                            token = chunk.choices[0].delta.content
                            token_count += 1
                            sys.stdout.write(token)
                            sys.stdout.flush()

                    print(f"\n  === 스트리밍 완료 (토큰 {token_count}개) ===")
                else:
                    msg = resp.get("message", "")
                    print(f"    message: {msg[:100]}..." if len(msg) > 100 else f"    message: {msg}")

            elif node_name == "format_response":
                resp = node_output.get("agent_response", {})
                print(f"    type: {resp.get('type')}")

            else:
                print(f"    output keys: {list(node_output.keys())}")

    print(f"\n  ─────────────────────────────────")
    print(f"  테스트 완료!")


async def main():
    ok = await test_1_llm_streaming()
    if ok:
        await test_2_doc_search_stream()
    else:
        print("\n[스킵] LLM 스트리밍 실패로 테스트 2 건너뜀")


if __name__ == "__main__":
    asyncio.run(main())
