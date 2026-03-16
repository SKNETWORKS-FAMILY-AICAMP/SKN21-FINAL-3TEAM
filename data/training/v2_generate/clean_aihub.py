"""
AI Hub 학습 데이터 정제 스크립트

목적:
  - priority 필드(content/summary/decisions/tasks/schedule 등)가 빈 값인 샘플 보충
  - 기존 텍스트 필드에서 GPT로 추출하여 채움
  - 필드 명세(user message)도 동기화

사용법:
    python data/training/v2_generate/clean_aihub.py --dry-run
    python data/training/v2_generate/clean_aihub.py
"""

import argparse
import io
import json
import os
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=True)
except ImportError:
    pass

INPUT_PATH = BASE_DIR / "data" / "training" / "v2_generate" / "ai_hub_generate.jsonl"
OUTPUT_PATH = BASE_DIR / "data" / "training" / "v2_generate" / "ai_hub_generate_cleaned.jsonl"

# 입력 길이 다양화: AI Hub 원본은 대부분 중~장문이므로
# 일부 샘플의 입력(user message 내 passage)을 짧게 축약하여
# "짧은 입력 → 풍부한 출력" 패턴도 학습시킴
SHORT_INPUT_RATIO = 0.25  # 25% 샘플을 짧은 입력으로 축약

# 유형별 priority 필드 (반드시 채워져야 할 필드)
PRIORITY_FIELDS = {
    "meeting_minutes": {
        "content": "회의 내용을 상세하게 기술",
        "summary": "회의에서 논의된 주요 내용을 3~5문장으로 요약",
        "decisions": "결정된 사항 목록 (배열, 없으면 빈 배열)",
        "action_items": '후속 조치 목록 배열. 각 항목은 {"content": "내용", "assignee": "담당자", "due_date": "기한"} 형태',
    },
    "report": {
        "overview": "업무 내용을 요약한 보고 개요 (3~5문장)",
        "main_content": "업무 세부 내용을 항목별로 구체적으로 작성",
        "tasks": '진행 업무 목록 배열. 각 항목은 {"item": "업무명", "assignee": "담당자", "progress": "진행률", "start_date": "시작일", "end_date": "종료일"} 형태',
        "next_plan": "향후 계획 (구체적으로 작성)",
    },
    "proposal": {
        "content": "제안 내용을 항목별로 구체적으로 작성",
        "expected_effect": "기대 효과 (3~5문장)",
        "schedule": '추진 일정 배열. 각 항목은 {"phase": "단계", "task": "업무", "period": "기간"} 형태',
        "budget": '예산 배열. 각 항목은 {"item": "항목", "amount": "금액"} 형태',
    },
}


def shorten_passage(passage: str, model: str = "gpt-4o-mini", max_retries: int = 3) -> str | None:
    """긴 passage를 50~200자 메모/키워드 형태로 축약"""
    from openai import OpenAI
    client = OpenAI()

    system_prompt = (
        "주어진 텍스트를 50~200자 이내의 간단한 메모/키워드 나열 형태로 축약하세요.\n"
        "예시: '팀미팅 진행, 예산 10% 삭감 결정, 신규 프로젝트 킥오프, 담당자 김철수 배정'\n"
        "핵심 정보(주제, 결정사항, 수치, 이름)만 남기고 나머지는 생략하세요.\n"
        "축약된 텍스트만 출력하세요."
    )

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": passage[:2000]},
                ],
                temperature=0.5,
                max_tokens=300,
            )
            result = response.choices[0].message.content.strip()
            if 30 <= len(result) <= 300:
                return result
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return None


def detect_doc_type(user_msg: str) -> str:
    if "회의록" in user_msg:
        return "meeting_minutes"
    elif "보고서" in user_msg or "업무보고" in user_msg:
        return "report"
    elif "제안서" in user_msg:
        return "proposal"
    return "unknown"


def get_source_text(output: dict) -> str:
    """출력 JSON에서 가장 긴 텍스트를 source로 사용"""
    candidates = []
    for key in ["content", "main_content", "overview", "summary", "purpose",
                 "background", "current_situation", "scope", "expected_effect"]:
        val = output.get(key, "")
        if isinstance(val, str) and len(val) > 30:
            candidates.append(val)

    # 나머지 문자열 필드도 추가
    for key, val in output.items():
        if isinstance(val, str) and len(val) > 50 and val not in candidates:
            candidates.append(val)

    if not candidates:
        return ""

    return "\n\n".join(candidates)


