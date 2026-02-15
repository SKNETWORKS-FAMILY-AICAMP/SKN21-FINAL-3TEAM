"""
판단 Agent 단위 테스트

테스트 항목:
  1. 다중 규정 그룹핑 (_group_regulations)
  2. 규정별 컨텍스트 프롬프트 구성 (_build_context_prompt)
  3. 판단 이력 추출 (_extract_judgment_history)
  4. 프롬프트 구성 (_build_user_prompt)
  5. LLM 응답 파싱 (_parse_llm_response)
  6. confidence 보정 (_calibrate_confidence)
"""
import json


from ai.agents.judgment_agent import (
    _build_context_prompt,
    _build_user_prompt,
    _calibrate_confidence,
    _extract_judgment_history,
    _group_regulations,
    _parse_llm_response,
)


# ── 테스트 데이터 ──

MULTI_REG_CONTEXT = [
    {"content": "직원은 연간 15일의 유급 연차휴가를 사용할 수 있다.", "source": "취업규칙 15조", "score": 0.92},
    {"content": "연차휴가는 1년 미만 시 매월 1일 발생한다.", "source": "취업규칙 16조", "score": 0.85},
    {"content": "재택근무는 주 2회까지 허용된다.", "source": "재택근무 규정 3조", "score": 0.78},
    {"content": "재택근무 시 업무 보고 의무가 있다.", "source": "재택근무 규정 5조", "score": 0.65},
    {"content": "정보보안 위반 시 징계 대상이다.", "source": "정보보안 규정 10조", "score": 0.55},
]

SINGLE_REG_CONTEXT = [
    {"content": "야근 수당은 통상임금의 1.5배이다.", "source": "취업규칙 22조", "score": 0.90},
    {"content": "야근은 사전 승인이 필요하다.", "source": "취업규칙 23조", "score": 0.88},
]

EMPTY_CONTEXT: list[dict] = []


# ── 1. 다중 규정 그룹핑 ──


class TestGroupRegulations:
    def test_groups_by_regulation_name(self):
        """규정명별로 올바르게 그룹핑된다."""
        groups = _group_regulations(MULTI_REG_CONTEXT)

        assert "취업규칙" in groups
        assert "재택근무 규정" in groups
        assert "정보보안 규정" in groups
        assert len(groups["취업규칙"]) == 2
        assert len(groups["재택근무 규정"]) == 2

    def test_single_regulation(self):
        """단일 규정이면 그룹 1개."""
        groups = _group_regulations(SINGLE_REG_CONTEXT)
        assert len(groups) == 1
        assert "취업규칙" in groups

    def test_empty_context(self):
        """빈 context면 빈 dict."""
        groups = _group_regulations(EMPTY_CONTEXT)
        assert groups == {}

    def test_unknown_source(self):
        """출처 불명인 문서도 그룹핑된다."""
        docs = [{"content": "내용", "source": "출처 불명", "score": 0.5}]
        groups = _group_regulations(docs)
        assert "출처 불명" in groups


# ── 2. 컨텍스트 프롬프트 구성 ──


class TestBuildContextPrompt:
    def test_multi_reg_has_warning(self):
        """다중 규정이면 교차 분석 경고 문구가 포함된다."""
        prompt = _build_context_prompt(MULTI_REG_CONTEXT)
        assert "다중 규정 교차 분석 필요" in prompt

    def test_single_reg_no_warning(self):
        """단일 규정이면 교차 분석 경고 없음."""
        prompt = _build_context_prompt(SINGLE_REG_CONTEXT)
        assert "다중 규정 교차 분석 필요" not in prompt

    def test_empty_context_message(self):
        """빈 context면 안내 메시지 반환."""
        prompt = _build_context_prompt(EMPTY_CONTEXT)
        assert "찾지 못했습니다" in prompt

    def test_score_included(self):
        """관련도 점수가 프롬프트에 포함된다."""
        prompt = _build_context_prompt(MULTI_REG_CONTEXT)
        assert "관련도: 0.920" in prompt


# ── 3. 판단 이력 추출 ──


class TestExtractJudgmentHistory:
    def test_extracts_judgment_from_history(self):
        """assistant 메시지에서 judgment JSON을 추출한다."""
        judgment_json = json.dumps({
            "type": "judgment",
            "result": "yes",
            "confidence": 0.9,
            "reasoning": "규정에 의하면 가능합니다.",
        }, ensure_ascii=False)
        chat_history = [
            {"role": "user", "content": "연차 사용 가능한가요?"},
            {"role": "assistant", "content": judgment_json},
        ]

        history = _extract_judgment_history(chat_history)
        assert len(history) == 1
        assert history[0]["result"] == "yes"

    def test_ignores_non_judgment(self):
        """judgment 타입이 아닌 응답은 무시한다."""
        chat_history = [
            {"role": "assistant", "content": "안녕하세요. 도움이 필요하시면 말씀해주세요."},
        ]
        history = _extract_judgment_history(chat_history)
        assert len(history) == 0

    def test_empty_history(self):
        """빈 대화 이력이면 빈 리스트."""
        assert _extract_judgment_history([]) == []
        assert _extract_judgment_history(None) == []

    def test_handles_malformed_json(self):
        """잘못된 JSON은 건너뛴다."""
        chat_history = [
            {"role": "assistant", "content": '{"type": "judgment", broken json'},
        ]
        history = _extract_judgment_history(chat_history)
        assert len(history) == 0


# ── 4. 프롬프트 구성 ──


