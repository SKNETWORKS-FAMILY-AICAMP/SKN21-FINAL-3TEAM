"""
기존 필터링 데이터의 B급 → A급 보완

B급(always OK, priority 일부 빈값) 샘플의 빈 priority 필드를
content에서 GPT로 생성하여 채움.

사용법:
    python data/training/v2_generate/boost_priority.py --dry-run
    python data/training/v2_generate/boost_priority.py
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

PRIO_FIELDS = {
    "meeting_minutes": {
        "decisions": "결정된 사항 목록 (JSON 배열, 각 항목은 문자열)",
        "action_items": '후속 조치 목록 배열. 각 항목은 {"content": "내용", "assignee": "담당자", "due_date": "기한"} 형태',
    },
    "report": {
        "tasks": '진행 업무 목록 배열. 각 항목은 {"item": "업무명", "assignee": "담당자", "progress": "진행률", "start_date": "시작일", "end_date": "종료일"} 형태',
        "next_plan": "향후 계획 (구체적으로 작성)",
        "issues": "이슈 및 건의사항 (서술형 문자열, 없으면 빈 문자열)",
    },
    "proposal": {
        "schedule": '추진 일정 배열. 각 항목은 {"item": "추진항목", "phase1": "1단계 내용", "phase2": "2단계 내용", "phase3": "3단계 내용", "phase4": "4단계 내용"} 형태',
        "budget": '예산 배열. 각 항목은 {"item": "항목", "quantity": "수량", "unit_price": "단가", "amount": "금액"} 형태',
        "background": "제안 배경 (2~3문장, 서술형 문자열)",
        "current_situation": "현황 분석 (3~5문장, 서술형 문자열)",
    },
}


def detect_type(user_msg):
    if "회의록" in user_msg: return "meeting_minutes"
    elif "보고서" in user_msg or "업무보고" in user_msg: return "report"
    elif "제안서" in user_msg: return "proposal"
    return None


def get_source_text(out):
    """출력 JSON에서 서술형 텍스트를 모아서 source로 사용"""
    parts = []
    for key in ["content", "main_content", "overview", "summary", "purpose",
                 "background", "expected_effect"]:
        val = out.get(key, "")
        # list/dict → str 변환
        if isinstance(val, (list, dict)):
            val = json.dumps(val, ensure_ascii=False)
        if isinstance(val, str) and len(val) > 30:
            parts.append(val)
    return "\n\n".join(parts)


def call_gpt_fill(source_text, missing_fields, doc_type, model="gpt-4o-mini"):
    """GPT로 content에서 빈 priority 필드 생성"""
    from openai import OpenAI
    client = OpenAI()

    doc_names = {"meeting_minutes": "회의록", "report": "보고서", "proposal": "제안서"}
    field_spec = "\n".join(f"- {k}: {v}" for k, v in missing_fields.items())

    system_prompt = (
        f"당신은 {doc_names[doc_type]} 작성 전문가입니다. "
        "주어진 문서 내용을 바탕으로 아래 필드를 작성하여 JSON으로 반환하세요.\n\n"
        "규칙:\n"
        "- 문서에서 언급된 업무/활동/성과/결정사항을 빠짐없이 정리하세요.\n"
        "- 문서에 해당 정보가 없으면 빈 배열로 두세요.\n"
        "- budget(예산)은 문서에 수치가 언급된 경우에만 작성하세요. 없으면 빈 배열로 두세요.\n"
        "- 반드시 JSON만 출력하세요."
    )

    user_prompt = f"[채울 필드]\n{field_spec}\n\n[문서 내용]\n{source_text[:4000]}"

    for attempt in range(3):
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
            return json.loads(response.choices[0].message.content.strip())
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
    return {}


def main():
    parser = argparse.ArgumentParser(description="B급 데이터 priority 필드 보완")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", type=str, default="gpt-4o-mini")
    args = parser.parse_args()

    paths = [
        BASE_DIR / "data" / "training" / "v2_generate" / "ai_hub_filtered.jsonl",
    ]

    total_boosted = 0
    total_skipped = 0

    for path in paths:
        samples = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))

        label = "Synthetic" if "synthetic" in str(path) else "AI Hub"
        b_grade = []

        for i, s in enumerate(samples):
            user_msg = s["messages"][1]["content"]
            try:
                out = json.loads(s["messages"][2]["content"])
            except:
                continue

            dt = detect_type(user_msg)
            if not dt:
                continue

            # B급 찾기: always OK지만 priority에 빈 값 있음
            missing = {}
            for field, desc in PRIO_FIELDS[dt].items():
                val = out.get(field)
                if not val or val == [] or val == "" or val == {}:
                    missing[field] = desc

            if missing:
                source = get_source_text(out)
                if len(source) > 100:  # source가 있어야 채울 수 있음
                    b_grade.append((i, dt, missing, source))

        print(f"\n[{label}] B급 보완 대상: {len(b_grade)}건")

        if args.dry_run:
            # 유형별 통계
            by_dt = {}
            for _, dt, missing, _ in b_grade:
                if dt not in by_dt:
                    by_dt[dt] = {}
                for field in missing:
                    by_dt[dt][field] = by_dt[dt].get(field, 0) + 1
            for dt, fields in by_dt.items():
                print(f"  {dt}: {fields}")
            continue

        if not os.getenv("OPENAI_API_KEY"):
            print("[오류] OPENAI_API_KEY 필요")
            sys.exit(1)

        boosted = 0
        for idx, (i, dt, missing, source) in enumerate(b_grade):
            print(f"  [{idx+1}/{len(b_grade)}] #{i} {dt} | 빈: {list(missing.keys())}", end=" ", flush=True)

            result = call_gpt_fill(source, missing, dt, model=args.model)
            if not result:
                print("- API 실패")
                continue

            out = json.loads(samples[i]["messages"][2]["content"])
            filled = []
            for field in missing:
                val = result.get(field)
                if val and val != [] and val != "" and val != {}:
                    out[field] = val
                    filled.append(field)

            if filled:
                samples[i]["messages"][2]["content"] = json.dumps(out, ensure_ascii=False)
                boosted += 1
                print(f"- OK ({filled})")
            else:
                print(f"- 근거 없음 (빈값 유지)")
                total_skipped += 1

            if (idx + 1) % 20 == 0:
                time.sleep(1)

        # 저장
        with open(path, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

        print(f"  보완 완료: {boosted}건")
        total_boosted += boosted

    print(f"\n=== 총 보완: {total_boosted}건, 스킵(근거 없음): {total_skipped}건 ===")


if __name__ == "__main__":
    main()
