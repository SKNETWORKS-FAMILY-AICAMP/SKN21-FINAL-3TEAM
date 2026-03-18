"""
판단 Agent (3단계 고도화 #12 + 멘토 피드백 반영)

기능:
  - RAG 파이프라인으로 관련 규정 검색
  - 다중 규정 교차 판단 (규정 간 충돌/보완 분석)
  - confidence score 산출 (RAG 점수 + 규정 커버리지 기반 보정)
  - 3중 보조 장치:
    1) 규정 키워드 매칭 점수 — LLM 인용 조항 vs RAG 검색 결과 cross-check (환각 탐지)
    2) 규정 조항 존재 여부 검증 — Qdrant에서 실제 조항 존재 validate
    3) 판단 결과 카테고리 제한 — yes/no/conditional/no_regulation 외 자동 reject
  - 이전 동일 쿼리 캐싱 — 같은 질문에 다른 답이면 flag (일관성 모니터링)
  - 조건부 판단 (조건 분기별 상세 판단)
  - 판단 이력 참조 (대화 이력에서 이전 판단 추출 → 일관성 유지)
  - SSE 스트리밍 대응

입출력:
  Input: AgentState (user_input, user_id, chat_history)
  Output: AgentState (context, agent_response 채움)
"""
import hashlib
import json
import logging
import os
import re
import time
from collections import defaultdict
from typing import AsyncGenerator

from ai.agents.state import AgentState
from ai.llm import get_llm
from ai.llm.prompts import JUDGMENT_SYSTEM_PROMPT
from ai.rag.qdrant_pipeline import get_qdrant_pipeline

logger = logging.getLogger(__name__)

# ── sLLM 모드 지원 ──

_judgment_model_name = "unknown"


async def _call_judgment_llm(sys_prompt: str, user_prompt: str) -> str:
    """판단 Agent LLM 호출 — sLLM 모드면 LoRA 사용, 아니면 API.

    환경변수:
        JUDGMENT_AGENT_MODE: "api" (기본) 또는 "sllm"
        VLLM_USE_LORA: "true"면 v1_judgment LoRA 어댑터 사용
    """
    global _judgment_model_name
    mode = os.getenv("JUDGMENT_AGENT_MODE", "api")
    _t = time.time()

    try:
        if mode == "sllm":
            from ai.serving.vllm_client import VLLMProvider
            use_lora = os.getenv("VLLM_USE_LORA", "false").lower() == "true"
            if use_lora:
                llm = VLLMProvider().with_lora("v1_judgment")
                _judgment_model_name = os.getenv("VLLM_MODEL", "Kanana-1.5-8B") + " (LoRA v1_judgment)"
                print(f"[JudgmentAgent] sLLM: v1_judgment LoRA")
            else:
                llm = VLLMProvider()
                _judgment_model_name = os.getenv("VLLM_MODEL", "Kanana-1.5-8B") + " (base)"
                print(f"[JudgmentAgent] sLLM: base model")

            try:
                response = await llm.generate(
                    prompt=user_prompt,
                    system_prompt=sys_prompt,
                    temperature=0.1,
                    json_mode=True,
                )
                print(f"[JudgmentAgent] sLLM 응답 ({time.time()-_t:.2f}s) 길이: {len(response.content)}자")
                return response.content
            except Exception as e:
                print(f"[JudgmentAgent] sLLM 실패, API fallback: {e}")
                _judgment_model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini") + " (fallback)"
                llm = get_llm()
        else:
            llm = get_llm()
            _judgment_model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            print(f"[JudgmentAgent] API: {llm.__class__.__name__}")

        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=sys_prompt,
            temperature=0.1,
        )
        print(f"[JudgmentAgent] 응답 ({time.time()-_t:.2f}s) 길이: {len(response.content)}자")
        return response.content

    except Exception as e:
        print(f"[JudgmentAgent] LLM 호출 실패: {e}")
        import traceback
        traceback.print_exc()
        return '{"result": "no_regulation", "confidence": 0.0, "reasoning": "LLM 호출 실패"}'