class TestBuildUserPrompt:
    def test_includes_question(self):
        """사용자 질문이 프롬프트에 포함된다."""
        prompt = _build_user_prompt("연차 가능한가요?", "규정 텍스트")
        assert "연차 가능한가요?" in prompt

    def test_includes_context(self):
        """규정 텍스트가 프롬프트에 포함된다."""
        prompt = _build_user_prompt("질문", "규정 내용 여기")
        assert "규정 내용 여기" in prompt

    def test_includes_chat_history(self):
        """대화 이력이 있으면 프롬프트에 포함된다."""
        history = [{"role": "user", "content": "이전 질문"}]
        prompt = _build_user_prompt("현재 질문", "규정", chat_history=history)
        assert "이전 대화" in prompt
        assert "이전 질문" in prompt

    def test_includes_judgment_history(self):
        """판단 이력이 있으면 프롬프트에 포함된다."""
        jh = [{"result": "yes", "confidence": 0.9, "reasoning": "가능합니다"}]
        prompt = _build_user_prompt("질문", "규정", judgment_history=jh)
        assert "이전 판단 이력" in prompt
        assert "결과: yes" in prompt

    def test_no_history_no_sections(self):
        """이력이 없으면 이력 섹션이 없다."""
        prompt = _build_user_prompt("질문", "규정")
        assert "이전 대화" not in prompt
        assert "이전 판단 이력" not in prompt


# ── 5. LLM 응답 파싱 ──


class TestParseLlmResponse:
    def test_parse_clean_json(self):
        """깨끗한 JSON을 파싱한다."""
        raw = '{"result": "yes", "confidence": 0.9, "reasoning": "허용됨"}'
        parsed = _parse_llm_response(raw)
        assert parsed["result"] == "yes"
        assert parsed["confidence"] == 0.9

    def test_parse_json_in_codeblock(self):
        """```json 코드블록 안의 JSON을 파싱한다."""
        raw = '```json\n{"result": "no", "confidence": 0.8}\n```'
        parsed = _parse_llm_response(raw)
        assert parsed["result"] == "no"

    def test_parse_json_with_surrounding_text(self):
        """앞뒤 텍스트가 있어도 JSON을 추출한다."""
        raw = '판단 결과입니다: {"result": "conditional", "confidence": 0.7} 이상입니다.'
        parsed = _parse_llm_response(raw)
        assert parsed["result"] == "conditional"

    def test_parse_failure_returns_fallback(self):
        """파싱 실패 시 fallback 응답을 반환한다."""
        raw = "이것은 JSON이 아닙니다"
        parsed = _parse_llm_response(raw)
        assert parsed["result"] == "no_regulation"
        assert parsed["confidence"] == 0.0
        assert "cross_references" in parsed

    def test_parse_with_cross_references(self):
        """cross_references가 포함된 JSON을 파싱한다."""
        raw = json.dumps({
            "result": "conditional",
            "confidence": 0.75,
            "reasoning": "두 규정을 종합하면...",
            "regulations": [],
            "cross_references": [
                {"articles": ["취업규칙 15조", "재택근무 규정 3조"], "relationship": "보완", "detail": "상호 보완"}
            ],
            "conditions": "팀장 승인 필요",
            "alternatives": [],
        })
        parsed = _parse_llm_response(raw)
        assert len(parsed["cross_references"]) == 1
        assert parsed["cross_references"][0]["relationship"] == "보완"


# ── 6. confidence 보정 ──


class TestCalibrateConfidence:
    def test_no_context_caps_at_03(self):
        """규정이 없으면 confidence 최대 0.3."""
        parsed = {"confidence": 0.9}
        result = _calibrate_confidence(parsed, EMPTY_CONTEXT)
        assert result <= 0.3

    def test_high_rag_score_boosts(self):
        """RAG 점수가 높으면 confidence가 상향 보정된다."""
        parsed = {"confidence": 0.7}
        high_score_ctx = [{"content": "c", "source": "s", "score": 0.95}]
        low_score_ctx = [{"content": "c", "source": "s", "score": 0.3}]

        high_result = _calibrate_confidence(parsed, high_score_ctx)
        low_result = _calibrate_confidence(parsed, low_score_ctx)
        assert high_result > low_result

    def test_multi_reg_coverage_boosts(self):
        """다중 규정이면 coverage 보정으로 confidence가 상향된다."""
        parsed = {"confidence": 0.7}
        single = _calibrate_confidence(parsed, SINGLE_REG_CONTEXT)
        multi = _calibrate_confidence(parsed, MULTI_REG_CONTEXT)
        assert multi >= single

    def test_conflict_penalty(self):
        """충돌이 있으면 confidence가 하향 보정된다."""
        no_conflict = {"confidence": 0.8, "cross_references": []}
        with_conflict = {
            "confidence": 0.8,
            "cross_references": [{"relationship": "충돌"}],
        }

        result_no = _calibrate_confidence(no_conflict, MULTI_REG_CONTEXT)
        result_yes = _calibrate_confidence(with_conflict, MULTI_REG_CONTEXT)
        assert result_no > result_yes

    def test_result_in_range(self):
        """결과는 항상 0.0 ~ 1.0 범위."""
        parsed = {"confidence": 1.5, "cross_references": []}
        result = _calibrate_confidence(parsed, MULTI_REG_CONTEXT)
        assert 0.0 <= result <= 1.0

        parsed_low = {"confidence": -0.5}
        result_low = _calibrate_confidence(parsed_low, MULTI_REG_CONTEXT)
        assert 0.0 <= result_low <= 1.0
