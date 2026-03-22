"""공유 유틸리티 — LLM 호출, RAG, 소스, 텍스트 유틸"""
import contextvars
import json
import os
import time
from pathlib import Path

GENERATED_DOCS_DIR = Path(__file__).resolve().parents[3] / "backend" / "generated_docs"

# ── 모델명 getter/setter (요청별 격리) ──
_last_model_name: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_last_model_name", default="unknown",
)


def get_last_model_name() -> str:
    return _last_model_name.get()


def set_last_model_name(name: str) -> None:
    _last_model_name.set(name)


# ── 텍스트 유틸 ──

def _to_readable_str(val) -> str:
    """LLM이 반환한 값을 사람이 읽을 수 있는 문자열로 변환.

    - str  → 그대로 반환
    - dict → "- key: value" 형태로 줄 구성
    - list → 각 항목을 "-" 로 시작하는 줄로 구성
             항목이 dict이면 values만 추출하여 " / " 로 연결
    """
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return "\n".join(f"- {k}: {v}" for k, v in val.items() if v)
    if isinstance(val, list):
        lines = []
        for item in val:
            if isinstance(item, dict):
                # dict 값들만 추출 (빈 값 제외) → "값1 / 값2" 형태
                parts = [str(v) for v in item.values() if v]
                lines.append("- " + " / ".join(parts) if parts else "")
            else:
                lines.append(f"- {item}")
        return "\n".join(l for l in lines if l)
    return str(val) if val else ""


def _format_chat_context(chat_history: list, max_turns: int = 3) -> str:
    """최근 N턴 대화를 프롬프트용 텍스트로 변환"""
    if not chat_history:
        return ""
    recent = chat_history[-max_turns * 2:]
    lines = []
    for msg in recent:
        role = "사용자" if msg["role"] == "user" else "어시스턴트"
        content = msg.get("content", "")[:200]
        if content:
            lines.append(f"{role}: {content}")
    if not lines:
        return ""
    return "[이전 대화]\n" + "\n".join(lines)


def truncate_by_paragraph(text: str, max_chars: int = 8000) -> str:
    """문단 기준으로 텍스트를 자른다. 문장 중간 잘림 방지."""
    if len(text) <= max_chars:
        return text
    paragraphs = text.split('\n\n')
    truncated = ""
    for p in paragraphs:
        if len(truncated) + len(p) + 2 > max_chars:
            break
        truncated += p + "\n\n"
    truncated = truncated.rstrip()
    if not truncated:
        truncated = text[:max_chars]
    return truncated


# ── RAG ──

async def _retrieve_context(query: str, user_id: int = None, user_team: str = None, top_k: int = 7, use_reranker: bool = False, score_threshold: float = None) -> tuple:
    """공통 RAG 검색 — search/QA/summary에서 재사용

    Args:
        use_reranker: Cross-Encoder 재정렬 사용 여부 (정밀도 ↑, 지연 +2~5초)
        score_threshold: 최소 점수 기준 (미달 문서 제거)

    Returns:
        (search_results, context, sources, rag_status)
        rag_status: "success" | "timeout" | "error"
    """
    _t = time.time()
    print(f"[DocumentAgent] _retrieve_context | query='{query[:50]}', top_k={top_k}, reranker={use_reranker}, threshold={score_threshold}")
    search_results = []
    context = []
    rag_status = "success"
    try:
        import asyncio
        from ai.rag.qdrant_pipeline import get_qdrant_pipeline

        pipeline = get_qdrant_pipeline()
        search_results = await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(
                None,
                lambda: pipeline.retrieve(
                    query, user_id=user_id, user_team=user_team,
                    top_k=top_k, filter={"source": "documents"},
                    use_reranker=use_reranker,
                    score_threshold=score_threshold,
                ),
            ),
            timeout=30,
        )
        context = [f"[문서 제목: {doc.get('title', '')}]\n{doc['content']}" for doc in search_results]
        print(f"[DocumentAgent] _retrieve_context 완료 ({time.time()-_t:.2f}s): {len(context)}개 문서")
    except asyncio.TimeoutError:
        print(f"[DocumentAgent] !!! _retrieve_context 타임아웃 (30초 초과)")
        rag_status = "timeout"
    except Exception as e:
        print(f"[DocumentAgent] !!! _retrieve_context 실패: {e}")
        import traceback
        traceback.print_exc()
        rag_status = "error"

    sources = _build_sources(search_results)
    return search_results, context, sources, rag_status


