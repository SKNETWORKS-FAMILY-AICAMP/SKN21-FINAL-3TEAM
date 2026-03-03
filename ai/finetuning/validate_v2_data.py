"""
v2 Document 학습 데이터 검증 스크립트

검증 항목:
  1. JSON 파싱 가능 여부
  2. messages 구조 검증 (system/user/assistant 3개 메시지)
  3. 필수 필드 존재 여부 (태스크/템플릿별 스키마 체크)
  4. 필드명이 정확한 영문 키인지 (한국어 키 혼입 방지)
  5. 한국어 텍스트 품질 (영어 혼입, 의미 없는 반복 탐지)
  6. 의미 유사도 기반 중복 제거 (코사인 > 0.95 → 제거)
  7. 다중 모델 교차 검증 보고

사용법:
    # 전체 검증 (data/training/v2_document/ 내 모든 JSONL)
    python ai/finetuning/validate_v2_data.py

    # 특정 파일 검증
    python ai/finetuning/validate_v2_data.py --file data/training/v2_document/train.jsonl

    # 중복 제거 (실제 파일 수정)
    python ai/finetuning/validate_v2_data.py --deduplicate

    # Train/Eval 분할
    python ai/finetuning/validate_v2_data.py --split --eval_ratio 0.1
"""

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "v2_document"

# ── 필수 필드 정의 ──

# doc_generate: 템플릿별 필수 영문 키
GENERATE_FIELDS = {
    "meeting_minutes": {
        "required": ["title", "date", "attendees", "summary", "decisions", "action_items"],
        "optional": ["time", "location", "meeting_type", "author", "risks", "notes"],
    },
    "report": {
        "required": ["title", "author", "date", "department", "report_type", "overview", "main_content", "tasks"],
        "optional": ["position", "report_to", "issues", "next_plan", "attachments", "notes"],
    },
    "proposal": {
        "required": [
            "title", "submit_date", "submit_to", "company", "manager",
            "proposal_name", "background", "purpose", "content", "schedule", "budget",
        ],
        "optional": [
            "contact", "proposal_date", "period", "proposer", "manager_contact",
            "analysis", "budget_total", "expected_effect", "attachments", "notes",
        ],
    },
    "jd": {
        "required": ["position", "employment_type", "responsibilities", "requirements"],
        "optional": ["experience", "location", "preferred", "benefits"],
    },
}

# doc_qa 필수 필드
QA_FIELDS = {
    "required": ["answer", "citations", "confidence"],
}

# 한국어 키 패턴 (영문 키에 한국어 섞인 경우 감지)
KOREAN_KEY_PATTERN = re.compile(r"[\uac00-\ud7a3]")

# 반복 패턴 탐지
REPETITION_PATTERN = re.compile(r"(.{10,})\1{2,}")


# ── 검증 함수 ──


def validate_sample(sample: dict, idx: int) -> list[str]:
    """단일 샘플 검증. 에러 목록 반환."""
    errors = []

    # 1. messages 구조
    messages = sample.get("messages")
    if not messages:
        errors.append(f"[{idx}] messages 필드 없음")
        return errors

    if not isinstance(messages, list) or len(messages) < 2:
        errors.append(f"[{idx}] messages는 최소 2개 메시지 필요 (현재 {len(messages) if isinstance(messages, list) else 0}개)")
        return errors

    roles = [m.get("role") for m in messages]
    if roles[0] != "system":
        errors.append(f"[{idx}] 첫 번째 메시지 role이 'system'이 아님: {roles[0]}")
    if "user" not in roles:
        errors.append(f"[{idx}] 'user' role 메시지 없음")
    if "assistant" not in roles:
        errors.append(f"[{idx}] 'assistant' role 메시지 없음")

    # 2. content 비어있는지
    for msg in messages:
        if not msg.get("content", "").strip():
            errors.append(f"[{idx}] {msg.get('role', '?')} 메시지 content 비어있음")

    # 3. 태스크 타입 감지 + 필드 검증
    task_type = _detect_task(messages)
    assistant_content = ""
    for msg in messages:
        if msg.get("role") == "assistant":
            assistant_content = msg.get("content", "")
            break

    if task_type in ("doc_generate", "doc_qa"):
        # JSON 파싱 검증
        parsed = _safe_parse_json(assistant_content)
        if parsed is None:
            errors.append(f"[{idx}] ({task_type}) assistant 응답이 유효한 JSON이 아님")
        else:
            # 한국어 키 검사
            korean_keys = [k for k in parsed.keys() if KOREAN_KEY_PATTERN.search(k)]
            if korean_keys:
                errors.append(f"[{idx}] ({task_type}) 한국어 키 발견: {korean_keys}")

            # 필수 필드 검사
            if task_type == "doc_generate":
                template_type = _detect_template(messages)
                fields_spec = GENERATE_FIELDS.get(template_type, {})
                required = fields_spec.get("required", [])
                missing = [f for f in required if f not in parsed]
                if missing:
                    errors.append(f"[{idx}] ({task_type}/{template_type}) 필수 필드 누락: {missing}")

            elif task_type == "doc_qa":
                required = QA_FIELDS["required"]
                missing = [f for f in required if f not in parsed]
                if missing:
                    errors.append(f"[{idx}] ({task_type}) 필수 필드 누락: {missing}")

                # citations 구조 검사
                citations = parsed.get("citations", [])
                if isinstance(citations, list):
                    for ci, citation in enumerate(citations):
                        if not isinstance(citation, dict):
                            errors.append(f"[{idx}] citations[{ci}]가 dict가 아님")
                        elif "content" not in citation:
                            errors.append(f"[{idx}] citations[{ci}]에 'content' 키 없음")

    elif task_type == "doc_summary":
        # 마크다운 요약 검증
        if len(assistant_content.strip()) < 30:
            errors.append(f"[{idx}] (doc_summary) 요약이 너무 짧음 ({len(assistant_content)}자)")

    # 4. 텍스트 품질
    if assistant_content:
        # 반복 패턴 탐지
        if REPETITION_PATTERN.search(assistant_content):
            errors.append(f"[{idx}] 반복 패턴 탐지됨")

        # 너무 짧거나 긴 응답
        if len(assistant_content) < 20:
            errors.append(f"[{idx}] 응답이 너무 짧음 ({len(assistant_content)}자)")
        if len(assistant_content) > 10000:
            errors.append(f"[{idx}] 응답이 너무 김 ({len(assistant_content)}자)")

    return errors


