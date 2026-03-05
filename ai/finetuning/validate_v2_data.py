"""
v2 Document 학습 데이터 검증 스크립트

검증 항목:
  공통:
    1. JSONL 파싱, messages 구조 (system/user/assistant)
    2. content 비어있는지, 반복 패턴 탐지
    3. 길이 분포 통계
  v2_generate:
    4. assistant JSON 파싱, 한국어 키 혼입 방지
    5. 동적 필드 명세 기반 필드 존재/과잉 검증
  v2_qa:
    6. assistant JSON 파싱 (answer, citations)
    7. deprecated 필드 거부 (confidence, relevance, source)
    8. citations 배열 구조 검증
  v2_summary:
    9. 마크다운 구조 (## 주요 포인트, ## 키워드)
    10. 포인트 개수 (3~5), 키워드 개수 (3~7)
    11. 키워드 품질 (조사/어미 포함 여부)
    12. 메타지시문 복사 감지
  중복:
    13. 간이 중복 체크 (Jaccard trigram similarity)

사용법:
    # 전체 검증
    python ai/finetuning/validate_v2_data.py

    # 특정 어댑터
    python ai/finetuning/validate_v2_data.py --dir data/training/v2_summary

    # 특정 파일
    python ai/finetuning/validate_v2_data.py --file data/training/v2_qa/aihub_qa.jsonl

    # 중복 체크 포함
    python ai/finetuning/validate_v2_data.py --deduplicate

    # Train/Eval 분할
    python ai/finetuning/validate_v2_data.py --split
"""

import argparse
import io
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

# Windows 콘솔 한글 출력
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent

ADAPTER_DIRS = {
    "v2_generate": BASE_DIR / "data" / "training" / "v2_generate",
    "v2_qa": BASE_DIR / "data" / "training" / "v2_qa",
    "v2_summary": BASE_DIR / "data" / "training" / "v2_summary",
}

QA_FIELDS = ["answer", "citations"]

# 메타지시문 복사 패턴 (summary용)
SUMMARY_META_PATTERNS = [
    "핵심 요약 2-3문장",
    "빈 줄",
    "불릿(-)",
    "명사/명사구",
    "쉼표로 구분",
]

KOREAN_KEY_PATTERN = re.compile(r"[\uac00-\ud7a3]")
REPETITION_PATTERN = re.compile(r"(.{10,})\1{2,}")

# 키워드 품질 체크: 조사/어미가 붙은 단어 패턴
BAD_KEYWORD_ENDINGS = re.compile(
    r"(은|는|이|가|을|를|의|에|에서|으로|로|와|과|도|만|까지|부터|에게|한테|"
    r"였다|했다|됐다|있다|없다|하는|되는|있는|없는|이다|므로|에는|에서는|으며|"
    r"하고|이며|라서|에도|에선|라고|라는|에게서|처럼|같이|보다|마저|조차)$"
)


# ── 태스크/템플릿 감지 ──

def _detect_task(messages: list) -> str:
    sys_content = ""
    for msg in messages:
        if msg.get("role") == "system":
            sys_content = msg.get("content", "")
            break

    sys_lower = sys_content.lower()

    # 동적 필드 방식: "필드 명세" or "기업 문서 작성 전문가"
    if any(kw in sys_lower for kw in ("필드 명세", "기업 문서 작성 전문가", "json으로 생성")):
        return "doc_generate"
    if any(kw in sys_lower for kw in ("질의응답", "citation", "citations")):
        return "doc_qa"
    if any(kw in sys_lower for kw in ("요약", "summary", "주요 포인트", "키워드")):
        return "doc_summary"
    return "unknown"


