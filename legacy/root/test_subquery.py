import asyncio
import logging
logging.disable(logging.CRITICAL)  # 에러 로그 숨김

from ai.agents.orchestrator import get_graph

async def test(query):
    graph = get_graph()
    result = await graph.ainvoke({
        "user_input": query,
        "stream_mode": False,
        "chat_history": [],
        "sub_queries": None,
    })
    print(f"입력: {query}")
    print(f"compound: {result.get('_is_compound')}")
    sqs = result.get("sub_queries")
    if sqs:
        print(f"sub_queries ({len(sqs)}개):")
        for sq in sqs:
            print(f"  step {sq['step_id']}: [{sq['hint']}] \"{sq['query']}\" depends_on={sq['depends_on']}")
    else:
        print(f"단일 질문 → intent: {result.get('intent')}")
    print()

queries = [
    # ── 복합 질문 (compound=True 기대) ──
    "회의록 찾아서 분석하고 보고서 만들어줘",                    # doc_retrieve → judgment → doc_generate
    "연차 규정 확인하고 다음주 금요일에 휴가 등록해줘",          # judgment → schedule_add
    "이번주 일정 확인하고 회의록 작성해줘",                      # schedule_view → doc_generate
    "지난달 매출 보고서 찾아서 요약하고 이번달 보고서 만들어줘",  # doc_retrieve → doc_generate
    "출장 규정 알려주고 다음주 화요일에 출장 일정 잡아줘",       # judgment → schedule_add
    "프로젝트 기획서 찾아서 분석해줘",                          # doc_retrieve → judgment
    "연차 규정 확인하고 다음주 일정 조회한 다음 휴가 등록해줘",  # judgment → schedule_view → schedule_add (3-step)
    "회의록 찾아서 내용 분석하고 보고서 작성해줘",              # doc_retrieve → judgment → doc_generate (3-step)

    # ── 단일 질문 (compound=False 기대) ──
    "보고서 만들어줘",                                          # doc_generate
    "연차 며칠 남았어?",                                        # judgment
    "다음주 일정 보여줘",                                       # schedule_view
    "안녕하세요",                                               # general
]

async def run_all():
    for q in queries:
        await test(q)
        print("─" * 60)

asyncio.run(run_all())
