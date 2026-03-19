"""
v4 판단 Agent 학습 데이터 보강

1. system prompt를 JUDGMENT_STREAMING_SYSTEM_PROMPT로 교체
2. assistant 응답을 "자연어 설명 + ```json 코드블록" 형태로 변환
3. 질문 어체 다양화 ("~알려줘", "~뭐야" 등)

사용법:
    python -m ai.finetuning.scripts.augment_v4_question_patterns

출력:
    data/training/v1_judgment_v4/train.jsonl  (전체 학습 데이터)
    data/training/v1_judgment_v4/eval.jsonl   (평가 데이터)
"""
import json
import os
import random
import asyncio
import re
from pathlib import Path

# -- 설정 --
INPUT_PATH = "data/training/v1_judgment_v3/train.jsonl"
OUTPUT_DIR = "data/training/v1_judgment_v4"
AUGMENT_SIZE = 500  # 어체 변환할 샘플 수
OPENAI_MODEL = "gpt-4o-mini"
BATCH_SIZE = 5  # 응답 변환은 개별 처리가 필요해서 작게

# -- 프롬프트 --
REWRITE_QUESTION_PROMPT = """다음 질문들의 **의미는 그대로 유지**하면서 **어체(말투)만** 바꿔주세요.

변환 규칙:
- 질문의 핵심 의미, 주체, 조건은 절대 바꾸지 마세요
- 다음 패턴 중 하나로 자연스럽게 변환하세요:
  1. "~알려줘" / "~알려주세요"
  2. "~뭐야?" / "~뭔가요?"
  3. "~설명해줘" / "~설명해주세요"
  4. "~궁금해" / "~궁금합니다"
  5. "~어떻게 돼?" / "~어떻게 되나요?"
  6. 짧은 구어체: "~규정 좀", "~찾아줘"
- 각 질문마다 랜덤하게 다른 패턴을 사용하세요
- 변환된 질문만 한 줄씩 출력하세요 (번호 없이)

질문들:
{questions}"""

CONVERT_RESPONSE_PROMPT = """다음 JSON 판단 결과를 바탕으로 자연어 설명을 작성하고, 마지막에 JSON 코드블록을 붙여주세요.

형식:
1. 먼저 판단 근거를 자연어로 상세히 설명 (2-4문장)
   - 어떤 규정을 참조했는지
   - 규정의 핵심 내용
   - 최종 판단과 그 이유
2. 그 다음 반드시 ```json 코드블록으로 원본 JSON을 그대로 출력

주의:
- 자연어 설명에 "1부", "2부", "##" 같은 섹션 헤더를 넣지 마세요
- 바로 설명을 시작하세요
- JSON 내용은 절대 수정하지 마세요, 원본 그대로 사용

사용자 질문: {question}

원본 JSON:
{json_response}"""


async def rewrite_questions_batch(client, questions: list[str]) -> list[str]:
    """GPT로 질문 배치를 어체 변환"""
    numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    prompt = REWRITE_QUESTION_PROMPT.format(questions=numbered)

    try:
        resp = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=2000,
        )
        lines = resp.choices[0].message.content.strip().split("\n")
        cleaned = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^\d+[\.\)]\s*", "", line)
            if line:
                cleaned.append(line)
        return cleaned
    except Exception as e:
        print(f"  질문 변환 실패: {e}")
        return []