def _build_sources(search_results: list) -> list:
    """검색 결과에서 출처 정보 구성 (중복 제거)"""
    sources = []
    seen_sources = set()
    if search_results:
        for doc in search_results:
            content_key = doc.get("content", "")[:100]
            if content_key in seen_sources:
                continue
            seen_sources.add(content_key)

            sources.append({
                "title": doc.get("title") or doc.get("chapter") or doc.get("source", "제목 없음"),
                "source": doc.get("source", ""),
                "score": doc.get("score", 0.0),
                "content": doc.get("content", ""),
                "document_id": doc.get("document_id"),
            })
    return sources


# ── LLM 호출 ──

async def _call_llm(sys_prompt: str, user_prompt: str, json_mode: bool = False, task: str = None, temperature: float = None) -> str:
    """
    LLM 호출 — 모드에 따라 LLM API 또는 sLLM(vLLM + LoRA) 사용

    Args:
        task: 파인튜닝 태스크명 ("generate", "qa", "summary", "extract").
              DOC_AGENT_MODE=sllm일 때 해당 LoRA 어댑터로 라우팅.
              "extract"는 커스텀 템플릿 2단계 추출용 — LoRA 없이 base/API 사용.
              None이면 항상 LLM API 사용 (template_type 감지 등).
        temperature: LLM 온도. None이면 task에 따라 자동 결정
                     (generate=0.15, extract=0.1, 검색/QA=0.1)
    """
    if temperature is None:
        temperature = 0.15 if task == "generate" else 0.1
    _t_llm = time.time()
    mode = os.getenv("DOC_AGENT_MODE", "api")
    sllm_tasks = os.getenv("DOC_SLLM_TASKS", "generate").split(",")
    print(f"[DocumentAgent] _call_llm 호출 | mode={mode}, task={task}, temperature={temperature}, json_mode={json_mode}")
    try:
        # task="extract": 커스텀 템플릿 2단계 — LoRA 없이 base 모델 또는 API
        if task == "extract" and mode == "sllm":
            try:
                from ai.serving.vllm_client import VLLMProvider
                llm = VLLMProvider()  # LoRA 안 태움
                set_last_model_name(os.getenv("VLLM_MODEL", "Kanana-1.5-8B") + " (base, extract)")
                print(f"[DocumentAgent] _call_llm | sLLM base (extract, no LoRA)")
                response = await llm.generate(
                    prompt=user_prompt,
                    system_prompt=sys_prompt,
                    temperature=temperature,
                    json_mode=json_mode,
                )
                result = response.content
                print(f"[DocumentAgent] _call_llm | extract 응답 ({time.time()-_t_llm:.2f}s) 길이: {len(result)}자")
                return result
            except Exception as e:
                print(f"[DocumentAgent] _call_llm | extract sLLM 실패, API fallback: {e}")
                set_last_model_name(os.getenv("OPENAI_MODEL", "gpt-4o-mini") + " (fallback)")
                from ai.llm import get_llm
                llm = get_llm()

        elif mode == "sllm" and task:
            # sLLM 모드: vLLM — LoRA 적용 태스크만 어댑터 사용, 나머지는 base
            try:
                from ai.serving.vllm_client import VLLMProvider
                lora_tasks = set(os.getenv("DOC_LORA_TASKS", "generate").split(","))
                use_lora = os.getenv("VLLM_USE_LORA", "false").lower() == "true"
                # task별 LoRA 어댑터 이름 매핑
                LORA_ADAPTER_NAMES = {
                    "generate": "v3_generate",
                    "summary": "v3_summary",
                }
                if use_lora and task in lora_tasks:
                    adapter_name = LORA_ADAPTER_NAMES.get(task, f"v3_{task}")
                    llm = VLLMProvider().with_lora(adapter_name)
                    set_last_model_name(os.getenv("VLLM_MODEL", "Kanana-1.5-8B") + f" (LoRA {adapter_name})")
                    print(f"[DocumentAgent] _call_llm | sLLM: {adapter_name} LoRA 어댑터")
                else:
                    llm = VLLMProvider()
                    set_last_model_name(os.getenv("VLLM_MODEL", "Kanana-1.5-8B") + " (base)")
                    print(f"[DocumentAgent] _call_llm | sLLM: base model (task={task})")
                response = await llm.generate(
                    prompt=user_prompt,
                    system_prompt=sys_prompt,
                    temperature=temperature,
                    json_mode=json_mode,
                )
                result = response.content
                print(f"[DocumentAgent] _call_llm | sLLM 응답 ({time.time()-_t_llm:.2f}s) 길이: {len(result)}자")
                return result
            except Exception as e:
                print(f"[DocumentAgent] _call_llm | sLLM 실패, API fallback: {e}")
                set_last_model_name(os.getenv("OPENAI_MODEL", "gpt-4o-mini") + " (fallback)")
                from ai.llm import get_llm
                llm = get_llm()
        else:
            # API 모드: 기존 LLM Factory (GPT/Claude)
            from ai.llm import get_llm
            llm = get_llm()
            set_last_model_name(os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
            print(f"[DocumentAgent] _call_llm | API: {llm.__class__.__name__}")

        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=sys_prompt,
            temperature=temperature,
            json_mode=json_mode,
        )

        result = response.content
        print(f"[DocumentAgent] _call_llm | 응답 ({time.time()-_t_llm:.2f}s) 길이: {len(result)}자")
        return result

    except Exception as e:
        print(f"[DocumentAgent] _call_llm | !!! 에러: {e}")
        import traceback
        traceback.print_exc()
        return _get_mock_response(user_prompt, json_mode)