def find_missing_priority_fields(output: dict, doc_type: str) -> dict:
    """비어있는 priority 필드 찾기. {field_name: description} 반환"""
    priority = PRIORITY_FIELDS.get(doc_type, {})
    missing = {}
    for field, desc in priority.items():
        val = output.get(field)
        if val is None or val == "" or val == [] or val == {}:
            missing[field] = desc
        elif field not in output:
            missing[field] = desc
    return missing


def call_gpt_extract(source_text: str, missing_fields: dict, doc_type: str,
                     model: str = "gpt-4o-mini", max_retries: int = 3) -> dict:
    """GPT로 source_text에서 missing_fields 추출"""
    from openai import OpenAI
    client = OpenAI()

    doc_type_names = {
        "meeting_minutes": "회의록",
        "report": "업무보고서",
        "proposal": "제안서",
    }
    doc_name = doc_type_names.get(doc_type, "문서")

    field_spec = "\n".join(f"- {k}: {v}" for k, v in missing_fields.items())

    system_prompt = (
        f"당신은 {doc_name} 분석 전문가입니다. "
        "주어진 문서 내용에서 아래 필드에 해당하는 정보를 추출하여 JSON으로 반환하세요.\n\n"
        "규칙:\n"
        "- 문서 내용에 명시적으로 언급된 내용만 추출하세요.\n"
        "- 추측하거나 새로운 내용을 만들지 마세요.\n"
        "- 정보가 없으면 빈 문자열 또는 빈 배열로 두세요.\n"
        "- 반드시 JSON만 출력하세요."
    )

    user_prompt = (
        f"[추출 필드]\n{field_spec}\n\n"
        f"[문서 내용]\n{source_text[:4000]}"
    )

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content.strip())
            return result
        except Exception as e:
            print(f"      [API 에러 {attempt+1}/{max_retries}] {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return {}


def update_field_spec(user_msg: str, added_fields: dict) -> str:
    """user message의 [필드 명세] 섹션에 새 필드 추가"""
    for field, desc in added_fields.items():
        field_line = f"- {field}: {desc}"
        # 이미 있으면 스킵
        if f"- {field}:" in user_msg:
            continue
        # [필드 명세] 섹션 끝에 추가
        # 마지막 "- xxx:" 줄 뒤에 삽입
        lines = user_msg.split("\n")
        insert_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("- ") and ":" in line:
                insert_idx = i + 1
        if insert_idx is not None:
            lines.insert(insert_idx, field_line)
            user_msg = "\n".join(lines)

    return user_msg


def main():
    parser = argparse.ArgumentParser(description="AI Hub 학습 데이터 정제")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 분석만")
    parser.add_argument("--model", type=str, default="gpt-4o-mini")
    parser.add_argument("--input", type=str, default=str(INPUT_PATH))
    parser.add_argument("--output", type=str, default=str(OUTPUT_PATH))
    args = parser.parse_args()

    # 데이터 로드
    samples = []
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    print(f"총 {len(samples)}건 로드\n")

    # 분석
    stats = {
        "meeting_minutes": {"total": 0, "needs_fix": 0, "no_source": 0},
        "report": {"total": 0, "needs_fix": 0, "no_source": 0},
        "proposal": {"total": 0, "needs_fix": 0, "no_source": 0},
    }
    fix_plan = []  # (index, doc_type, missing_fields, has_source)

    for i, sample in enumerate(samples):
        user_msg = sample["messages"][1]["content"]
        doc_type = detect_doc_type(user_msg)
        if doc_type == "unknown":
            continue

        try:
            output = json.loads(sample["messages"][2]["content"])
        except json.JSONDecodeError:
            continue

        stats[doc_type]["total"] += 1
        missing = find_missing_priority_fields(output, doc_type)
        if missing:
            source = get_source_text(output)
            has_source = len(source) > 100
            stats[doc_type]["needs_fix"] += 1
            if not has_source:
                stats[doc_type]["no_source"] += 1
            fix_plan.append((i, doc_type, missing, has_source))

    # 리포트 출력
    print("=== 정제 필요 분석 ===")
    for doc_type, s in stats.items():
        if s["total"] == 0:
            continue
        print(f"\n{doc_type} ({s['total']}건):")
        print(f"  정제 필요: {s['needs_fix']}건 ({s['needs_fix']/s['total']*100:.0f}%)")
        print(f"  source 텍스트 없음: {s['no_source']}건")

    fixable = [(i, dt, mf, hs) for i, dt, mf, hs in fix_plan if hs]
    unfixable = [(i, dt, mf, hs) for i, dt, mf, hs in fix_plan if not hs]

    print(f"\n정제 가능: {len(fixable)}건 (source 있음)")
    print(f"정제 불가: {len(unfixable)}건 (source 없음 → 빈 값 유지)")
    print(f"예상 API 호출: {len(fixable)}회 ({args.model})")

    if args.dry_run:
        # 누락 필드 상세
        print("\n=== 누락 필드 상세 ===")
        for doc_type in ["meeting_minutes", "report", "proposal"]:
            type_fixes = [(i, dt, mf, hs) for i, dt, mf, hs in fix_plan if dt == doc_type]
            if not type_fixes:
                continue
            field_miss_counts = {}
            for _, _, mf, _ in type_fixes:
                for field in mf:
                    field_miss_counts[field] = field_miss_counts.get(field, 0) + 1
            print(f"\n{doc_type}:")
            for field, count in sorted(field_miss_counts.items(), key=lambda x: -x[1]):
                print(f"  {field}: {count}건 누락")
        return

    if not os.getenv("OPENAI_API_KEY"):
        print("\n[오류] OPENAI_API_KEY 환경변수가 필요합니다.")
        sys.exit(1)

    # 정제 실행
    fixed_count = 0
    for idx, (i, doc_type, missing, has_source) in enumerate(fixable):
        sample = samples[i]
        output = json.loads(sample["messages"][2]["content"])
        source = get_source_text(output)

        print(f"  [{idx+1}/{len(fixable)}] #{i} {doc_type} | 누락: {list(missing.keys())}", end=" ", flush=True)

        extracted = call_gpt_extract(source, missing, doc_type, model=args.model)
        if not extracted:
            print("- API 실패")
            continue

        # output에 추출 결과 병합
        filled_fields = {}
        for field, desc in missing.items():
            val = extracted.get(field)
            if val is not None and val != "" and val != [] and val != {}:
                output[field] = val
                filled_fields[field] = desc
            elif field not in output:
                # 필드 키는 추가하되 빈 값
                if "배열" in desc or "목록" in desc:
                    output[field] = []
                else:
                    output[field] = ""

        # assistant message 업데이트
        sample["messages"][2]["content"] = json.dumps(output, ensure_ascii=False)

        # user message에 필드 명세 추가 (없는 필드만)
        sample["messages"][1]["content"] = update_field_spec(
            sample["messages"][1]["content"], missing
        )

        fixed_count += 1
        print(f"- OK (채운 필드: {list(filled_fields.keys())})")

        if (idx + 1) % 20 == 0:
            time.sleep(1)
            print(f"    --- {idx+1}건 처리 완료 ---")

    # 입력 길이 다양화: 25% 샘플의 passage를 짧게 축약
    import random as _random
    rng = _random.Random(42)
    shorten_candidates = [i for i in range(len(samples))]
    rng.shuffle(shorten_candidates)
    shorten_count = int(len(samples) * SHORT_INPUT_RATIO)
    shorten_targets = shorten_candidates[:shorten_count]

    print(f"\n=== 입력 길이 다양화 ({shorten_count}건 축약) ===")
    shortened = 0
    for idx, i in enumerate(shorten_targets):
        sample = samples[i]
        user_msg = sample["messages"][1]["content"]

        # passage 부분 추출 (마지막 섹션)
        sections = user_msg.split("\n\n")
        if len(sections) < 2:
            continue

        # 마지막 섹션이 passage ([회의 내용], [업무 내용], [제안 내용])
        last_section = sections[-1]
        # 이미 짧으면 스킵
        if len(last_section) < 300:
            continue

        # 헤더 분리 (예: "[회의 내용]\n실제내용...")
        header_end = last_section.find("\n")
        if header_end < 0:
            continue
        header = last_section[:header_end]
        passage = last_section[header_end + 1:]

        print(f"  [{idx+1}/{shorten_count}] #{i} ({len(passage)}자 → 축약)", end=" ", flush=True)

        short = shorten_passage(passage, model=args.model)
        if not short:
            print("- 실패")
            continue

        # user message 업데이트
        sections[-1] = f"{header}\n{short}"
        sample["messages"][1]["content"] = "\n\n".join(sections)
        shortened += 1
        print(f"- OK ({len(short)}자)")

        if (idx + 1) % 20 == 0:
            time.sleep(1)

    print(f"  축약 완료: {shortened}건")

    # 저장
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"\n=== 완료 ===")
    print(f"  정제된 샘플: {fixed_count}/{len(fixable)}건")
    print(f"  입력 축약: {shortened}건")
    print(f"  저장: {output_path}")


if __name__ == "__main__":
    main()
