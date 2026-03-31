"""
부족분 추가 생성 스크립트

filter_and_select.py 실행 후, 부족한 길이/유형 조합만 추가 생성.
min_length 검증으로 GPT가 짧게 쓰는 문제 방지.

사용법:
    python data/training/v2_generate/generate_supplement.py --dry-run
    python data/training/v2_generate/generate_supplement.py
"""

import argparse
import io
import json
import os
import random
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=True)
except ImportError:
    pass

OUTPUT_PATH = BASE_DIR / "data" / "training" / "v2_generate" / "synthetic_supplement.jsonl"

# 추가 생성 계획
GEN_PLAN = [
    # (template, length_range, count, min_chars)
    # 부족분 154건 → report(tasks 부족)와 proposal(budget 부족)에 집중
    ("report", "500~1500", 80, 500),      # tasks 채움률 61% 보강
    ("proposal", "500~1500", 80, 500),    # budget 채움률 42% 보강
]

# synthesize_generate.py에서 필요한 것들 import
from ai.finetuning.scripts.synthesize_generate import (
    FIELD_POOLS, DYNAMIC_SYSTEM_PROMPT, SCENARIO_SYSTEM_PROMPTS,
    INDUSTRIES, MEETING_TOPICS, REPORT_TOPICS, PROPOSAL_TOPICS,
    select_random_fields, build_dynamic_user_prompt,
    call_openai, validate_json_output, OMITTABLE_FIELDS,
)


def generate_scenario_with_min_length(
    template, industry, topic, length_range, min_chars,
    model="gpt-4o", max_attempts=3
):
    """시나리오 생성 + min_length 검증. 미달 시 재생성."""
    doc_type_map = {
        "meeting_minutes": "회의",
        "report": "업무 보고",
        "proposal": "제안",
    }
    doc_type = doc_type_map[template]

    if length_range.startswith("1500"):
        style = f"구체적인 수치, 한국식 이름, 날짜, 세부 항목을 포함하여 매우 상세하게 작성하세요. 반드시 {min_chars}자 이상으로 작성하세요. 절대 짧게 쓰지 마세요."
        tokens = 4096
    elif length_range.startswith("800"):
        style = f"구체적인 수치, 한국식 이름, 날짜를 포함하여 상세하게 작성하세요. 반드시 {min_chars}자 이상으로 작성하세요."
        tokens = 4096
    else:
        style = f"핵심 내용을 간결하게 서술형으로 작성하세요. 반드시 {min_chars}자 이상으로 작성하세요."
        tokens = 2048

    user_prompt = (
        f"다음 조건으로 {industry} 업종의 {doc_type} 관련 원문 내용을 생성해주세요.\n\n"
        f"주제: {topic}\n"
        f"길이: {length_range}자\n"
        f"{style}"
    )

    for attempt in range(max_attempts):
        passage = call_openai(
            SCENARIO_SYSTEM_PROMPTS[template],
            user_prompt,
            model=model,
            temperature=0.9,
            max_tokens=tokens,
        )
        if not passage:
            continue
        if len(passage) >= min_chars:
            return passage
        print(f"      길이 미달 ({len(passage)}자 < {min_chars}자), 재생성 {attempt+1}/{max_attempts}")

    # max_attempts 초과 — 마지막 결과라도 반환 (min_chars의 70% 이상이면)
    if passage and len(passage) >= min_chars * 0.7:
        return passage
    return None