def _detect_template(messages: list) -> str:
    sys_content = ""
    for msg in messages:
        if msg.get("role") == "system":
            sys_content = msg.get("content", "")
            break

    # 고정 프롬프트 방식
    if "회의록 작성 전문가" in sys_content:
        return "meeting_minutes"
    if "제안서 작성 전문가" in sys_content:
        return "proposal"
    if "보고서 작성 전문가" in sys_content or "업무보고서 작성" in sys_content:
        return "report"
    # 동적 필드 방식: user prompt의 [문서 유형]에서 감지
    user_content = ""
    for msg in messages:
        if msg.get("role") == "user":
            user_content = msg.get("content", "")
            break
    if "[문서 유형] 회의록" in user_content:
        return "meeting_minutes"
    if "[문서 유형] 제안서" in user_content:
        return "proposal"
    if "[문서 유형] 업무보고서" in user_content:
        return "report"
    return "report"


def _safe_parse_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    if not text.startswith("{"):
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ── 검증 함수 ──

def validate_sample(sample: dict, idx: int) -> tuple[list[str], list[str]]:
    """단일 샘플 검증. (errors, warnings) 반환."""
    errors = []
    warnings = []

    # 1. messages 구조
    messages = sample.get("messages")
    if not messages or not isinstance(messages, list) or len(messages) < 3:
        errors.append(f"[{idx}] messages 구조 이상 (3개 필요)")
        return errors, warnings

    roles = [m.get("role") for m in messages]
    if roles != ["system", "user", "assistant"]:
        errors.append(f"[{idx}] role 순서 이상: {roles}")

    # 2. content 비어있는지
    for msg in messages:
        if not msg.get("content", "").strip():
            errors.append(f"[{idx}] {msg.get('role', '?')} content 비어있음")

    assistant_content = messages[2].get("content", "") if len(messages) > 2 else ""
    task_type = _detect_task(messages)

    # 3. 공통 텍스트 품질
    if assistant_content:
        if REPETITION_PATTERN.search(assistant_content):
            warnings.append(f"[{idx}] 반복 패턴 탐지")
        if len(assistant_content) < 20:
            errors.append(f"[{idx}] 응답 너무 짧음 ({len(assistant_content)}자)")
        if len(assistant_content) > 10000:
            warnings.append(f"[{idx}] 응답 너무 김 ({len(assistant_content)}자)")

    # 4. 태스크별 검증
    if task_type == "doc_generate":
        _validate_generate(assistant_content, messages, idx, errors, warnings)
    elif task_type == "doc_qa":
        _validate_qa(assistant_content, idx, errors, warnings)
    elif task_type == "doc_summary":
        _validate_summary(assistant_content, idx, errors, warnings)

    return errors, warnings


def _parse_field_spec(user_content: str) -> list[str]:
    """user prompt의 [필드 명세]에서 필드 이름 목록 추출"""
    fields = []
    in_spec = False
    for line in user_content.split("\n"):
        stripped = line.strip()
        if "[필드 명세]" in stripped:
            in_spec = True
            continue
        if in_spec:
            if stripped.startswith("[") and "필드" not in stripped:
                break  # 다음 섹션 시작
            if stripped.startswith("- ") and ":" in stripped:
                field_name = stripped[2:].split(":")[0].strip()
                if field_name:
                    fields.append(field_name)
    return fields


def _validate_generate(content: str, messages: list, idx: int, errors: list, warnings: list):
    """v2_generate 검증 (동적 필드 명세 기반)"""
    parsed = _safe_parse_json(content)
    if parsed is None:
        errors.append(f"[{idx}] (generate) JSON 파싱 실패")
        return

    # 한국어 키
    korean_keys = [k for k in parsed.keys() if KOREAN_KEY_PATTERN.search(k)]
    if korean_keys:
        errors.append(f"[{idx}] (generate) 한국어 키: {korean_keys}")

    # 동적 필드 명세에서 요청된 필드 파싱
    user_content = messages[1].get("content", "") if len(messages) > 1 else ""
    expected_fields = _parse_field_spec(user_content)

    if expected_fields:
        # 누락 필드 체크
        missing = [f for f in expected_fields if f not in parsed]
        if missing:
            errors.append(f"[{idx}] (generate) 필드 누락: {missing}")

        # 과잉 필드 체크
        extra = [k for k in parsed.keys() if k not in expected_fields]
        if extra:
            warnings.append(f"[{idx}] (generate) 과잉 필드: {extra}")
    else:
        # 필드 명세 파싱 실패 시 기본 체크만
        if len(parsed) == 0:
            errors.append(f"[{idx}] (generate) JSON 키 없음")


