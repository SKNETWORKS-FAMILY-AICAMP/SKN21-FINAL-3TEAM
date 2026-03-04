"""
판단 데이터 품질 검증 스크립트

LLM이 생성한 규정판단 파인튜닝 데이터를 전수 자동 검증합니다.
샘플링(사람이 일부만 보는 것)과 달리, 전체 데이터를 프로그래밍으로 체크하고
불량 건만 추려서 인간 검수 대상으로 제시합니다.

검증 항목:
  1. 구조 검증 — JSON 파싱, 필수 필드, 값 범위
  2. 조항 실존 검증 — 인용된 "제N조"가 규정 원문에 실제 존재하는지
  3. 인용 정합성 — 인용한 내용(content)이 규정 원문과 일치하는지
  4. 논리 일관성 — result ↔ confidence, conditional ↔ conditions 정합
  5. 교차참조 검증 — 교차규정 데이터에서 cross_references가 채워졌는지
  6. 중복 검출 — 질문 간 유사도로 복붙/중복 탐지
  7. 분포 분석 — result/confidence/규정 커버리지 통계

사용법:
    # 기존 train/eval 검증
    python scripts/validate_judgment_data.py

    # 교차규정 데이터 검증
    python scripts/validate_judgment_data.py --file data/training/v1_judgment/cross_regulation.jsonl

    # 상세 불량 건 출력
    python scripts/validate_judgment_data.py --verbose

    # 인간 검수 대상만 추출
    python scripts/validate_judgment_data.py --export-flagged
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# 프로젝트 루트
BASE_DIR = Path(__file__).resolve().parent.parent
REGULATION_DIR = BASE_DIR / "data" / "regulations"
TRAINING_DIR = BASE_DIR / "data" / "training" / "v1_judgment"

# Windows 콘솔 UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ═══════════════════════════════════════════════════════════════
# 1. 규정 원문 로드 (검증 기준)
# ═══════════════════════════════════════════════════════════════


def load_regulation_articles() -> dict[str, dict[str, str]]:
    """
    규정 .txt → {규정명: {조항키: 본문}} 로드.
    조항키는 "제N조" 형태로 정규화 (검색용).
    """
    regulations = {}

    for txt_file in sorted(REGULATION_DIR.glob("*.txt")):
        text = txt_file.read_text(encoding="utf-8")
        lines = text.strip().split("\n")
        reg_name = lines[0].strip()  # 첫 줄 = 규정명

        articles = {}
        current_key = None
        current_lines = []

        for line in lines:
            match = re.match(r"^(제\d+조)\s*(\([^)]+\))?", line.strip())
            if match:
                if current_key:
                    articles[current_key] = "\n".join(current_lines).strip()
                article_num = match.group(1)
                article_title = match.group(2) or ""
                current_key = f"{article_num} {article_title}".strip()
                current_lines = [line.strip()]
            elif current_key:
                if re.match(r"^제\d+장\s", line.strip()) or line.strip().startswith("부칙"):
                    articles[current_key] = "\n".join(current_lines).strip()
                    current_key = None
                    current_lines = []
                else:
                    current_lines.append(line)

        if current_key:
            articles[current_key] = "\n".join(current_lines).strip()

        regulations[reg_name] = articles

    return regulations


def find_article_in_regulations(
    regulations: dict, article_ref: str
) -> tuple[str, str, str] | None:
    """
    인용된 조항명(예: "급여규정 제8조 (시간외근무수당)")에서
    실제 규정 원문을 찾아 반환.
    Returns: (규정명, 조항키, 본문) or None
    """
    # "제N조" 패턴 추출
    num_match = re.search(r"제(\d+)조", article_ref)
    if not num_match:
        return None
    article_num = f"제{num_match.group(1)}조"

    # 조항 제목 추출 (괄호 안 내용, 예: "채용", "시간외근무수당")
    title_match = re.search(r"\(([^)]+)\)", article_ref)
    article_title = title_match.group(1) if title_match else ""

    # 1순위: 규정명이 인용에 포함된 경우
    for reg_name, articles in regulations.items():
        if reg_name in article_ref or reg_name.replace("규정", "") in article_ref:
            for key, text in articles.items():
                if article_num in key:
                    return reg_name, key, text

    # 2순위: 조항 제목으로 매칭 (예: "채용" → "제4조 (채용)")
    if article_title:
        for reg_name, articles in regulations.items():
            for key, text in articles.items():
                if article_num in key and article_title in key:
                    return reg_name, key, text

    # 3순위: 조항번호만으로 탐색 (첫 번째 매치)
    for reg_name, articles in regulations.items():
        for key, text in articles.items():
            if article_num in key:
                return reg_name, key, text

    return None


# ═══════════════════════════════════════════════════════════════
# 2. 데이터 로드
# ═══════════════════════════════════════════════════════════════


def load_jsonl(filepath: Path) -> list[dict]:
    """JSONL 파일 로드"""
    records = []
    with open(filepath, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append({"_line": i, **json.loads(line)})
            except json.JSONDecodeError:
                records.append({"_line": i, "_parse_error": True})
    return records


# ═══════════════════════════════════════════════════════════════
# 3. 검증 함수들
# ═══════════════════════════════════════════════════════════════

VALID_RESULTS = {"yes", "no", "conditional", "no_regulation"}
VALID_RELEVANCE = {"높음", "중간", "낮음"}
VALID_RELATIONSHIP = {"보완", "충돌", "상위규정", "보충", "상충", "무관"}


def validate_record(record: dict, regulations: dict, idx: int) -> list[dict]:
    """
    단일 레코드 검증 → 발견된 이슈 리스트 반환.
    각 이슈: {"level": "error|warning|info", "code": "...", "detail": "..."}
    """
    issues = []
    line_num = record.get("_line", idx)

    def add(level, code, detail):
        issues.append({"level": level, "code": code, "detail": detail, "line": line_num})

    # ── 3.1 JSONL 파싱 ──
    if record.get("_parse_error"):
        add("error", "JSONL_PARSE", "JSONL 행 자체가 유효한 JSON이 아님")
        return issues

    # ── 3.2 messages 구조 ──
    messages = record.get("messages")
    if not isinstance(messages, list):
        add("error", "NO_MESSAGES", "messages 필드 누락 또는 배열 아님")
        return issues

    if len(messages) < 3:
        add("error", "MSG_COUNT", f"messages 길이 {len(messages)} (최소 3 필요: system/user/assistant)")
        return issues

    roles = [m.get("role") for m in messages]
    if roles != ["system", "user", "assistant"]:
        add("warning", "ROLE_ORDER", f"role 순서 이상: {roles}")

    # ── 3.3 user 메시지 구조 ──
    user_content = messages[1].get("content", "")
    has_regulation_header = "## 관련 규정 문서" in user_content
    has_question_header = "## 사용자 질문" in user_content

    if not has_regulation_header:
        add("warning", "NO_REG_HEADER", "user 메시지에 '## 관련 규정 문서' 헤더 없음")
    if not has_question_header:
        add("warning", "NO_Q_HEADER", "user 메시지에 '## 사용자 질문' 헤더 없음")

    # 질문 추출
    question = ""
    if has_question_header:
        q_parts = user_content.split("## 사용자 질문")
        if len(q_parts) > 1:
            question = q_parts[1].strip()

    if question and len(question) < 10:
        add("warning", "SHORT_QUESTION", f"질문이 너무 짧음: '{question}'")

    # ── 3.4 assistant 응답 JSON 파싱 ──
    assistant_content = messages[2].get("content", "")

    try:
        answer = json.loads(assistant_content)
    except json.JSONDecodeError:
        add("error", "ANSWER_JSON", "assistant 응답이 유효한 JSON이 아님")
        return issues

    # ── 3.5 필수 필드 검증 ──
    required_fields = ["result", "confidence", "reasoning", "regulations"]
    for field in required_fields:
        if field not in answer:
            add("error", "MISSING_FIELD", f"필수 필드 누락: {field}")

    if "result" not in answer:
        return issues  # 이후 검증 불가

    # ── 3.6 result 값 검증 ──
    result = answer["result"]
    if result not in VALID_RESULTS:
        add("error", "INVALID_RESULT", f"result 값 '{result}'은 유효하지 않음 (허용: {VALID_RESULTS})")

    # ── 3.7 confidence 범위 ──
    confidence = answer.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, (int, float)):
            add("error", "CONF_TYPE", f"confidence가 숫자가 아님: {type(confidence).__name__}")
        elif confidence < 0 or confidence > 1:
            add("error", "CONF_RANGE", f"confidence {confidence}은 0~1 범위 밖")

    # ── 3.8 result ↔ confidence 논리 일관성 ──
    if isinstance(confidence, (int, float)) and result in VALID_RESULTS:
        if result in ("yes", "no") and confidence < 0.5:
            add("warning", "LOW_CONF_CERTAIN", f"result='{result}'인데 confidence={confidence} (0.5 미만)")
        if result == "no_regulation" and confidence > 0.7:
            add("warning", "HIGH_CONF_NO_REG", f"result='no_regulation'인데 confidence={confidence} (0.7 초과)")

    # ── 3.9 conditional ↔ conditions 일관성 ──
    conditions = answer.get("conditions")
    if result == "conditional":
        if not conditions or conditions == "null":
            add("warning", "COND_NO_DESC", "result='conditional'인데 conditions가 비어있거나 null")
    elif result in ("yes", "no") and conditions and conditions != "null":
        add("info", "COND_UNNECESSARY", f"result='{result}'인데 conditions가 채워져 있음")

    # ── 3.10 reasoning 길이 ──
    reasoning = answer.get("reasoning", "")
    if len(reasoning) < 20:
        add("warning", "SHORT_REASONING", f"reasoning이 너무 짧음 ({len(reasoning)}자)")
    if len(reasoning) > 2000:
        add("info", "LONG_REASONING", f"reasoning이 매우 김 ({len(reasoning)}자)")

    # ── 3.11 regulations 배열 검증 ──
    regs = answer.get("regulations", [])
    if not isinstance(regs, list):
        add("error", "REGS_NOT_LIST", "regulations가 배열이 아님")
        regs = []

    if len(regs) == 0 and result != "no_regulation":
        add("error", "NO_REGS_CITED", f"result='{result}'인데 regulations가 비어있음")

    for r_idx, reg in enumerate(regs):
        if not isinstance(reg, dict):
            add("error", "REG_NOT_DICT", f"regulations[{r_idx}]가 객체가 아님")
            continue

        article = reg.get("article", "")
        relevance = reg.get("relevance", "")
        content = reg.get("content", "")

        if not article:
            add("warning", "REG_NO_ARTICLE", f"regulations[{r_idx}].article이 비어있음")
        if relevance and relevance not in VALID_RELEVANCE:
            add("warning", "REG_BAD_RELEVANCE", f"regulations[{r_idx}].relevance='{relevance}' (허용: {VALID_RELEVANCE})")
        if not content:
            add("warning", "REG_NO_CONTENT", f"regulations[{r_idx}].content이 비어있음")

        # 조항 실존 검증
        if article:
            found = find_article_in_regulations(regulations, article)
            if not found:
                # "제N조" 패턴이 있는데 못 찾으면 할루시네이션 가능
                if re.search(r"제\d+조", article):
                    add("warning", "ARTICLE_NOT_FOUND", f"regulations[{r_idx}].article='{article}' — 규정 원문에서 찾을 수 없음 (할루시네이션 가능)")
            else:
                # 인용 정합성: content가 실제 원문과 관련 있는지 간단 체크
                _, _, original_text = found
                if content and len(content) > 10:
                    # content의 핵심 키워드가 원문에 있는지
                    keywords = re.findall(r"[가-힣]{2,}", content)
                    if keywords:
                        matched = sum(1 for kw in keywords if kw in original_text)
                        match_ratio = matched / len(keywords) if keywords else 0
                        if match_ratio < 0.2 and len(keywords) >= 3:
                            add("warning", "CONTENT_MISMATCH",
                                f"regulations[{r_idx}] content 키워드 일치율 {match_ratio:.0%} — "
                                f"인용 내용이 원문과 다를 수 있음")

    # ── 3.12 cross_references 검증 ──
    cross_refs = answer.get("cross_references", [])
    if not isinstance(cross_refs, list):
        add("warning", "XREF_NOT_LIST", "cross_references가 배열이 아님")
        cross_refs = []

    for x_idx, xref in enumerate(cross_refs):
        if not isinstance(xref, dict):
            add("warning", "XREF_NOT_DICT", f"cross_references[{x_idx}]가 객체가 아님")
            continue

        articles = xref.get("articles", [])
        relationship = xref.get("relationship", "")
        detail = xref.get("detail", "")

        if not articles or len(articles) < 2:
            add("warning", "XREF_FEW_ARTICLES", f"cross_references[{x_idx}].articles이 2개 미만")
        if relationship and relationship not in VALID_RELATIONSHIP:
            add("warning", "XREF_BAD_REL", f"cross_references[{x_idx}].relationship='{relationship}' (허용: {VALID_RELATIONSHIP})")
        if not detail:
            add("warning", "XREF_NO_DETAIL", f"cross_references[{x_idx}].detail이 비어있음")

    # ── 3.13 다중 규정인데 cross_references 비어있으면 ──
    if len(regs) >= 2 and len(cross_refs) == 0:
        # 여러 규정명이 인용됐는지 확인
        cited_reg_names = set()
        for reg in regs:
            article = reg.get("article", "")
            for reg_name in regulations:
                if reg_name in article or reg_name.replace("규정", "") in article:
                    cited_reg_names.add(reg_name)
        if len(cited_reg_names) >= 2:
            add("warning", "XREF_EMPTY_MULTI", f"{len(cited_reg_names)}개 규정 인용인데 cross_references가 비어있음")

    # ── 3.14 user context에 있는 규정이 answer에서 인용됐는지 ──
    context_reg_names = set()
    for reg_name in regulations:
        if reg_name in user_content:
            context_reg_names.add(reg_name)

    cited_reg_names_in_answer = set()
    for reg in regs:
        article = reg.get("article", "")
        for reg_name in regulations:
            if reg_name in article:
                cited_reg_names_in_answer.add(reg_name)

    uncited = context_reg_names - cited_reg_names_in_answer
    if uncited and result != "no_regulation" and len(context_reg_names) <= 3:
        add("info", "UNCITED_REG", f"context에 있지만 미인용된 규정: {uncited}")

    return issues


# ═══════════════════════════════════════════════════════════════
# 4. 중복 검출 (질문 유사도)
# ═══════════════════════════════════════════════════════════════


def extract_question(record: dict) -> str:
    """레코드에서 질문 텍스트 추출"""
    try:
        user_content = record["messages"][1]["content"]
        parts = user_content.split("## 사용자 질문")
        if len(parts) > 1:
            return parts[1].strip()
    except (KeyError, IndexError):
        pass
    return ""


def detect_duplicates(records: list[dict], threshold: float = 0.85) -> list[dict]:
    """
    질문 간 자카드 유사도로 중복 탐지.
    (embedding 기반보다 가볍고, 명백한 복붙을 잡기엔 충분)
    """
    duplicates = []
    questions = [(i, extract_question(r)) for i, r in enumerate(records)]
    questions = [(i, q) for i, q in questions if q]

    # 토큰화 (공백 + 한글 형태소 근사)
    def tokenize(text):
        return set(re.findall(r"[가-힣]+|[a-zA-Z]+|\d+", text))

    token_sets = [(i, tokenize(q)) for i, q in questions]

    for a in range(len(token_sets)):
        for b in range(a + 1, len(token_sets)):
            i_a, set_a = token_sets[a]
            i_b, set_b = token_sets[b]
            if not set_a or not set_b:
                continue
            intersection = len(set_a & set_b)
            union = len(set_a | set_b)
            similarity = intersection / union if union > 0 else 0
            if similarity >= threshold:
                duplicates.append({
                    "pair": (i_a, i_b),
                    "similarity": round(similarity, 3),
                    "q_a": questions[a][1][:80],
                    "q_b": questions[b][1][:80],
                })

    return duplicates


# ═══════════════════════════════════════════════════════════════
# 5. 통계 분석
# ═══════════════════════════════════════════════════════════════


def compute_statistics(records: list[dict]) -> dict:
    """데이터 분포 통계"""
    stats = {
        "total": len(records),
        "result_dist": Counter(),
        "confidence_dist": {"0.0-0.5": 0, "0.5-0.7": 0, "0.7-0.9": 0, "0.9-1.0": 0},
        "regulations_count": Counter(),  # 인용 규정 수별 분포
        "cross_ref_count": Counter(),    # 교차참조 수별 분포
        "reasoning_lengths": [],
        "question_lengths": [],
        "cited_regulations": Counter(),  # 어떤 규정이 가장 많이 인용됐는지
        "cited_articles": Counter(),     # 어떤 조항이 가장 많이 인용됐는지
    }

    for record in records:
        try:
            answer = json.loads(record["messages"][2]["content"])
        except (json.JSONDecodeError, KeyError, IndexError):
            continue

        # result 분포
        result = answer.get("result", "?")
        stats["result_dist"][result] += 1

        # confidence 분포
        conf = answer.get("confidence", 0)
        if isinstance(conf, (int, float)):
            if conf < 0.5:
                stats["confidence_dist"]["0.0-0.5"] += 1
            elif conf < 0.7:
                stats["confidence_dist"]["0.5-0.7"] += 1
            elif conf < 0.9:
                stats["confidence_dist"]["0.7-0.9"] += 1
            else:
                stats["confidence_dist"]["0.9-1.0"] += 1

        # regulations 수
        regs = answer.get("regulations", [])
        stats["regulations_count"][len(regs)] += 1

        for reg in regs:
            article = reg.get("article", "")
            stats["cited_articles"][article] += 1
            # 규정명 추출
            for rname in ["급여규정", "출장규정", "교육훈련규정", "복리후생규정",
                          "징계규정", "개인정보처리규정", "윤리강령"]:
                if rname in article:
                    stats["cited_regulations"][rname] += 1

        # cross_references 수
        xrefs = answer.get("cross_references", [])
        stats["cross_ref_count"][len(xrefs)] += 1

        # reasoning 길이
        reasoning = answer.get("reasoning", "")
        stats["reasoning_lengths"].append(len(reasoning))

        # 질문 길이
        question = extract_question(record)
        if question:
            stats["question_lengths"].append(len(question))

    return stats


# ═══════════════════════════════════════════════════════════════
# 6. 리포트 출력
# ═══════════════════════════════════════════════════════════════


def print_report(
    filepath: str,
    records: list[dict],
    all_issues: list[list[dict]],
    duplicates: list[dict],
    stats: dict,
    verbose: bool = False,
):
    """검증 결과 리포트 출력"""
    total = len(records)
    error_count = sum(1 for issues in all_issues if any(i["level"] == "error" for i in issues))
    warning_count = sum(1 for issues in all_issues if any(i["level"] == "warning" for i in issues))
    clean_count = sum(1 for issues in all_issues if not issues)

    # 이슈 코드별 집계
    issue_code_counter = Counter()
    for issues in all_issues:
        for issue in issues:
            issue_code_counter[f"{issue['level']}:{issue['code']}"] += 1

    print()
    print("=" * 70)
    print(f"  판단 데이터 품질 검증 리포트")
    print(f"  파일: {filepath}")
    print("=" * 70)

    # ── 요약 ──
    print(f"\n{'─' * 70}")
    print(f"  1. 검증 요약")
    print(f"{'─' * 70}")
    print(f"  총 레코드    : {total}건")
    print(f"  정상 (이슈 0): {clean_count}건 ({clean_count / total * 100:.1f}%)" if total else "")
    print(f"  경고 포함    : {warning_count}건 ({warning_count / total * 100:.1f}%)" if total else "")
    print(f"  오류 포함    : {error_count}건 ({error_count / total * 100:.1f}%)" if total else "")
    print(f"  중복 의심    : {len(duplicates)}쌍")

    # 품질 점수 (0~100)
    if total > 0:
        # error=-10, warning=-3, duplicate=-5, clean=0
        penalty = error_count * 10 + warning_count * 3 + len(duplicates) * 5
        max_penalty = total * 10
        score = max(0, 100 - (penalty / max_penalty * 100)) if max_penalty > 0 else 100
        grade = "A+" if score >= 95 else "A" if score >= 90 else "B+" if score >= 85 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"
        print(f"\n  품질 점수    : {score:.1f} / 100 ({grade})")

    # ── 이슈 코드별 빈도 ──
    print(f"\n{'─' * 70}")
    print(f"  2. 이슈 유형별 빈도 (상위 15개)")
    print(f"{'─' * 70}")
    for code, cnt in issue_code_counter.most_common(15):
        level, name = code.split(":", 1)
        marker = "!!" if level == "error" else "!" if level == "warning" else " "
        print(f"  {marker} [{level:7s}] {name:30s} : {cnt}건")

    # ── 분포 통계 ──
    print(f"\n{'─' * 70}")
    print(f"  3. 데이터 분포")
    print(f"{'─' * 70}")

    print(f"\n  result 분포:")
    for k, v in stats["result_dist"].most_common():
        bar = "█" * int(v / total * 40) if total else ""
        print(f"    {k:15s}: {v:4d} ({v / total * 100:5.1f}%) {bar}")

    print(f"\n  confidence 분포:")
    for k, v in stats["confidence_dist"].items():
        bar = "█" * int(v / total * 40) if total else ""
        print(f"    {k:10s}: {v:4d} ({v / total * 100:5.1f}%) {bar}")

    print(f"\n  인용 규정 수 분포:")
    for k in sorted(stats["regulations_count"].keys()):
        v = stats["regulations_count"][k]
        print(f"    {k}개 규정: {v:4d}건")

    print(f"\n  교차참조 수 분포:")
    for k in sorted(stats["cross_ref_count"].keys()):
        v = stats["cross_ref_count"][k]
        print(f"    {k}개 교차참조: {v:4d}건")

    print(f"\n  규정별 인용 횟수:")
    for name, cnt in stats["cited_regulations"].most_common():
        print(f"    {name:20s}: {cnt}회")

    if stats["reasoning_lengths"]:
        lengths = stats["reasoning_lengths"]
        avg_len = sum(lengths) / len(lengths)
        min_len = min(lengths)
        max_len = max(lengths)
        print(f"\n  reasoning 길이: 평균 {avg_len:.0f}자, 최소 {min_len}자, 최대 {max_len}자")

    if stats["question_lengths"]:
        q_lengths = stats["question_lengths"]
        avg_q = sum(q_lengths) / len(q_lengths)
        print(f"  질문 길이    : 평균 {avg_q:.0f}자")

    # ── 중복 ──
    if duplicates:
        print(f"\n{'─' * 70}")
        print(f"  4. 중복 의심 ({len(duplicates)}쌍)")
        print(f"{'─' * 70}")
        for d in duplicates[:10]:
            i_a, i_b = d["pair"]
            print(f"\n  [{i_a}] vs [{i_b}] (유사도: {d['similarity']:.1%})")
            print(f"    A: {d['q_a']}")
            print(f"    B: {d['q_b']}")
        if len(duplicates) > 10:
            print(f"\n  ... 외 {len(duplicates) - 10}쌍")

    # ── 상세 불량 건 ──
    if verbose:
        flagged = [(i, issues) for i, issues in enumerate(all_issues) if issues]
        if flagged:
            print(f"\n{'─' * 70}")
            print(f"  5. 상세 불량 건 ({len(flagged)}건)")
            print(f"{'─' * 70}")
            for idx, issues in flagged[:30]:
                question = extract_question(records[idx])
                print(f"\n  [{idx}] (line {records[idx].get('_line', '?')})")
                print(f"    질문: {question[:100]}...")
                for issue in issues:
                    marker = "!!" if issue["level"] == "error" else "!" if issue["level"] == "warning" else " "
                    print(f"    {marker} {issue['code']}: {issue['detail']}")
            if len(flagged) > 30:
                print(f"\n  ... 외 {len(flagged) - 30}건")

    print(f"\n{'=' * 70}")


def export_flagged(
    records: list[dict],
    all_issues: list[list[dict]],
    duplicates: list[dict],
    output_path: Path,
):
    """인간 검수 대상 추출 → JSON 파일"""
    flagged = []

    for idx, issues in enumerate(all_issues):
        if not issues:
            continue

        has_error = any(i["level"] == "error" for i in issues)
        has_warning = any(i["level"] == "warning" for i in issues)

        question = extract_question(records[idx])
        try:
            answer = json.loads(records[idx]["messages"][2]["content"])
        except (json.JSONDecodeError, KeyError, IndexError):
            answer = None

        flagged.append({
            "index": idx,
            "line": records[idx].get("_line", idx),
            "priority": "high" if has_error else "medium" if has_warning else "low",
            "question": question[:200],
            "result": answer.get("result") if answer else None,
            "confidence": answer.get("confidence") if answer else None,
            "issues": issues,
        })

    # 우선순위 정렬: high → medium → low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    flagged.sort(key=lambda x: priority_order.get(x["priority"], 3))

    # 중복도 추가
    for dup in duplicates:
        flagged.append({
            "index": f"{dup['pair'][0]}-{dup['pair'][1]}",
            "priority": "medium",
            "type": "duplicate",
            "similarity": dup["similarity"],
            "q_a": dup["q_a"],
            "q_b": dup["q_b"],
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_records": len(records),
            "flagged_count": len(flagged),
            "flagged_items": flagged,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  인간 검수 대상 추출: {output_path} ({len(flagged)}건)")


# ═══════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="판단 데이터 품질 검증 (전수 자동 검증)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
예시:
  python scripts/validate_judgment_data.py                     # 기본 (train+eval)
  python scripts/validate_judgment_data.py --file cross.jsonl  # 특정 파일
  python scripts/validate_judgment_data.py --verbose           # 상세 불량 건
  python scripts/validate_judgment_data.py --export-flagged    # 인간 검수 대상 추출
""",
    )
    parser.add_argument(
        "--file",
        type=str,
        nargs="*",
        help="검증할 JSONL 파일 경로 (기본: train.jsonl + eval.jsonl)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 불량 건 출력")
    parser.add_argument("--export-flagged", action="store_true", help="인간 검수 대상 JSON 추출")
    args = parser.parse_args()

    # 검증 대상 파일 결정
    if args.file:
        files = [Path(f) for f in args.file]
    else:
        files = []
        for name in ["train.jsonl", "eval.jsonl", "cross_regulation.jsonl"]:
            p = TRAINING_DIR / name
            if p.exists():
                files.append(p)

    if not files:
        print("  검증할 파일이 없습니다.")
        print(f"  확인 경로: {TRAINING_DIR}")
        return

    # 규정 원문 로드
    print("  규정 원문 로드 중...")
    regulations = load_regulation_articles()
    print(f"  {len(regulations)}개 규정 로드 완료")
    for name, articles in regulations.items():
        print(f"    {name}: {len(articles)}개 조항")

    # 각 파일 검증
    for filepath in files:
        print(f"\n  검증 시작: {filepath.name}")

        records = load_jsonl(filepath)
        if not records:
            print(f"  빈 파일: {filepath}")
            continue

        # 전수 검증
        all_issues = []
        for idx, record in enumerate(records):
            issues = validate_record(record, regulations, idx)
            all_issues.append(issues)

        # 중복 검출
        print(f"  중복 검출 중... ({len(records)}건)")
        duplicates = detect_duplicates(records, threshold=0.85)

        # 통계
        stats = compute_statistics(records)

        # 리포트
        print_report(str(filepath), records, all_issues, duplicates, stats, verbose=args.verbose)

        # 인간 검수 대상 추출
        if args.export_flagged:
            flagged_path = filepath.parent / f"{filepath.stem}_flagged.json"
            export_flagged(records, all_issues, duplicates, flagged_path)


if __name__ == "__main__":
    main()