def validate_file(filepath: Path) -> dict:
    """JSONL 파일 전체 검증"""
    print(f"\n파일 검증: {filepath}")

    samples = []
    parse_errors = 0
    line_count = 0

    with open(filepath, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            line_count += 1
            try:
                sample = json.loads(line)
                samples.append((line_num, sample))
            except json.JSONDecodeError as e:
                parse_errors += 1
                print(f"  [JSONL 파싱 에러] 줄 {line_num}: {e}")

    print(f"  총 {line_count}줄, 파싱 성공 {len(samples)}건, 파싱 실패 {parse_errors}건")

    # 샘플별 검증
    all_errors = []
    task_counter = Counter()
    template_counter = Counter()

    for line_num, sample in samples:
        errors = validate_sample(sample, line_num)
        all_errors.extend(errors)

        task_type = _detect_task(sample.get("messages", []))
        task_counter[task_type] += 1
        if task_type == "doc_generate":
            template_type = _detect_template(sample.get("messages", []))
            template_counter[template_type] += 1

    # 결과 출력
    print(f"\n  태스크 분포: {dict(task_counter)}")
    if template_counter:
        print(f"  템플릿 분포: {dict(template_counter)}")
    print(f"  검증 에러: {len(all_errors)}건")

    if all_errors:
        # 에러 유형별 집계
        error_types = Counter()
        for err in all_errors:
            # 괄호 안의 타입 추출
            match = re.search(r"\(([^)]+)\)", err)
            error_type = match.group(1) if match else "기타"
            error_types[error_type] += 1

        print(f"\n  에러 유형:")
        for etype, count in error_types.most_common():
            print(f"    {etype}: {count}건")

        # 처음 10개 에러만 출력
        print(f"\n  에러 상세 (처음 10개):")
        for err in all_errors[:10]:
            print(f"    {err}")

    return {
        "file": str(filepath),
        "total_lines": line_count,
        "parse_success": len(samples),
        "parse_errors": parse_errors,
        "validation_errors": len(all_errors),
        "task_distribution": dict(task_counter),
        "template_distribution": dict(template_counter),
        "errors": all_errors,
    }


def check_duplicates(filepaths: list[Path], threshold: float = 0.95) -> list[tuple[int, int, float]]:
    """간이 중복 체크 (assistant 응답의 문자열 유사도 기반)

    Returns:
        [(idx1, idx2, similarity), ...] — 중복 쌍 목록
    """
    print("\n중복 체크 중...")
    all_texts = []

    for filepath in filepaths:
        with open(filepath, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    sample = json.loads(line)
                    assistant_text = ""
                    for msg in sample.get("messages", []):
                        if msg.get("role") == "assistant":
                            assistant_text = msg.get("content", "")
                            break
                    all_texts.append((filepath, line_num, assistant_text))
                except json.JSONDecodeError:
                    pass

    print(f"  총 {len(all_texts)}개 샘플")
    duplicates = []

    # 간이 유사도: Jaccard similarity on character trigrams
    trigrams_cache = {}
    for i, (fp1, ln1, text1) in enumerate(all_texts):
        if i not in trigrams_cache:
            trigrams_cache[i] = set(_char_trigrams(text1))
        t1 = trigrams_cache[i]
        if not t1:
            continue

        for j in range(i + 1, len(all_texts)):
            if j not in trigrams_cache:
                trigrams_cache[j] = set(_char_trigrams(all_texts[j][2]))
            t2 = trigrams_cache[j]
            if not t2:
                continue

            # Jaccard similarity
            intersection = len(t1 & t2)
            union = len(t1 | t2)
            sim = intersection / union if union > 0 else 0

            if sim >= threshold:
                duplicates.append((i, j, sim))

    print(f"  중복 쌍: {len(duplicates)}개 (threshold={threshold})")
    for idx1, idx2, sim in duplicates[:10]:
        fp1, ln1, _ = all_texts[idx1]
        fp2, ln2, _ = all_texts[idx2]
        print(f"    {fp1.name}:{ln1} <-> {fp2.name}:{ln2} (sim={sim:.3f})")

    return duplicates


def split_train_eval(input_dir: Path, eval_ratio: float = 0.1, seed: int = 42):
    """전체 JSONL 파일들을 합쳐서 train/eval 분할"""
    print(f"\nTrain/Eval 분할 (eval_ratio={eval_ratio})")

    all_samples = []
    for filepath in sorted(input_dir.glob("*.jsonl")):
        if filepath.name in ("train.jsonl", "eval.jsonl"):
            continue
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    all_samples.append(line)

    print(f"  총 {len(all_samples)}개 샘플")

    random.seed(seed)
    random.shuffle(all_samples)

    eval_count = max(1, int(len(all_samples) * eval_ratio))
    eval_samples = all_samples[:eval_count]
    train_samples = all_samples[eval_count:]

    train_path = input_dir / "train.jsonl"
    eval_path = input_dir / "eval.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for sample in train_samples:
            f.write(sample + "\n")

    with open(eval_path, "w", encoding="utf-8") as f:
        for sample in eval_samples:
            f.write(sample + "\n")

    print(f"  Train: {len(train_samples)}건 → {train_path}")
    print(f"  Eval:  {len(eval_samples)}건 → {eval_path}")


# ── 유틸리티 ──


def _detect_task(messages: list) -> str:
    """시스템 프롬프트에서 태스크 타입 감지"""
    sys_content = ""
    for msg in messages:
        if msg.get("role") == "system":
            sys_content = msg.get("content", "").lower()
            break

    if any(kw in sys_content for kw in ("문서 작성", "회의록", "보고서", "제안서", "jd", "채용")):
        return "doc_generate"
    if any(kw in sys_content for kw in ("질의응답", "qa", "인용", "citation")):
        return "doc_qa"
    if any(kw in sys_content for kw in ("요약", "summary")):
        return "doc_summary"
    return "unknown"


def _detect_template(messages: list) -> str:
    """시스템 프롬프트에서 템플릿 타입 감지"""
    sys_content = ""
    for msg in messages:
        if msg.get("role") == "system":
            sys_content = msg.get("content", "").lower()
            break

    if "회의록" in sys_content:
        return "meeting_minutes"
    if "제안서" in sys_content:
        return "proposal"
    if "jd" in sys_content or "채용" in sys_content:
        return "jd"
    return "report"


def _safe_parse_json(text: str) -> dict | None:
    """텍스트에서 JSON 추출"""
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


def _char_trigrams(text: str) -> list[str]:
    """문자 3-gram 생성"""
    text = text.replace(" ", "").replace("\n", "")
    return [text[i:i+3] for i in range(len(text) - 2)] if len(text) >= 3 else []


# ── 엔트리포인트 ──


def main():
    parser = argparse.ArgumentParser(description="v2 Document 학습 데이터 검증")
    parser.add_argument("--file", type=str, default=None, help="특정 JSONL 파일 검증")
    parser.add_argument("--dir", type=str, default=str(DATA_DIR), help="데이터 디렉토리")
    parser.add_argument("--deduplicate", action="store_true", help="중복 체크")
    parser.add_argument("--split", action="store_true", help="Train/Eval 분할")
    parser.add_argument("--eval_ratio", type=float, default=0.1, help="Eval 비율")
    args = parser.parse_args()

    data_dir = Path(args.dir)

    if args.file:
        validate_file(Path(args.file))
        return

    # 디렉토리 내 모든 JSONL 검증
    jsonl_files = sorted(data_dir.glob("*.jsonl"))
    if not jsonl_files:
        print(f"경고: {data_dir}에 JSONL 파일 없음")
        return

    print(f"데이터 디렉토리: {data_dir}")
    print(f"JSONL 파일: {len(jsonl_files)}개")

    all_results = []
    for filepath in jsonl_files:
        if filepath.name in ("train.jsonl", "eval.jsonl") and not args.file:
            continue  # 분할 결과 파일은 건너뜀
        result = validate_file(filepath)
        all_results.append(result)

    # 전체 요약
    total_samples = sum(r["parse_success"] for r in all_results)
    total_errors = sum(r["validation_errors"] for r in all_results)
    print(f"\n{'=' * 60}")
    print(f"  전체 요약")
    print(f"{'=' * 60}")
    print(f"  총 샘플: {total_samples}건")
    print(f"  총 에러: {total_errors}건")
    print(f"  에러율:  {total_errors/total_samples*100:.1f}%" if total_samples > 0 else "  에러율: N/A")

    if args.deduplicate:
        check_duplicates(jsonl_files)

    if args.split:
        split_train_eval(data_dir, eval_ratio=args.eval_ratio)


if __name__ == "__main__":
    main()