def _validate_qa(content: str, idx: int, errors: list, warnings: list):
    """v2_qa 검증 (sLLM 간소화 JSON: answer + citations[].content만)"""
    parsed = _safe_parse_json(content)
    if parsed is None:
        errors.append(f"[{idx}] (qa) JSON 파싱 실패")
        return

    # 필수 필드
    missing = [f for f in QA_FIELDS if f not in parsed]
    if missing:
        errors.append(f"[{idx}] (qa) 필수 필드 누락: {missing}")

    # deprecated 필드 거부 (sLLM v2에서 제거됨 — 백엔드가 RAG score 기반으로 계산)
    for deprecated in ("confidence", "relevance", "source"):
        if deprecated in parsed:
            errors.append(f"[{idx}] (qa) deprecated 필드 '{deprecated}' 존재 (sLLM v2에서 제거됨)")

    # answer 비어있는지
    answer = parsed.get("answer", "")
    if not answer or (isinstance(answer, str) and len(answer.strip()) < 2):
        errors.append(f"[{idx}] (qa) answer 비어있음")

    # citations 검증
    citations = parsed.get("citations", [])
    if not isinstance(citations, list):
        errors.append(f"[{idx}] (qa) citations가 배열 아님")
    elif len(citations) == 0:
        # not-found 케이스는 정상 (빈 배열 허용)
        not_found_answer = "제공된 문서에서 해당 내용을 찾을 수 없습니다."
        if not_found_answer not in answer:
            warnings.append(f"[{idx}] (qa) citations 비어있는데 not-found 문구 없음")
    else:
        for ci, cit in enumerate(citations):
            if not isinstance(cit, dict):
                errors.append(f"[{idx}] (qa) citations[{ci}] dict 아님")
                continue
            if "content" not in cit:
                errors.append(f"[{idx}] (qa) citations[{ci}] 'content' 없음")


def _validate_summary(content: str, idx: int, errors: list, warnings: list):
    """v2_summary 검증"""
    if len(content.strip()) < 30:
        errors.append(f"[{idx}] (summary) 요약 너무 짧음 ({len(content)}자)")

    # 마크다운 구조
    has_points = "## 주요 포인트" in content
    has_keywords = "## 키워드" in content

    if not has_points:
        errors.append(f"[{idx}] (summary) '## 주요 포인트' 없음")
    if not has_keywords:
        errors.append(f"[{idx}] (summary) '## 키워드' 없음")

    # 주요 포인트 불릿 개수 (3~5개)
    if has_points and has_keywords:
        points_section = content.split("## 주요 포인트")[1].split("## 키워드")[0]
        bullets = [line.strip() for line in points_section.strip().splitlines() if line.strip().startswith("- ")]
        if len(bullets) == 0:
            errors.append(f"[{idx}] (summary) 주요 포인트 불릿 없음")
        elif len(bullets) < 3 or len(bullets) > 5:
            errors.append(f"[{idx}] (summary) 주요 포인트 {len(bullets)}개 (3~5개 필요)")
    elif has_points:
        points_section = content.split("## 주요 포인트")[1]
        bullets = [line.strip() for line in points_section.strip().splitlines() if line.strip().startswith("- ")]
        if len(bullets) == 0:
            errors.append(f"[{idx}] (summary) 주요 포인트 불릿 없음")

    # 키워드 개수 (3~7개) + 품질
    if has_keywords:
        kw_section = content.split("## 키워드")[-1].strip()
        keywords = [kw.strip() for kw in kw_section.split(",") if kw.strip()]

        if len(keywords) == 0:
            errors.append(f"[{idx}] (summary) 키워드 비어있음")
        elif len(keywords) < 3 or len(keywords) > 7:
            errors.append(f"[{idx}] (summary) 키워드 {len(keywords)}개 (3~7개 필요)")

        # 조사/어미 붙은 키워드 체크
        bad_kws = [kw for kw in keywords if BAD_KEYWORD_ENDINGS.search(kw)]
        if bad_kws:
            warnings.append(f"[{idx}] (summary) 조사 포함 키워드: {bad_kws}")

    # 메타지시문 복사 감지
    for pattern in SUMMARY_META_PATTERNS:
        if pattern in content:
            errors.append(f"[{idx}] (summary) 메타지시문 복사: '{pattern}'")
            break
    if "포인트" in content and "작성하세요" in content:
        errors.append(f"[{idx}] (summary) 메타지시문 복사: '포인트'+'작성하세요'")