async def convert_response(client, question: str, json_str: str) -> str:
    """JSON만 있는 응답을 '자연어 + ```json' 형태로 변환"""
    prompt = CONVERT_RESPONSE_PROMPT.format(question=question, json_response=json_str)

    try:
        resp = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )
        content = resp.choices[0].message.content.strip()

        # 검증: ```json이 포함되어 있는지
        if "```json" not in content:
            # 자연어 + 원본 JSON을 수동으로 합침
            content = content.rstrip() + f"\n\n```json\n{json_str}\n```"

        # 검증: JSON 부분이 원본과 동일한지 확인
        json_match = re.search(r"```json\s*\n?(.*?)\n?\s*```", content, re.DOTALL)
        if json_match:
            try:
                generated_json = json.loads(json_match.group(1))
                original_json = json.loads(json_str)
                # result와 confidence가 바뀌지 않았는지 확인
                if generated_json.get("result") != original_json.get("result"):
                    # GPT가 JSON을 수정한 경우 원본으로 교체
                    natural_part = content.split("```json")[0].strip()
                    content = f"{natural_part}\n\n```json\n{json_str}\n```"
            except json.JSONDecodeError:
                # JSON 파싱 실패시 원본으로 교체
                natural_part = content.split("```json")[0].strip()
                content = f"{natural_part}\n\n```json\n{json_str}\n```"

        return content
    except Exception as e:
        # 실패시 기본 형태로 생성
        try:
            j = json.loads(json_str)
            reasoning = j.get("reasoning", "판단 근거를 확인하세요.")
            return f"{reasoning}\n\n```json\n{json_str}\n```"
        except:
            return f"판단 결과입니다.\n\n```json\n{json_str}\n```"


def extract_question(sample):
    user_content = sample["messages"][-2]["content"]
    if "## 사용자 질문" in user_content:
        return user_content.split("## 사용자 질문")[-1].strip()
    return user_content.split("\n")[-1].strip()