def main():
    parser = argparse.ArgumentParser(description="부족분 추가 생성")
    parser.add_argument("--model", type=str, default="gpt-4o")
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--empty-field-ratio", type=float, default=0.3)
    args = parser.parse_args()

    total_plan = sum(count for _, _, count, _ in GEN_PLAN)
    print(f"=== 부족분 추가 생성 ({total_plan}건) ===\n")

    for tmpl, lr, count, min_c in GEN_PLAN:
        print(f"  {tmpl} {lr}: {count}건 (min {min_c}자)")

    if args.dry_run:
        est_cost = total_plan * 2 * 0.025
        print(f"\n예상 API 호출: {total_plan * 2}회")
        print(f"예상 비용: ~${est_cost:.1f}")
        return

    if not os.getenv("OPENAI_API_KEY"):
        print("\n[오류] OPENAI_API_KEY 필요")
        sys.exit(1)

    rng = random.Random(args.seed)
    topic_map = {
        "meeting_minutes": MEETING_TOPICS,
        "report": REPORT_TOPICS,
        "proposal": PROPOSAL_TOPICS,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    success = 0
    failed = 0

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for tmpl, length_range, count, min_chars in GEN_PLAN:
            print(f"\n  === {tmpl} {length_range} ({count}건) ===")

            for i in range(count):
                industry = rng.choice(INDUSTRIES)
                topic = rng.choice(topic_map[tmpl])
                selected_fields = select_random_fields(tmpl, rng)
                field_names = [name for name, _ in selected_fields]

                print(f"    [{i+1}/{count}] {industry}/{topic} ({len(selected_fields)}필드)", end=" ", flush=True)

                # Step A: 시나리오 (min_length 검증 포함)
                passage = generate_scenario_with_min_length(
                    tmpl, industry, topic, length_range, min_chars, model=args.model
                )
                if not passage:
                    print("- 시나리오 실패")
                    failed += 1
                    continue

                # sparse 처리 (30%)
                is_sparse = rng.random() < args.empty_field_ratio
                omit_fields = []
                if is_sparse:
                    omittable = [fn for fn in field_names if fn in OMITTABLE_FIELDS.get(tmpl, [])]
                    if omittable:
                        k = rng.randint(1, min(3, len(omittable)))
                        omit_fields = rng.sample(omittable, k)
                        passage += (
                            f"\n\n[참고] 다음 정보는 원문에 포함되어 있지 않습니다: "
                            f"{', '.join(omit_fields)}. "
                            f"해당 필드는 빈 문자열 또는 빈 배열로 두세요."
                        )

                # Step B: JSON 응답
                tokens = 4096 if len(passage) > 1200 else 2048
                user_prompt = build_dynamic_user_prompt(tmpl, passage.split("\n\n[참고]")[0] if is_sparse else passage, selected_fields)
                json_output = call_openai(
                    DYNAMIC_SYSTEM_PROMPT, user_prompt,
                    model=args.model, temperature=0.7,
                    max_tokens=tokens, json_mode=True,
                )
                if not json_output:
                    print("- JSON 실패")
                    failed += 1
                    continue

                # 검증
                is_valid, parsed, errors = validate_json_output(json_output, selected_fields)
                if not is_valid and parsed:
                    for k in list(parsed.keys()):
                        if k not in field_names:
                            del parsed[k]
                    json_output = json.dumps(parsed, ensure_ascii=False)
                    is_valid, parsed, errors = validate_json_output(json_output, selected_fields)

                if not is_valid:
                    print(f"- 검증 실패: {errors}")
                    failed += 1
                    continue

                # 서술형 필드 str 변환 (GPT가 list/dict로 반환하는 경우 방지)
                for str_key in ["content", "main_content", "overview", "summary",
                                "expected_effect", "purpose", "background", "next_plan",
                                "issues", "notes"]:
                    sv = parsed.get(str_key)
                    if sv is not None and not isinstance(sv, str):
                        if isinstance(sv, list):
                            parts = []
                            for item in sv:
                                if isinstance(item, str):
                                    parts.append(item)
                                elif isinstance(item, dict):
                                    parts.append(" / ".join(str(v) for v in item.values() if v))
                                else:
                                    parts.append(str(item))
                            parsed[str_key] = "\n".join(p for p in parts if p)
                        elif isinstance(sv, dict):
                            parsed[str_key] = "\n".join(f"{k}: {v}" for k, v in sv.items() if v)
                        else:
                            parsed[str_key] = str(sv)
                        json_output = json.dumps(parsed, ensure_ascii=False)

                # sparse 후처리
                if is_sparse and parsed and omit_fields:
                    for field in omit_fields:
                        val = parsed.get(field)
                        if val not in ("", [], None, {}):
                            parsed[field] = [] if isinstance(val, list) else ""
                    json_output = json.dumps(parsed, ensure_ascii=False)

                # 2차 boost: 빈 priority 필드를 content에서 GPT로 채움 (sparse 제외)
                if not is_sparse and parsed:
                    _PRIO = {
                        "meeting_minutes": {
                            "decisions": "결정된 사항 목록 (JSON 배열, 각 항목은 문자열)",
                            "action_items": '후속 조치 목록 배열. 각 항목은 {"content": "내용", "assignee": "담당자", "due_date": "기한"} 형태',
                        },
                        "report": {
                            "tasks": '진행 업무 목록 배열. 각 항목은 {"item": "업무명", "assignee": "담당자", "progress": "진행률"} 형태',
                            "next_plan": "향후 계획 (구체적으로 작성)",
                            "issues": "이슈 및 건의사항 (서술형 문자열)",
                        },
                        "proposal": {
                            "schedule": '추진 일정 배열. 각 항목은 {"item": "추진항목", "phase1": "1단계 내용", "phase2": "2단계 내용", "phase3": "3단계 내용", "phase4": "4단계 내용"} 형태',
                            "budget": '예산 배열. 각 항목은 {"item": "항목", "quantity": "수량", "unit_price": "단가", "amount": "금액"} 형태',
                            "background": "제안 배경 (2~3문장, 서술형 문자열)",
                            "current_situation": "현황 분석 (3~5문장, 서술형 문자열)",
                        },
                    }
                    missing_prio = {}
                    for pk, pdesc in _PRIO.get(tmpl, {}).items():
                        if pk in field_names:
                            pv = parsed.get(pk)
                            if not pv or pv == [] or pv == "":
                                missing_prio[pk] = pdesc

                    if missing_prio:
                        source = parsed.get("content", "") or parsed.get("main_content", "") or parsed.get("overview", "")
                        if source and len(str(source)) > 50:
                            doc_names = {"meeting_minutes": "회의록", "report": "보고서", "proposal": "제안서"}
                            boost_spec = "\n".join(f"- {k}: {v}" for k, v in missing_prio.items())
                            boost_sys = (
                                f"당신은 {doc_names.get(tmpl, '문서')} 작성 전문가입니다. "
                                "주어진 문서 내용을 바탕으로 아래 필드를 작성하여 JSON으로 반환하세요.\n\n"
                                "규칙:\n"
                                "- 문서에서 언급된 업무/활동/성과/결정사항을 빠짐없이 정리하세요.\n"
                                "- 문서에 해당 정보가 없으면 빈 배열로 두세요.\n"
                                "- budget은 문서에 수치가 있을 때만 작성하세요.\n"
                                "- JSON만 출력하세요."
                            )
                            boost_result = call_openai(
                                boost_sys, f"[채울 필드]\n{boost_spec}\n\n[문서 내용]\n{str(source)[:3000]}",
                                model="gpt-4o-mini", temperature=0.3, max_tokens=1500, json_mode=True,
                            )
                            if boost_result:
                                try:
                                    boost_parsed = json.loads(boost_result)
                                    boosted = []
                                    for pk in missing_prio:
                                        bv = boost_parsed.get(pk)
                                        if bv and bv != [] and bv != "":
                                            parsed[pk] = bv
                                            boosted.append(pk)
                                    if boosted:
                                        json_output = json.dumps(parsed, ensure_ascii=False)
                                except Exception:
                                    pass

                # 저장
                clean_passage = passage.split("\n\n[참고]")[0] if is_sparse else passage
                save_prompt = build_dynamic_user_prompt(tmpl, clean_passage, selected_fields)
                sample = {
                    "messages": [
                        {"role": "system", "content": DYNAMIC_SYSTEM_PROMPT},
                        {"role": "user", "content": save_prompt},
                        {"role": "assistant", "content": json_output},
                    ]
                }
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                success += 1

                sparse_tag = " [sparse]" if is_sparse and omit_fields else ""
                print(f"- OK {len(passage)}자 {len(parsed)}키{sparse_tag}")

                if (success + failed) % 20 == 0:
                    time.sleep(1)

    print(f"\n=== 완료: 성공 {success}, 실패 {failed} ===")
    print(f"저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