# ── 파일/디렉토리 검증 ──

def validate_file(filepath: Path) -> dict:
    """JSONL 파일 전체 검증"""
    print(f"\n  파일: {filepath.name}")

    samples = []
    parse_errors = 0

    with open(filepath, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                sample = json.loads(line)
                samples.append((line_num, sample))
            except json.JSONDecodeError as e:
                parse_errors += 1
                if parse_errors <= 3:
                    print(f"    [파싱 에러] 줄 {line_num}: {e}")

    print(f"    총 {len(samples) + parse_errors}줄, 파싱 성공 {len(samples)}건, 파싱 실패 {parse_errors}건")

    all_errors = []
    all_warnings = []
    task_counter = Counter()
    template_counter = Counter()
    citation_len_dist = Counter()  # citations 배열 길이 분포 (QA용)
    not_found_count = 0
    user_lens = []
    asst_lens = []

    for line_num, sample in samples:
        errors, warnings = validate_sample(sample, line_num)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

        messages = sample.get("messages", [])
        task_type = _detect_task(messages)
        task_counter[task_type] += 1

        if task_type == "doc_generate":
            template_counter[_detect_template(messages)] += 1

        # QA: citations 길이 분포 수집
        if task_type == "doc_qa" and len(messages) >= 3:
            parsed = _safe_parse_json(messages[2].get("content", ""))
            if parsed and isinstance(parsed.get("citations"), list):
                cit_len = len(parsed["citations"])
                citation_len_dist[cit_len] += 1
                if cit_len == 0:
                    not_found_count += 1

        # 길이 수집
        if len(messages) >= 3:
            user_lens.append(len(messages[1].get("content", "")))
            asst_lens.append(len(messages[2].get("content", "")))

    # 결과 출력
    print(f"    태스크: {dict(task_counter)}")
    if template_counter:
        print(f"    템플릿: {dict(template_counter)}")
    if citation_len_dist:
        total_qa = sum(citation_len_dist.values())
        print(f"    citations 길이 분포: {dict(sorted(citation_len_dist.items()))}")
        print(f"    not-found (citations=[]): {not_found_count}건 ({not_found_count/total_qa*100:.1f}%)")

    if user_lens:
        print(f"    user 길이: 평균 {sum(user_lens)//len(user_lens)}자 "
              f"(min {min(user_lens)}, max {max(user_lens)})")
    if asst_lens:
        print(f"    assistant 길이: 평균 {sum(asst_lens)//len(asst_lens)}자 "
              f"(min {min(asst_lens)}, max {max(asst_lens)})")

    print(f"    에러: {len(all_errors)}건, 경고: {len(all_warnings)}건")

    if all_errors:
        error_types = Counter()
        for err in all_errors:
            match = re.search(r"\(([^)]+)\)", err)
            error_types[match.group(1) if match else "기타"] += 1
        print(f"    에러 유형: {dict(error_types)}")
        for err in all_errors[:5]:
            print(f"      {err}")
        if len(all_errors) > 5:
            print(f"      ... 외 {len(all_errors) - 5}건")

    if all_warnings:
        warn_types = Counter()
        for w in all_warnings:
            match = re.search(r"\(([^)]+)\)", w)
            warn_types[match.group(1) if match else "기타"] += 1
        print(f"    경고 유형: {dict(warn_types)}")

    return {
        "file": str(filepath),
        "total": len(samples),
        "parse_errors": parse_errors,
        "errors": len(all_errors),
        "warnings": len(all_warnings),
        "task_dist": dict(task_counter),
        "template_dist": dict(template_counter),
        "error_list": all_errors,
        "warning_list": all_warnings,
    }


def validate_directory(data_dir: Path) -> list[dict]:
    """단일 디렉토리의 모든 JSONL 파일 검증"""
    jsonl_files = sorted(data_dir.glob("*.jsonl"))
    jsonl_files = [f for f in jsonl_files if f.name not in ("train.jsonl", "eval.jsonl")]

    if not jsonl_files:
        print(f"  경고: {data_dir}에 JSONL 파일 없음")
        return []

    print(f"\n{'='*60}")
    print(f"  {data_dir.name} 검증 ({len(jsonl_files)}개 파일)")
    print(f"{'='*60}")

    results = []
    for fp in jsonl_files:
        results.append(validate_file(fp))
    return results


# ── 중복 체크 ──

def _char_trigrams(text: str) -> list[str]:
    text = text.replace(" ", "").replace("\n", "")
    return [text[i:i+3] for i in range(len(text) - 2)] if len(text) >= 3 else []


def check_duplicates(filepaths: list[Path], threshold: float = 0.95):
    """간이 중복 체크 (샘플링 기반으로 대용량 대응)"""
    print(f"\n{'='*60}")
    print(f"  중복 체크 (threshold={threshold})")
    print(f"{'='*60}")

    all_texts = []
    for filepath in filepaths:
        if filepath.name in ("train.jsonl", "eval.jsonl"):
            continue
        with open(filepath, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    sample = json.loads(line)
                    msgs = sample.get("messages", [])
                    if len(msgs) >= 3:
                        # user + assistant 쌍으로 비교 (not-found처럼 assistant만 같은 경우 제외)
                        user = msgs[1].get("content", "")
                        asst = msgs[2].get("content", "")
                        all_texts.append((filepath.name, line_num, user + asst))
                except json.JSONDecodeError:
                    pass

    print(f"  총 {len(all_texts)}개 샘플")

    if len(all_texts) > 2000:
        print(f"  대용량 → 해시 기반 exact duplicate 체크만 수행")
        # exact duplicate
        seen = {}
        exact_dups = []
        for fname, ln, text in all_texts:
            h = hash(text)
            if h in seen:
                exact_dups.append((seen[h], (fname, ln)))
            else:
                seen[h] = (fname, ln)
        print(f"  완전 중복: {len(exact_dups)}건")
        for (f1, l1), (f2, l2) in exact_dups[:10]:
            print(f"    {f1}:{l1} == {f2}:{l2}")
        return

    # 소규모: Jaccard trigram
    duplicates = []
    trigrams_cache = {}

    for i in range(len(all_texts)):
        if i not in trigrams_cache:
            trigrams_cache[i] = set(_char_trigrams(all_texts[i][2]))
        t1 = trigrams_cache[i]
        if not t1:
            continue

        for j in range(i + 1, len(all_texts)):
            if j not in trigrams_cache:
                trigrams_cache[j] = set(_char_trigrams(all_texts[j][2]))
            t2 = trigrams_cache[j]
            if not t2:
                continue

            intersection = len(t1 & t2)
            union = len(t1 | t2)
            sim = intersection / union if union > 0 else 0

            if sim >= threshold:
                duplicates.append((i, j, sim))

    print(f"  유사 중복: {len(duplicates)}건")
    for idx1, idx2, sim in duplicates[:10]:
        f1, l1, _ = all_texts[idx1]
        f2, l2, _ = all_texts[idx2]
        print(f"    {f1}:{l1} <-> {f2}:{l2} (sim={sim:.3f})")


# ── Train/Eval 분할 ──

def split_train_eval(input_dir: Path, eval_ratio: float = 0.1, seed: int = 42):
    """전체 JSONL → train/eval 분할"""
    print(f"\n  Train/Eval 분할: {input_dir.name} (eval={eval_ratio*100:.0f}%)")

    all_samples = []
    for filepath in sorted(input_dir.glob("*.jsonl")):
        if filepath.name in ("train.jsonl", "eval.jsonl"):
            continue
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    all_samples.append(line)

    if not all_samples:
        print(f"    데이터 없음")
        return

    random.seed(seed)
    random.shuffle(all_samples)

    eval_count = max(1, int(len(all_samples) * eval_ratio))
    eval_samples = all_samples[:eval_count]
    train_samples = all_samples[eval_count:]

    train_path = input_dir / "train.jsonl"
    eval_path = input_dir / "eval.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for s in train_samples:
            f.write(s + "\n")

    with open(eval_path, "w", encoding="utf-8") as f:
        for s in eval_samples:
            f.write(s + "\n")

    print(f"    Train: {len(train_samples)}건 → {train_path.name}")
    print(f"    Eval:  {len(eval_samples)}건 → {eval_path.name}")


# ── 메인 ──

def main():
    parser = argparse.ArgumentParser(description="v2 학습 데이터 검증")
    parser.add_argument("--file", type=str, help="특정 파일 검증")
    parser.add_argument("--dir", type=str, help="특정 디렉토리 검증")
    parser.add_argument("--deduplicate", action="store_true", help="중복 체크")
    parser.add_argument("--split", action="store_true", help="Train/Eval 분할")
    parser.add_argument("--eval_ratio", type=float, default=0.1, help="Eval 비율")
    args = parser.parse_args()

    print("=" * 60)
    print("  v2 학습 데이터 검증")
    print("=" * 60)

    if args.file:
        validate_file(Path(args.file))
        return

    # 디렉토리 결정
    if args.dir:
        dirs_to_check = {Path(args.dir).name: Path(args.dir)}
    else:
        dirs_to_check = {k: v for k, v in ADAPTER_DIRS.items() if v.exists()}

    if not dirs_to_check:
        print("검증할 디렉토리가 없습니다.")
        return

    # 전체 검증
    grand_total = 0
    grand_errors = 0
    grand_warnings = 0
    all_jsonl = []

    for name, data_dir in dirs_to_check.items():
        results = validate_directory(data_dir)
        for r in results:
            grand_total += r["total"]
            grand_errors += r["errors"]
            grand_warnings += r["warnings"]
        all_jsonl.extend([f for f in sorted(data_dir.glob("*.jsonl"))
                          if f.name not in ("train.jsonl", "eval.jsonl")])

    # 전체 요약
    print(f"\n{'='*60}")
    print(f"  전체 요약")
    print(f"{'='*60}")
    print(f"  검증 디렉토리: {len(dirs_to_check)}개")
    print(f"  총 샘플: {grand_total}건")
    print(f"  총 에러: {grand_errors}건")
    print(f"  총 경고: {grand_warnings}건")
    if grand_total > 0:
        err_pct = grand_errors / grand_total * 100
        print(f"  에러율: {err_pct:.1f}%")
        print(f"  판정: {'✅ PASS' if err_pct < 5 else '⚠️ REVIEW' if err_pct < 15 else '❌ FAIL'}")

    if args.deduplicate and all_jsonl:
        check_duplicates(all_jsonl)

    if args.split:
        eval_ratios = {"v2_generate": 0.1, "v2_qa": 0.1, "v2_summary": 0.15}
        for name, d in dirs_to_check.items():
            if list(d.glob("*.jsonl")):
                ratio = eval_ratios.get(name, args.eval_ratio)
                split_train_eval(d, eval_ratio=ratio)


if __name__ == "__main__":
    main()