def _get_mock_response(user_prompt: str, json_mode: bool) -> str:
    """API 키 없을 때 나가는 Mock 응답"""
    prompt_lower = user_prompt.lower()
    if json_mode:
        # doc_qa mock — "Question:" 패턴 우선 검사
        if "question" in prompt_lower or "answer" in prompt_lower:
            return json.dumps({
                "answer": "문서에 따르면 해당 내용은 다음과 같습니다. (Mock 응답)",
                "citations": [
                    {"source": "내부 규정 문서", "content": "관련 조항 내용 발췌 (Mock)", "relevance": "높음"}
                ],
                "confidence": 0.85,
            }, ensure_ascii=False)
        # meeting mock
        if "회의" in user_prompt or "summary" in prompt_lower:
             return json.dumps({
                "title": "주간 개발 회의 (Mock)",
                "date": "2026-02-12",
                "attendees": ["김철수", "이영희", "박민수"],
                "summary": "금주 개발 진행 상황 공유 및 이슈 논의. API 스키마 확정됨.",
                "decisions": ["API 스키마 확정", "DB 설계를 이번 주 내로 완료하기로 함"],
                "action_items": [
                    {"content": "API 명세서 작성", "assignee": "김철수", "due_date": "2026-02-15"},
                    {"content": "DB 마이그레이션", "assignee": "이영희", "due_date": "2026-02-16"}
                ],
                "risks": [
                    {"description": "일정 지연 가능성 존재", "regulation": "프로젝트 관리 규정", "level": "중간"}
                ]
            }, ensure_ascii=False)
        # 기본 문서 mock
        return json.dumps({
            "title": "자동 생성 문서 (Mock)",
            "content": "LLM에 의해 생성된 문서 내용입니다.\\n사용자 요청을 반영하여 작성되었습니다."
        }, ensure_ascii=False)

    # 요약 mock
    if "요약" in user_prompt or "문서 내용" in user_prompt:
        return "## 핵심 요약\n\n이 문서는 주요 업무 프로세스를 설명합니다. (Mock 요약 응답)\n\n### 주요 포인트\n- 포인트 1\n- 포인트 2\n- 포인트 3"

    return "LLM이 생성한 답변입니다. (문서 검색 결과 등) - Mock Response"