async def main():
    from openai import AsyncOpenAI
    from dotenv import load_dotenv
    load_dotenv()

    print("=" * 60)
    print(" v4 판단 데이터 보강")
    print(" - system prompt: STREAMING 버전으로 교체")
    print(" - assistant: 자연어 + json 코드블록 형태로 변환")
    print(" - 질문 어체 다양화 (500건)")
    print("=" * 60)

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # 서비스 프롬프트 로드
    from ai.llm.prompts import JUDGMENT_STREAMING_SYSTEM_PROMPT
    NEW_SYSTEM_PROMPT = JUDGMENT_STREAMING_SYSTEM_PROMPT

    # 1. 기존 데이터 로드
    print(f"\n[1/6] 기존 데이터 로드: {INPUT_PATH}")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        all_data = [json.loads(line) for line in f]
    print(f"  전체: {len(all_data)}건")

    # 2. 전체 데이터의 system prompt 교체 + assistant 응답 변환
    print(f"\n[2/6] 전체 데이터 응답 형식 변환 (자연어 + json)...")
    print(f"  system prompt: {len(all_data[0]['messages'][0]['content'])}자 -> {len(NEW_SYSTEM_PROMPT)}자")

    converted_data = [None] * len(all_data)
    PARALLEL = 20  # 동시 요청 수

    async def convert_one(idx, sample):
        question = extract_question(sample)
        original_assistant = sample["messages"][-1]["content"]
        new_assistant = await convert_response(client, question, original_assistant)
        converted_data[idx] = {
            "messages": [
                {"role": "system", "content": NEW_SYSTEM_PROMPT},
                sample["messages"][-2],
                {"role": "assistant", "content": new_assistant},
            ]
        }

    import asyncio as _aio
    for batch_start in range(0, len(all_data), PARALLEL):
        batch_end = min(batch_start + PARALLEL, len(all_data))
        tasks = [convert_one(i, all_data[i]) for i in range(batch_start, batch_end)]
        await _aio.gather(*tasks)
        print(f"  진행: {batch_end}/{len(all_data)} ({batch_end*100//len(all_data)}%)")

    # 3. 어체 변환용 샘플 선택
    print(f"\n[3/6] 어체 변환 대상 선택: {AUGMENT_SIZE}건")
    random.seed(42)
    candidates = []
    for d in converted_data:
        q = extract_question(d)
        skip_patterns = ["알려", "뭐야", "뭔가", "설명해", "궁금"]
        if not any(p in q for p in skip_patterns):
            candidates.append(d)
    samples = random.sample(candidates, min(AUGMENT_SIZE, len(candidates)))
    print(f"  후보: {len(candidates)}건 -> 선택: {len(samples)}건")

    # 4. GPT로 어체 변환
    print(f"\n[4/6] GPT 어체 변환...")
    augmented = []
    batch_size = 20
    for i in range(0, len(samples), batch_size):
        batch = samples[i:i + batch_size]
        questions = [extract_question(s) for s in batch]
        rewritten = await rewrite_questions_batch(client, questions)

        count = min(len(rewritten), len(batch))
        for j in range(count):
            sample = batch[j]
            new_question = rewritten[j]
            user_content = sample["messages"][-2]["content"]

            if "## 사용자 질문" in user_content:
                regulation_part = user_content.split("## 사용자 질문")[0]
                new_user_content = f"{regulation_part}## 사용자 질문\n{new_question}"
            else:
                lines = user_content.split("\n")
                lines[-1] = new_question
                new_user_content = "\n".join(lines)

            new_sample = {
                "messages": [
                    sample["messages"][0],  # system prompt (이미 교체됨)
                    {"role": "user", "content": new_user_content},
                    sample["messages"][-1],  # assistant (이미 변환됨)
                ]
            }
            augmented.append(new_sample)

        done = min(i + batch_size, len(samples))
        print(f"  진행: {done}/{len(samples)} ({done*100//len(samples)}%)")

    print(f"  어체 변환: {len(augmented)}건")

    # 5. 저장
    print(f"\n[5/6] 저장...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    merged_path = f"{OUTPUT_DIR}/train.jsonl"
    merged = converted_data + augmented
    random.shuffle(merged)
    with open(merged_path, "w", encoding="utf-8") as f:
        for item in merged:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  train: {merged_path} ({len(merged)}건)")

    # eval도 변환
    eval_src = INPUT_PATH.replace("train.jsonl", "eval.jsonl")
    eval_dst = f"{OUTPUT_DIR}/eval.jsonl"
    if os.path.exists(eval_src):
        print(f"  eval 변환 중 (병렬)...")
        with open(eval_src, "r", encoding="utf-8") as f:
            eval_data = [json.loads(line) for line in f]
        eval_converted = [None] * len(eval_data)

        async def convert_eval(idx, sample):
            question = extract_question(sample)
            original_assistant = sample["messages"][-1]["content"]
            new_assistant = await convert_response(client, question, original_assistant)
            eval_converted[idx] = {
                "messages": [
                    {"role": "system", "content": NEW_SYSTEM_PROMPT},
                    sample["messages"][-2],
                    {"role": "assistant", "content": new_assistant},
                ]
            }

        for batch_start in range(0, len(eval_data), PARALLEL):
            batch_end = min(batch_start + PARALLEL, len(eval_data))
            tasks = [convert_eval(i, eval_data[i]) for i in range(batch_start, batch_end)]
            await _aio.gather(*tasks)
            print(f"    eval 진행: {batch_end}/{len(eval_data)}")
        with open(eval_dst, "w", encoding="utf-8") as f:
            for item in eval_converted:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"  eval: {eval_dst} ({len(eval_converted)}건)")

    # 6. 패턴 분석
    print(f"\n[6/6] 패턴 분석")
    patterns = {"알려": 0, "뭐야": 0, "뭔가": 0, "설명": 0, "궁금": 0, "어떻게": 0, "가능": 0, "되나": 0, "있나": 0, "기타": 0}
    for item in merged:
        q = extract_question(item)
        matched = False
        for k in patterns:
            if k != "기타" and k in q:
                patterns[k] += 1
                matched = True
                break
        if not matched:
            patterns["기타"] += 1

    print(f"\n  {'패턴':<10} {'건수':>6}  {'비율':>6}")
    print(f"  {'-'*26}")
    for k, v in sorted(patterns.items(), key=lambda x: -x[1]):
        pct = v * 100 / len(merged)
        print(f"  {k:<10} {v:>6}건  {pct:>5.1f}%")

    print(f"\n  합계: {len(merged)}건 (기존 {len(converted_data)} + 보강 {len(augmented)})")

    # 샘플 출력
    print(f"\n-- 변환 샘플 --")
    sample = merged[0]
    q = extract_question(sample)
    a = sample["messages"][-1]["content"]
    print(f"질문: {q[:100]}")
    print(f"응답 (앞 200자): {a[:200]}")

    print(f"\n완료!")


if __name__ == "__main__":
    asyncio.run(main())
