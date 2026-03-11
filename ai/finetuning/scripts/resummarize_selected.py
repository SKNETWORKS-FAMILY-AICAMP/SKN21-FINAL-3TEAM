"""
선별된 300건의 요약을 새 프롬프트로 재생성

원문은 유지하고 Step B(요약)만 새 DOC_SUMMARY_SLLM_PROMPT로 다시 생성합니다.

사용법:
    python ai/finetuning/scripts/resummarize_selected.py
    python ai/finetuning/scripts/resummarize_selected.py --dry-run
"""

import argparse
import json
import io
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env", override=True)

from ai.llm.prompts import DOC_SUMMARY_SLLM_PROMPT

DATA_DIR = BASE_DIR / "data" / "training" / "v2_summary"
INPUT_FILE = DATA_DIR / "synthetic_selected.jsonl"
OUTPUT_FILE = DATA_DIR / "synthetic_selected_v2.jsonl"


def call_openai(system_prompt, user_prompt, model="gpt-4o", temperature=0.7, max_tokens=1024, max_retries=3):
    from openai import OpenAI
    client = OpenAI()
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print("    [API 에러 %d/%d] %s" % (attempt + 1, max_retries, e))
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return None


def validate_summary(summary):
    errors = []
    if "태그:" not in summary:
        errors.append("'태그:' 없음")
    if "요약:" not in summary:
        errors.append("'요약:' 없음")
    if "태그:" in summary:
        tag_line = summary.split("태그:")[1].split("\n")[0].strip()
        tags = [t.strip().lstrip("#").strip() for t in tag_line.split("#") if t.strip()]
        if len(tags) < 3 or len(tags) > 7:
            errors.append("태그 개수 부적합: %d개" % len(tags))
    if "요약:" in summary:
        summary_text = summary.split("요약:", 1)[1].strip()
        if len(summary_text) < 30:
            errors.append("요약 너무 짧음: %d자" % len(summary_text))
    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description="선별 300건 요약 재생성")
    parser.add_argument("--input", type=str, default=str(INPUT_FILE))
    parser.add_argument("--output", type=str, default=str(OUTPUT_FILE))
    parser.add_argument("--model", type=str, default="gpt-4o")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    with open(input_path, encoding="utf-8") as f:
        samples = [json.loads(line.strip()) for line in f if line.strip()]

    print("=" * 60)
    print("  선별 300건 요약 재생성 (새 프롬프트)")
    print("=" * 60)
    print("  입력: %s (%d건)" % (args.input, len(samples)))
    print("  새 프롬프트: DOC_SUMMARY_SLLM_PROMPT (2~5문장, 구체적 태그)")

    if args.dry_run:
        print("\n[DRY RUN] API 호출 안 함")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for i, sample in enumerate(samples):
            user_content = sample["messages"][1]["content"]
            print("  [%d/%d]" % (i + 1, len(samples)), end=" ", flush=True)

            # Step B: 새 프롬프트로 요약 재생성
            new_summary = call_openai(
                DOC_SUMMARY_SLLM_PROMPT,
                user_content,
                model=args.model,
                temperature=0.7,
                max_tokens=1024,
            )

            if not new_summary:
                print("- 요약 생성 실패")
                failed += 1
                continue

            is_valid, errors = validate_summary(new_summary)
            if not is_valid:
                print("- 검증 실패: %s" % errors)
                failed += 1
                continue

            new_sample = {
                "messages": [
                    {"role": "system", "content": DOC_SUMMARY_SLLM_PROMPT},
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": new_summary},
                ]
            }

            f.write(json.dumps(new_sample, ensure_ascii=False) + "\n")
            f.flush()
            success += 1
            print("- OK")

            if (i + 1) % 10 == 0:
                time.sleep(0.5)
                print("    --- %d건 완료 (성공: %d, 실패: %d) ---" % (i + 1, success, failed))

    print("\n  결과: 성공 %d, 실패 %d" % (success, failed))
    print("  저장: %s" % args.output)


if __name__ == "__main__":
    main()