# ── 허용 판단 결과 카테고리 ──
VALID_JUDGMENT_RESULTS = {"yes", "no", "conditional", "no_regulation"}

# ── 동일 쿼리 캐싱 (일관성 모니터링) ──
# {query_hash: {"result": ..., "confidence": ..., "count": N, "inconsistent": bool}}
_judgment_cache: dict[str, dict] = {}
_CACHE_MAX_SIZE = 500  # 메모리 누수 방지: 최대 500개 쿼리 캐시


# ── 다중 규정 그룹핑 ──


def _group_regulations(context: list[dict]) -> dict[str, list[dict]]:
    """RAG 검색 결과를 규정 출처별로 그룹핑한다.

    Returns:
        {"제3장 근로시간 및 휴가": [doc1, doc2], "제5장 정보보호 관리체계": [doc3]} 형태
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for doc in context:
        # 1순위: chapter 메타데이터 (조항 기반 청킹에서 제공)
        chapter = doc.get("chapter", "")
        if chapter:
            groups[chapter].append(doc)
            continue

        # 2순위: source에서 규정명 추출 (예: "인사규정.pdf" → "인사규정")
        source = doc.get("source", "출처 불명")
        reg_name = re.sub(r"\.(pdf|md|txt)$", "", source, flags=re.IGNORECASE).strip()
        # "제N조" 형태면 article 메타로 대체 시도
        if re.match(r"^제\s*\d+\s*조", reg_name):
            reg_name = doc.get("title", "") or reg_name
        if not reg_name:
            reg_name = source
        groups[reg_name].append(doc)
    return dict(groups)


def _build_context_prompt(context: list[dict], max_docs: int = 3) -> str:
    """RAG 검색 결과를 학습 데이터(eval.jsonl)와 동일한 형식으로 변환.

    학습 데이터 형식:
        ### 제9조 (원격근무)
        {규정 내용}

        ### 개인정보처리규정 — 제5조 (개인정보 수집 원칙)
        {규정 내용}

    Args:
        context: RAG 검색 결과 (reranker 점수 순으로 정렬됨)
        max_docs: 프롬프트에 포함할 최대 문서 수 (상위 N개만 사용, 노이즈 감소)
    """
    if not context:
        return "(관련 규정을 찾지 못했습니다)"

    parts = []
    for doc in context[:max_docs]:
        title = doc.get("title", "")
        article = doc.get("article", "")
        content = doc.get("content", "")

        # 학습 데이터와 동일한 헤더 형식 구성
        if article and title and title != article:
            # "### 개인정보처리규정 — 제5조 (개인정보 수집 원칙)"
            header = f"### {title} — {article}"
        elif article:
            # "### 제9조 (원격근무)"
            header = f"### {article}"
        elif title:
            # "### 출장규정"
            header = f"### {title}"
        else:
            header = "### 규정"

        parts.append(f"{header}\n{content}")

    return "\n\n".join(parts)


# ── 판단 이력 추출 ──


def _extract_judgment_history(chat_history: list[dict]) -> list[dict]:
    """대화 이력에서 이전 판단 결과를 추출한다.

    assistant 메시지 중 judgment 타입 JSON을 포함한 응답을 찾아 반환.
    """
    history = []
    if not chat_history:
        return history

    for msg in chat_history:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        # JSON 블록 추출 시도
        match = re.search(r"\{.*?\"type\"\s*:\s*\"judgment\".*?\}", content, re.DOTALL)
        if not match:
            continue
        try:
            parsed = json.loads(match.group(0))
            if parsed.get("type") == "judgment":
                history.append(parsed)
        except json.JSONDecodeError:
            continue

    return history


def _build_user_prompt(
    user_input: str,
    context_text: str,
    chat_history: list[dict] | None = None,
    judgment_history: list[dict] | None = None,
) -> str:
    """사용자 질문 + 규정 context + 판단 이력을 합쳐 최종 프롬프트 구성"""
    prompt_parts = []

    # 1. 이전 대화 컨텍스트
    if chat_history:
        recent = chat_history[-6:]  # 최근 3턴 (user+assistant × 3)
        history_text = "\n".join(
            f"{'사용자' if m['role'] == 'user' else '어시스턴트'}: {m['content']}"
            for m in recent
        )
        prompt_parts.append(f"## 이전 대화\n{history_text}\n")

    # 2. 판단 이력 (일관성 유지용)
    if judgment_history:
        history_parts = []
        for i, jh in enumerate(judgment_history[-3:], 1):  # 최근 3건
            history_parts.append(
                f"[이전 판단 {i}] 결과: {jh.get('result', '?')}, "
                f"신뢰도: {jh.get('confidence', 0):.2f}, "
                f"근거: {jh.get('reasoning', '없음')[:100]}"
            )
        prompt_parts.append(
            "## 이전 판단 이력 (일관성 유지 참고)\n"
            + "\n".join(history_parts) + "\n"
        )

    # 3. 규정 문서
    prompt_parts.append(f"## 관련 규정 문서\n{context_text}")

    # 4. 사용자 질문
    prompt_parts.append(f"\n## 사용자 질문\n{user_input}")

    return "\n".join(prompt_parts)


# ── 응답 파싱 + confidence 보정 ──


def _parse_llm_response(raw: str) -> dict:
    """LLM 응답에서 JSON을 파싱한다. 실패하면 fallback 응답 반환."""
    text = raw.strip()

    # 1차: ```json ... ``` 코드블록에서 추출 (앞뒤 텍스트 무시)
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    # 2차: 코드블록이 없으면 첫 번째 { ... } 블록 추출
    if not text.startswith("{"):
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # JSON 복구 시도: 잘린 JSON 닫기, 제어문자 제거 등
        try:
            # 제어문자 제거
            cleaned = re.sub(r'[\x00-\x1f\x7f]', '', text)
            # 트레일링 콤마 제거
            cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
            # 닫히지 않은 JSON 복구 시도
            open_braces = cleaned.count('{') - cleaned.count('}')
            open_brackets = cleaned.count('[') - cleaned.count(']')
            cleaned += ']' * max(0, open_brackets) + '}' * max(0, open_braces)
            result = json.loads(cleaned)
            logger.info("LLM 응답 JSON 복구 성공 (제어문자/잘림 보정)")
            return result
        except json.JSONDecodeError:
            pass

        logger.warning("LLM 응답 JSON 파싱 실패, 원문을 reasoning에 저장")
        logger.warning(f"[파싱실패 원문] {raw[:500]}")
        return {
            "result": "no_regulation",
            "confidence": 0.0,
            "reasoning": raw,
            "regulations": [],
            "cross_references": [],
            "conditions": None,
            "alternatives": [],
        }


# ── 규정 조항 참조 패턴 (다양한 번호 체계 지원) ──
_ARTICLE_PATTERNS = [
    r"제\s*\d+\s*조(?:\s*제\s*\d+\s*항)?",  # 제8조, 제8조 제2항
    r"제\s*\d+\s*[장편절관]",                  # 제3장, 제2편, 제1절
    r"별표\s*\d+",                             # 별표 1
    r"부칙\s*\d+",                             # 부칙 2
    r"\d+\.\d+(?:\.\d+)?\s*조",               # 3.2조, 3.2.1조
]
_CITED_ARTICLE_RE = re.compile("|".join(f"({p})" for p in _ARTICLE_PATTERNS))


def _extract_cited_articles(parsed: dict) -> list[str]:
    """LLM 응답에서 인용된 규정 조항명을 추출한다.

    regulations 필드의 article과 reasoning 텍스트에서 다양한 조항 패턴을 수집.
    지원: 제N조, 제N조 제N항, 제N장, 별표 N, 부칙 N, 3.2조 등
    """
    articles = set()

    def _find_articles(text: str):
        for m in _CITED_ARTICLE_RE.finditer(text):
            articles.add(m.group().replace(" ", ""))

    # 1. regulations 필드에서 추출
    for reg in parsed.get("regulations", []):
        article = reg.get("article", "")
        if article:
            articles.add(article)
            _find_articles(article)

    # 2. reasoning 텍스트에서 패턴 추출
    reasoning = parsed.get("reasoning", "")
    _find_articles(reasoning)

    return list(articles)


def _check_keyword_match(parsed: dict, context: list[dict]) -> float:
    """보조장치 1: 규정 키워드 매칭 점수 — LLM 인용 조항이 RAG 결과에 있는지 cross-check.

    환각 탐지: LLM이 인용한 조항이 RAG 검색 결과에 실제로 존재하는지 확인한다.

    Returns:
        0.0 ~ 1.0 매칭 비율. 인용 조항이 없으면 0.5 (중립).
    """
    cited = _extract_cited_articles(parsed)
    if not cited:
        return 0.5  # 인용 조항이 없으면 중립

    # RAG 검색 결과의 텍스트를 하나로 합침
    rag_text = " ".join(
        f"{d.get('content', '')} {d.get('source', '')} {d.get('title', '')}"
        for d in context
    )

    matched = 0
    for article in cited:
        # "제8조" → RAG 텍스트에 "제8조"가 포함되는지
        normalized = article.replace(" ", "")
        if normalized in rag_text.replace(" ", ""):
            matched += 1

    match_ratio = matched / len(cited)
    logger.info(
        f"[환각탐지] 인용 조항 {len(cited)}개 중 {matched}개 RAG 매칭 "
        f"(비율: {match_ratio:.2f}) | 인용: {cited}"
    )
    return match_ratio


def _validate_article_exists(parsed: dict, context: list[dict]) -> list[dict]:
    """보조장치 2: 규정 조항 존재 여부 검증.

    LLM이 "제8조"를 인용했으면, RAG 검색 결과에 해당 조항이 실제 있는지 validate.
    없는 조항은 hallucination_flags에 기록한다.

    Returns:
        list of {"article": str, "exists": bool} — 검증 결과
    """
    cited = _extract_cited_articles(parsed)
    if not cited:
        return []

    # RAG context에서 조항 패턴 수집 (확장된 패턴 사용)
    rag_articles = set()
    rag_full_text = ""
    for doc in context:
        content = doc.get("content", "")
        source = doc.get("source", "")
        title = doc.get("title", "")
        combined = f"{content} {source} {title}"
        rag_full_text += " " + combined
        for m in _CITED_ARTICLE_RE.finditer(combined):
            rag_articles.add(m.group().replace(" ", ""))

    results = []
    for article in cited:
        normalized = article.replace(" ", "")
        # 정규화된 조항이 RAG 조항 집합에 있는지 확인
        if normalized in rag_articles:
            results.append({"article": normalized, "exists": True})
        else:
            # fallback: RAG 전체 텍스트에서 문자열 검색
            exists = normalized in rag_full_text.replace(" ", "")
            results.append({"article": normalized, "exists": exists})

    hallucinated = [r for r in results if not r["exists"]]
    if hallucinated:
        logger.warning(
            f"[조항검증] 환각 의심 조항 {len(hallucinated)}건: "
            f"{[r['article'] for r in hallucinated]}"
        )

    return results


def _validate_result_category(parsed: dict) -> dict:
    """보조장치 3: 판단 결과 카테고리 제한.

    yes/no/conditional/no_regulation 이외 값이 나오면 자동 reject하고
    no_regulation으로 대체, confidence를 0.3으로 하향한다.

    Returns:
        보정된 parsed dict (원본 수정)
    """
    result = parsed.get("result", "")

    if result not in VALID_JUDGMENT_RESULTS:
        logger.warning(
            f"[카테고리제한] 유효하지 않은 result '{result}' → 'no_regulation'로 대체"
        )
        parsed["_original_result"] = result  # 원본 보존 (디버깅용)
        parsed["result"] = "no_regulation"
        parsed["confidence"] = min(parsed.get("confidence", 0.5), 0.3)
        parsed.setdefault("warnings", []).append(
            f"LLM이 유효하지 않은 판단 결과 '{result}'를 반환하여 no_regulation으로 대체됨"
        )

    return parsed


def _query_hash(query: str) -> str:
    """쿼리 정규화 후 해시 생성 (공백/대소문자 무시)"""
    normalized = re.sub(r"\s+", " ", query.strip().lower())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def _check_consistency(query: str, parsed: dict) -> dict | None:
    """보조장치 4: 이전 동일 쿼리 캐싱 — 일관성 모니터링.

    같은 질문에 다른 답이 나오면 flag.

    Returns:
        inconsistency info dict if flagged, None otherwise.
    """
    qhash = _query_hash(query)
    current_result = parsed.get("result", "")
    current_conf = parsed.get("confidence", 0.0)

    if qhash in _judgment_cache:
        cached = _judgment_cache[qhash]
        cached["count"] += 1

        if cached["result"] != current_result:
            cached["inconsistent"] = True
            flag = {
                "previous_result": cached["result"],
                "previous_confidence": cached["confidence"],
                "current_result": current_result,
                "current_confidence": current_conf,
                "query_count": cached["count"],
            }
            logger.warning(
                f"[일관성모니터링] 동일 쿼리에 다른 결과! "
                f"이전={cached['result']}({cached['confidence']:.3f}) → "
                f"현재={current_result}({current_conf:.3f})"
            )
            # 캐시 업데이트 (최신 결과로)
            cached["result"] = current_result
            cached["confidence"] = current_conf
            return flag
        else:
            # 동일 결과 — 캐시 갱신
            cached["confidence"] = current_conf
            return None
    else:
        # 새 쿼리 — 캐시 등록 (사이즈 제한)
        if len(_judgment_cache) >= _CACHE_MAX_SIZE:
            # 가장 오래된 항목 제거 (FIFO — dict 삽입 순서 보장, Python 3.7+)
            oldest_key = next(iter(_judgment_cache))
            del _judgment_cache[oldest_key]
        _judgment_cache[qhash] = {
            "result": current_result,
            "confidence": current_conf,
            "count": 1,
            "inconsistent": False,
        }
        return None


def _calibrate_confidence(
    parsed: dict,
    context: list[dict],
    keyword_match: float | None = None,
    article_validations: list[dict] | None = None,
) -> tuple[float, dict]:
    """LLM이 출력한 confidence를 RAG 검색 품질 기반으로 보정한다.

    보정 요소 (5가지):
    1. LLM raw confidence — 60%
    2. RAG 평균 score — 25%
    3. 규정 커버리지 — 15%
    4. 규정 충돌 시 감점 (-0.1/건)
    5. 환각 탐지 감점 — 인용 조항이 RAG에 없으면 추가 감점

    Args:
        keyword_match: 사전 계산된 키워드 매칭 점수 (None이면 내부 계산)
        article_validations: 사전 계산된 조항 검증 결과 (None이면 내부 계산)

    Returns:
        (calibrated_score, breakdown_dict) 튜플.
        breakdown_dict는 각 보정 요소의 기여값을 담고 있어 시각화에 사용.
    """
    llm_conf = parsed.get("confidence", 0.5)

    if not context:
        final = round(min(llm_conf, 0.3), 3)
        return final, {
            "llm_raw": round(llm_conf, 3),
            "llm_weighted": round(llm_conf * 0.6, 3),
            "rag_score": 0.0,
            "rag_weighted": 0.0,
            "coverage_score": 0.0,
            "coverage_weighted": 0.0,
            "conflict_penalty": 0.0,
            "hallucination_penalty": 0.0,
            "article_penalty": 0.0,
            "final": final,
            "note": "규정 문서 없음 — 최대 0.3 제한",
        }

    # RAG 점수 기반 보정
    avg_score = sum(d.get("score", 0) for d in context) / len(context)
    rag_factor = min(avg_score / 0.8, 1.0)  # 0.8 이상이면 1.0

    # 규정 커버리지 보정
    groups = _group_regulations(context)
    coverage_factor = min(len(groups) / 2.0, 1.0)  # 2개 이상 규정이면 1.0

    # 충돌 감지 보정
    cross_refs = parsed.get("cross_references", [])
    conflict_count = sum(
        1 for cr in cross_refs if cr.get("relationship") == "충돌"
    )
    conflict_penalty = 0.1 * conflict_count

    # 환각 탐지 보정 (보조장치 1)
    if keyword_match is None:
        keyword_match = _check_keyword_match(parsed, context)
    # 0.5는 "인용 조항 없음 → 중립"이므로 감점하지 않음
    if keyword_match < 0.5:
        hallucination_penalty = (0.5 - keyword_match) * 0.3  # 매칭 0%일 때 최대 0.15
    else:
        hallucination_penalty = 0.0

    # 조항 존재 검증 보정 (보조장치 2)
    if article_validations is None:
        article_validations = _validate_article_exists(parsed, context)
    if article_validations:
        missing_count = sum(1 for v in article_validations if not v["exists"])
        article_penalty = 0.05 * missing_count
    else:
        article_penalty = 0.0

    calibrated = (
        llm_conf * 0.6
        + rag_factor * 0.25
        + coverage_factor * 0.15
        - conflict_penalty
        - hallucination_penalty
        - article_penalty
    )

    # 개별 요소 임계값 보호 — 어느 하나라도 심각하면 confidence 상한 제한
    # (가중합만으로는 한 요소가 0이어도 다른 요소로 높은 점수가 나올 수 있는 문제 방지)
    cap_note = None
    if rag_factor < 0.2:
        calibrated = min(calibrated, 0.4)
        cap_note = "RAG 검색 품질 낮음 — 최대 0.4 제한"
    if keyword_match < 0.2:
        calibrated = min(calibrated, 0.3)
        cap_note = "환각 의심 심각 — 최대 0.3 제한"
    if article_validations and all(not v["exists"] for v in article_validations):
        calibrated = min(calibrated, 0.25)
        cap_note = "인용 조항 전부 미존재 — 최대 0.25 제한"

    final = round(max(0.0, min(1.0, calibrated)), 3)

    breakdown = {
        "llm_raw": round(llm_conf, 3),
        "llm_weighted": round(llm_conf * 0.6, 3),
        "rag_score": round(avg_score, 3),
        "rag_weighted": round(rag_factor * 0.25, 3),
        "coverage_score": round(len(groups) / 2.0, 3),
        "coverage_weighted": round(coverage_factor * 0.15, 3),
        "conflict_penalty": round(conflict_penalty, 3),
        "hallucination_penalty": round(hallucination_penalty, 3),
        "article_penalty": round(article_penalty, 3),
        "final": final,
    }
    if cap_note:
        breakdown["cap_note"] = cap_note

    return final, breakdown


# ── 메인 Agent 함수 ──


async def judgment_agent(state: AgentState) -> AgentState:
    """
    판단 Agent 노드 함수 (LangGraph 노드 인터페이스)

    1. RAG 파이프라인으로 관련 규정 검색
    2. 규정을 출처별로 그룹핑 (다중 규정 교차 분석)
    3. 대화 이력에서 이전 판단 추출 (일관성 유지)
    4. LLM API에 판단 요청
    5. JSON 응답 파싱 + confidence 보정
    6. agent_response에 저장

    응답 형식:
    {
        "type": "judgment",
        "result": "yes" | "no" | "conditional" | "no_regulation",
        "confidence": 0.85,
        "reasoning": "근거 설명...",
        "regulations": [
            {"article": "정보보안 규정 3.2조", "relevance": "높음", "content": "..."}
        ],
        "cross_references": [
            {"articles": ["조항A", "조항B"], "relationship": "보완", "detail": "..."}
        ],
        "conditions": "조건부일 때 조건 설명",
        "alternatives": ["대안1", "대안2"],
        "regulation_groups": ["규정명1", "규정명2"]
    }
    """
    user_input = state["user_input"]
    user_id = state.get("user_id")
    chat_history = state.get("chat_history", [])

    _t_agent = time.time()
    print(f"[JudgmentAgent] 진입 | user_input='{user_input[:80]}', user_id={user_id}")

    try:
        # 1. RAG 검색 (Reranker + Score Threshold + HyDE 적용)
        _t_rag = time.time()
        print("[JudgmentAgent] RAG 검색 시작 (top_k=5, reranker=True, hyde=True)...")
        pipeline = get_qdrant_pipeline()
        context = pipeline.retrieve(
            query=user_input, user_id=user_id, top_k=5,
            filter={"source": "regulations"},
            use_reranker=True,       # Cross-Encoder로 관련도 재정렬
            score_threshold=0.0,     # Cross-Encoder 점수 0 이하 제거 (노이즈 필터링 강화)
            use_hyde=True,           # HyDE로 벡터 검색 품질 향상
        )
        print(f"[JudgmentAgent] RAG 검색 완료 ({time.time()-_t_rag:.2f}s) | {len(context)}개 문서 검색됨")

        # 2. 판단 이력 추출
        judgment_history = _extract_judgment_history(chat_history)
        print(f"[JudgmentAgent] 판단 이력: {len(judgment_history)}건")

        # 3. 규정 그룹핑 정보
        groups = _group_regulations(context)
        print(f"[JudgmentAgent] 규정 그룹: {list(groups.keys())}")

        # 4. LLM 호출 (sLLM 모드 지원)
        _t_llm = time.time()
        print("[JudgmentAgent] LLM 호출 중...")
        context_text = _build_context_prompt(context)
        user_prompt = _build_user_prompt(
            user_input, context_text, chat_history, judgment_history
        )

        raw_response = await _call_judgment_llm(JUDGMENT_SYSTEM_PROMPT, user_prompt)

        # 5. 응답 파싱 + 3중 보조 장치 + confidence 보정
        parsed = _parse_llm_response(raw_response)
        parsed["type"] = "judgment"

        # 보조장치 3: 판단 결과 카테고리 제한 (yes/no/conditional/no_regulation 외 reject)
        parsed = _validate_result_category(parsed)

        # 보조장치 1,2: 환각 탐지 + 조항 검증 (한 번만 수행)
        keyword_match = _check_keyword_match(parsed, context)
        article_validations = _validate_article_exists(parsed, context)

        # confidence 보정 (사전 계산 결과 전달 → 중복 호출 방지)
        calibrated, confidence_breakdown = _calibrate_confidence(
            parsed, context,
            keyword_match=keyword_match,
            article_validations=article_validations,
        )
        parsed["confidence"] = calibrated
        parsed["confidence_breakdown"] = confidence_breakdown
        parsed.setdefault("cross_references", [])
        parsed["regulation_groups"] = list(groups.keys())

        # 보조장치 2 결과를 응답에 포함 (조항 검증 상세)
        if article_validations:
            parsed["article_validations"] = article_validations
            hallucinated = [v["article"] for v in article_validations if not v["exists"]]
            if hallucinated:
                parsed.setdefault("warnings", []).append(
                    f"환각 의심 조항: {', '.join(hallucinated)} (RAG 검색 결과에 미존재)"
                )

        # 보조장치 4: 일관성 모니터링 (동일 쿼리 캐싱)
        inconsistency = _check_consistency(user_input, parsed)
        if inconsistency:
            parsed["consistency_flag"] = inconsistency
            parsed.setdefault("warnings", []).append(
                f"일관성 경고: 동일 질문에 이전과 다른 결과 "
                f"({inconsistency['previous_result']} → {inconsistency['current_result']})"
            )

        # 표준 필드: message (format_response 호환 + 다른 Agent 참조용)
        parsed["message"] = parsed.get("reasoning", "")

        print(
            f"[JudgmentAgent] 완료 ({time.time()-_t_agent:.2f}s) | "
            f"result={parsed.get('result')}, confidence={parsed.get('confidence')}, "
            f"warnings={len(parsed.get('warnings', []))}건"
        )

        return {
            **state,
            "context": context,
            "agent_response": parsed,
            "error": None,
        }

    except Exception as e:
        print(f"[JudgmentAgent] !!! 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        return {
            **state,
            "agent_response": {
                "type": "judgment",
                "result": "no_regulation",
                "confidence": 0.0,
                "reasoning": f"판단 처리 중 오류가 발생했습니다: {str(e)}",
                "message": f"판단 처리 중 오류가 발생했습니다: {str(e)}",
                "regulations": [],
                "cross_references": [],
                "conditions": None,
                "alternatives": [],
                "regulation_groups": [],
            },
            "error": str(e),
        }


# ── 스트리밍 Agent (SSE 대응) ──


async def judgment_agent_stream(state: AgentState) -> AsyncGenerator[str, None]:
    """
    판단 Agent 스트리밍 버전 (SSE 엔드포인트용)

    토큰 단위로 yield하며, 완료 후 최종 JSON을 별도로 yield한다.
    오케스트레이터에서 SSE 스트리밍 시 이 함수를 호출.

    Yields:
        str: 토큰 단위 텍스트 (스트리밍 중)
        str: "[DONE]" + JSON (스트리밍 완료 후 최종 구조화 응답)
    """
    user_input = state["user_input"]
    user_id = state.get("user_id")
    chat_history = state.get("chat_history", [])

    try:
        # RAG 검색 (Reranker + Score Threshold + HyDE 적용)
        pipeline = get_qdrant_pipeline()
        context = pipeline.retrieve(
            query=user_input, user_id=user_id, top_k=5,
            filter={"source": "regulations"},
            use_reranker=True,
            score_threshold=0.0,
            use_hyde=True,
        )

        # 판단 이력 추출
        judgment_history = _extract_judgment_history(chat_history)

        # 프롬프트 구성
        context_text = _build_context_prompt(context)
        user_prompt = _build_user_prompt(
            user_input, context_text, chat_history, judgment_history
        )

        # 스트리밍 호출 (sLLM 모드 지원)
        global _judgment_model_name
        mode = os.getenv("JUDGMENT_AGENT_MODE", "api")
        if mode == "sllm":
            from ai.serving.vllm_client import VLLMProvider
            use_lora = os.getenv("VLLM_USE_LORA", "false").lower() == "true"
            if use_lora:
                llm = VLLMProvider().with_lora("v1_judgment")
                _judgment_model_name = os.getenv("VLLM_MODEL", "Kanana-1.5-8B") + " (LoRA v1_judgment)"
            else:
                llm = VLLMProvider()
                _judgment_model_name = os.getenv("VLLM_MODEL", "Kanana-1.5-8B") + " (base)"
            print(f"[JudgmentAgent] 스트리밍 sLLM: {_judgment_model_name}")
        else:
            llm = get_llm()
            _judgment_model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            print(f"[JudgmentAgent] 스트리밍 API: {llm.__class__.__name__}")

        full_response = ""
        async for token in llm.stream_generate(
            prompt=user_prompt,
            system_prompt=JUDGMENT_SYSTEM_PROMPT,
            temperature=0.1,
        ):
            full_response += token
            yield token

        # 스트리밍 완료 후 구조화 응답 생성 + 3중 보조 장치
        parsed = _parse_llm_response(full_response)
        parsed["type"] = "judgment"
        parsed = _validate_result_category(parsed)

        # 보조장치 1,2 (한 번만)
        keyword_match = _check_keyword_match(parsed, context)
        article_validations = _validate_article_exists(parsed, context)

        calibrated, confidence_breakdown = _calibrate_confidence(
            parsed, context,
            keyword_match=keyword_match,
            article_validations=article_validations,
        )
        parsed["confidence"] = calibrated
        parsed["confidence_breakdown"] = confidence_breakdown
        parsed.setdefault("cross_references", [])
        groups = _group_regulations(context)
        parsed["regulation_groups"] = list(groups.keys())
        parsed["message"] = parsed.get("reasoning", "")

        # 보조장치 결과 포함
        if article_validations:
            parsed["article_validations"] = article_validations
        inconsistency = _check_consistency(user_input, parsed)
        if inconsistency:
            parsed["consistency_flag"] = inconsistency

        yield "\n[DONE]" + json.dumps(parsed, ensure_ascii=False)

    except Exception as e:
        logger.error(f"judgment_agent_stream 오류: {e}", exc_info=True)
        error_response = {
            "type": "judgment",
            "result": "no_regulation",
            "confidence": 0.0,
            "reasoning": f"판단 처리 중 오류가 발생했습니다: {str(e)}",
            "regulations": [],
            "cross_references": [],
            "conditions": None,
            "alternatives": [],
            "regulation_groups": [],
        }
        yield "\n[DONE]" + json.dumps(error_response, ensure_ascii=False)
