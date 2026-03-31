"""
v2_generate 학습 데이터 프롬프트 변환: 고정 템플릿 → 동적 필드 명세 방식

기존: 템플릿별 고정 system prompt ("당신은 회의록 작성 전문가입니다...")
변경: 범용 system prompt + user prompt에 [필드 명세] 포함

assistant 응답(JSON)은 그대로 유지 → GPT-4o 재호출 불필요

사용법:
    python ai/finetuning/scripts/convert_to_dynamic_fields.py
    python ai/finetuning/scripts/convert_to_dynamic_fields.py --dry-run
"""

import argparse
import json
import sys
import io
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from ai.llm.prompts import DOC_GENERATE_SLLM_PROMPT

INPUT_PATH = BASE_DIR / "data" / "training" / "v2_generate" / "aihub_generate.jsonl"
OUTPUT_PATH = BASE_DIR / "data" / "training" / "v2_generate" / "aihub_generate.jsonl"
BACKUP_PATH = BASE_DIR / "data" / "training" / "v2_generate" / "aihub_generate_fixed_prompt_backup.jsonl"

# ── sLLM 시스템 프롬프트 (ai/llm/prompts.py에서 import) ──
DYNAMIC_SYSTEM_PROMPT = DOC_GENERATE_SLLM_PROMPT

# ── 템플릿별 필드 명세 (user prompt에 삽입) ──

FIELD_SPECS = {
    "meeting_minutes": {
        "doc_type_name": "회의록",
        "input_label": "회의 내용",
        "fields": [
            ("title", "회의 주제를 반영한 구체적인 제목"),
            ("date", "회의 날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)"),
            ("attendees", "참석자 이름 배열 (없으면 빈 배열)"),
            ("summary", "회의에서 논의된 주요 내용을 파트별로 3~5문장으로 요약"),
            ("decisions", "결정된 사항 목록 (배열, 없으면 빈 배열)"),
            ("action_items", '후속 조치 목록 배열. 각 항목은 {"content", "assignee", "due_date"} 형태'),
            ("risks", '리스크 목록 배열. 각 항목은 {"description", "level"(상/중/하), "regulation"} 형태'),
        ],
    },
    "report": {
        "doc_type_name": "업무보고서",
        "input_label": "업무 내용",
        "fields": [
            ("title", "업무 내용을 반영한 구체적인 보고서 제목"),
            ("author", "작성자 이름 (없으면 빈 문자열)"),
            ("date", "작성 날짜 (YYYY-MM-DD 형식)"),
            ("department", "부서명 (없으면 빈 문자열)"),
            ("position", "직급 (없으면 빈 문자열)"),
            ("report_to", "보고 대상 (없으면 빈 문자열)"),
            ("report_type", "'일일', '주간', '월간', '수시' 중 하나"),
            ("overview", "업무 내용을 요약한 보고 개요 (3~5문장)"),
            ("main_content", "업무 세부 내용을 항목별로 구체적으로 작성"),
            ("tasks", '진행 업무 목록 배열. 각 항목은 {"item", "assignee", "progress", "start_date", "end_date"} 형태'),
            ("issues", "이슈 및 건의사항 (없으면 빈 문자열)"),
            ("next_plan", "향후 계획 (구체적으로 작성)"),
        ],
    },
    "proposal": {
        "doc_type_name": "제안서",
        "input_label": "제안 내용",
        "fields": [
            ("title", "제안 내용을 반영한 구체적인 제안서 제목"),
            ("submit_date", "제출 날짜 (YYYY-MM-DD, 없으면 오늘 날짜)"),
            ("submit_to", "제출처 (없으면 빈 문자열)"),
            ("company", "제안사 이름 (없으면 빈 문자열)"),
            ("manager", "담당자 이름 (없으면 빈 문자열)"),
            ("contact", "연락처 (없으면 빈 문자열)"),
            ("proposal_name", "제안명 (title과 유사하게)"),
            ("background", "제안 배경 (2~3문장)"),
            ("proposal_date", "제안 날짜 (YYYY-MM-DD)"),
            ("period", "제안 기간 (예: 2026년 3월 ~ 6월)"),
            ("proposer", "제안사명"),
            ("manager_contact", "담당자 / 연락처"),
            ("purpose", "제안 목적 및 필요성 (3~5문장)"),
            ("analysis", "현황 분석 (3~5문장)"),
            ("content", "제안 내용을 항목별로 구체적으로 작성"),
            ("schedule", '추진 일정 배열. 각 항목은 {"item", "phase1", "phase2", "phase3", "phase4"} 형태'),
            ("budget", '예산 배열. 각 항목은 {"item", "quantity", "unit_price", "amount"} 형태'),
            ("budget_total", "합계 금액"),
            ("expected_effect", "기대 효과 (3~5문장)"),
        ],
    },
}


def detect_template(system_content: str, user_content: str) -> str:
    """system prompt에서 템플릿 유형 감지 (원문에 '보고서' 등 포함 시 오탐 방지)"""
    # system prompt 기반 (가장 정확)
    if "회의록 작성 전문가" in system_content:
        return "meeting_minutes"
    elif "업무보고서 작성 전문가" in system_content:
        return "report"
    elif "제안서 작성 전문가" in system_content:
        return "proposal"
    # fallback: user prompt 첫 줄 기반
    first_line = user_content.split("\n")[0]
    if "회의록" in first_line:
        return "meeting_minutes"
    elif "보고서" in first_line:
        return "report"
    elif "제안서" in first_line:
        return "proposal"
    return "unknown"


def extract_passage(user_content: str) -> str:
    """기존 user prompt에서 원문(passage) 추출"""
    # 패턴: [회의 내용]\n{passage}\n\n출력 JSON 키:
    for label in ["[회의 내용]\n", "[업무 내용]\n", "[제안 내용]\n"]:
        if label in user_content:
            after = user_content.split(label, 1)[1]
            # "출력 JSON 키:" 이전까지가 passage
            if "\n\n출력 JSON 키:" in after:
                return after.split("\n\n출력 JSON 키:")[0].strip()
            return after.strip()
    return user_content


def build_dynamic_user_prompt(template: str, passage: str) -> str:
    """동적 필드 명세 방식의 user prompt 생성"""
    spec = FIELD_SPECS[template]
    doc_type = spec["doc_type_name"]
    input_label = spec["input_label"]

    # 필드 명세 문자열
    field_lines = []
    for field_name, field_desc in spec["fields"]:
        field_lines.append(f"- {field_name}: {field_desc}")
    field_spec_str = "\n".join(field_lines)

    return (
        f"다음 내용을 바탕으로 문서를 JSON 형식으로 작성해주세요.\n\n"
        f"[문서 유형] {doc_type}\n\n"
        f"[필드 명세]\n{field_spec_str}\n\n"
        f"[{input_label}]\n{passage}"
    )


def convert_sample(sample: dict) -> dict:
    """단일 샘플을 동적 필드 방식으로 변환"""
    messages = sample["messages"]
    system_content = messages[0]["content"]
    user_content = messages[1]["content"]
    assistant_content = messages[2]["content"]  # JSON 그대로 유지

    template = detect_template(system_content, user_content)
    if template == "unknown":
        return None

    passage = extract_passage(user_content)
    new_user = build_dynamic_user_prompt(template, passage)

    return {
        "messages": [
            {"role": "system", "content": DYNAMIC_SYSTEM_PROMPT},
            {"role": "user", "content": new_user},
            {"role": "assistant", "content": assistant_content},
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="v2_generate 프롬프트를 동적 필드 방식으로 변환")
    parser.add_argument("--input", type=str, default=str(INPUT_PATH))
    parser.add_argument("--output", type=str, default=str(OUTPUT_PATH))
    parser.add_argument("--dry-run", action="store_true", help="변환 미리보기만")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    # 원본 로드
    samples = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    print(f"원본 로드: {len(samples)}건")

    # 변환
    converted = []
    failed = 0
    template_counts = {}

    for i, sample in enumerate(samples):
        result = convert_sample(sample)
        if result is None:
            failed += 1
            continue
        converted.append(result)

        # 템플릿 카운트
        user = result["messages"][1]["content"]
        for tmpl_name, spec in FIELD_SPECS.items():
            if spec["doc_type_name"] in user:
                template_counts[tmpl_name] = template_counts.get(tmpl_name, 0) + 1
                break

    print(f"변환 성공: {len(converted)}건, 실패: {failed}건")
    print(f"템플릿 분포: {template_counts}")

    if args.dry_run:
        # 샘플 출력
        for tmpl in ["meeting_minutes", "report", "proposal"]:
            for item in converted:
                if FIELD_SPECS[tmpl]["doc_type_name"] in item["messages"][1]["content"]:
                    print(f"\n{'='*60}")
                    print(f"  [{tmpl}] 변환 샘플")
                    print(f"{'='*60}")
                    print(f"\n[SYSTEM]\n{item['messages'][0]['content'][:200]}...")
                    print(f"\n[USER]\n{item['messages'][1]['content'][:500]}...")
                    print(f"\n[ASSISTANT]\n{item['messages'][2]['content'][:200]}...")
                    break
        return

    # 백업
    if input_path == output_path:
        backup_path = Path(str(BACKUP_PATH))
        import shutil
        shutil.copy2(input_path, backup_path)
        print(f"백업 저장: {backup_path}")

    # 저장
    with open(output_path, "w", encoding="utf-8") as f:
        for item in converted:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"저장 완료: {output_path} ({len(converted)}건)")


if __name__ == "__main__":
    main()
