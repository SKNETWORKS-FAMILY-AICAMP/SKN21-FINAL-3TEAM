"""
v2_qa 합성 데이터 생성 스크립트

GPT-4o를 활용하여 완전 합성 QA 데이터 300개를 생성합니다.

문서 유형별 배분:
  업무보고서 75, 회의록 75, 제안서/사업계획 60, 규정/지침 45, 뉴스/보도자료 45

파이프라인:
  Step A: GPT-4o -> 문서 원문 + QA 쌍 동시 생성
  Step B: 후처리 -> 청크 분할, 프로덕션 형식 변환

사용법:
    python ai/finetuning/scripts/synthesize_qa.py --dry-run
    python ai/finetuning/scripts/synthesize_qa.py
    python ai/finetuning/scripts/synthesize_qa.py --count 50
    python ai/finetuning/scripts/synthesize_qa.py --append
"""

import argparse
import json
import io
import os
import random
import re
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env", override=True)

from ai.llm.prompts import DOC_QA_SLLM_PROMPT

OUTPUT_DIR = BASE_DIR / "data" / "training" / "v2_qa"

# ── sLLM 시스템 프롬프트 (ai/llm/prompts.py에서 import) ──
SYSTEM_PROMPT = DOC_QA_SLLM_PROMPT

# not-found 응답 문구 (프롬프트 기준 통일)
NOT_FOUND_ANSWER = "제공된 문서에서 해당 내용을 찾을 수 없습니다."

# ── QA 생성용 GPT-4o 프롬프트 ──

QA_GENERATION_SYSTEM = (
    "당신은 기업 문서 기반 QA 데이터 생성 전문가입니다.\n"
    "주어진 조건에 맞는 업무 문서를 생성하고, 그에 대한 자연스러운 질문-답변을 만드세요.\n\n"
    "반드시 아래 JSON 형식으로만 출력하세요:\n"
    "{\n"
    '  "passage": "문서 원문 (800~2000자)",\n'
    '  "source_title": "문서 제목",\n'
    '  "question": "문서에 대한 자연스러운 질문",\n'
    '  "answer": "문서 내용에 근거한 답변",\n'
    '  "citation_text": "답변의 근거가 되는 원문 인용 (1~2문장)"\n'
    "}\n\n"
    "규칙:\n"
    "- 질문은 실제 업무에서 할 법한 자연스러운 한국어로 작성하세요.\n"
    "- 답변은 반드시 문서 내용에 근거해야 합니다.\n"
    "- citation_text는 passage에 실제로 포함된 문장이어야 합니다.\n"
    "- 구체적인 이름, 수치, 날짜를 포함하여 사실적으로 작성하세요.\n"
    "- JSON만 출력하세요."
)

# ── 문서 유형별 목표 ──

DOC_TYPE_TARGETS = {
    "업무보고서": 75,
    "회의록": 75,
    "제안서/사업계획": 60,
    "규정/지침": 45,
    "뉴스/보도자료": 45,
}

# ── 업종 풀 ──

INDUSTRIES = [
    "IT/소프트웨어", "제조업", "금융/은행", "유통/물류", "의료/헬스케어",
    "건설/부동산", "교육", "미디어/광고", "에너지/환경", "공공/정부",
    "컨설팅", "식품/외식", "자동차", "통신", "바이오/제약",
]

# ── 문서 유형별 질문 스타일 힌트 ──

QUESTION_HINTS = {
    "업무보고서": "숫자/통계/진행률/담당자/일정에 대한 질문",
    "회의록": "결정사항/행동항목/참석자/일정에 대한 질문",
    "제안서/사업계획": "예산/일정/목적/기대효과에 대한 질문",
    "규정/지침": "조건/예외/적용범위/벌칙에 대한 질문",
    "뉴스/보도자료": "사실 확인/인물/기관/수치에 대한 질문",
}

# 청크 크기 (convert_aihub_qa.py와 동일)
CHUNK_SIZE = 250

# ── 부정 예시 비율 ──
NEGATIVE_RATIO = 0.12  # 10~15%는 "답을 찾을 수 없음" 예시


def call_openai(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4o",
    temperature: float = 0.9,
    max_tokens: int = 2048,
    json_mode: bool = False,
    max_retries: int = 3,
) -> str | None:
    """OpenAI API 호출"""
    try:
        from openai import OpenAI
    except ImportError:
        print("[오류] openai 패키지가 필요합니다: pip install openai")
        sys.exit(1)

    client = OpenAI()
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"    [API 에러 (시도 {attempt+1}/{max_retries})] {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return None


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """텍스트를 chunk_size 단위로 분할 (convert_aihub_qa.py와 동일 로직)"""
    if not text or len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    sentences = re.split(r"(?<=[.!?。])\s*", text)

    current_chunk = ""
    for sentence in sentences:
        if not sentence.strip():
            continue
        if len(current_chunk) + len(sentence) <= chunk_size:
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            while len(sentence) > chunk_size:
                chunks.append(sentence[:chunk_size].strip())
                sentence = sentence[chunk_size:]
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def generate_qa_pair(doc_type: str, industry: str, model: str = "gpt-4o") -> dict | None:
    """Step A: GPT-4o로 문서 + QA 쌍 동시 생성"""
    hint = QUESTION_HINTS.get(doc_type, "핵심 내용에 대한 질문")

    user_prompt = (
        f"문서 유형: {doc_type}\n"
        f"업종: {industry}\n"
        f"질문 스타일: {hint}\n\n"
        f"위 조건에 맞는 문서와 QA 쌍을 생성하세요."
    )

    result = call_openai(
        QA_GENERATION_SYSTEM,
        user_prompt,
        model=model,
        temperature=0.9,
        max_tokens=2048,
        json_mode=True,
    )

    if not result:
        return None

    try:
        parsed = json.loads(result)
        # 필수 필드 확인
        required = ["passage", "question", "answer", "citation_text"]
        if not all(parsed.get(k) for k in required):
            return None
        return parsed
    except (json.JSONDecodeError, KeyError):
        return None


def build_training_sample(
    qa_result: dict,
    is_negative: bool = False,
) -> dict:
    """QA 결과를 v2_qa 학습 데이터 형식으로 변환"""
    passage = qa_result["passage"]
    question = qa_result["question"]
    answer = qa_result["answer"]
    citation_text = qa_result["citation_text"]

    # Context를 청크로 분할
    chunks = split_into_chunks(passage)
    if not chunks:
        chunks = [passage[:CHUNK_SIZE]]

    context_array = json.dumps(chunks, ensure_ascii=False)

    if is_negative:
        # 부정 예시: 다른 카테고리의 질문을 사용하여 "답을 찾을 수 없음" 상황
        user_prompt = f"Context:\n{context_array}\n\nQuestion: {question}"
        assistant_response = json.dumps({
            "answer": NOT_FOUND_ANSWER,
            "citations": [],
        }, ensure_ascii=False)
    else:
        user_prompt = f"Context:\n{context_array}\n\nQuestion: {question}"
        assistant_response = json.dumps({
            "answer": answer,
            "citations": [
                {"content": citation_text[:200] if len(citation_text) > 200 else citation_text}
            ],
        }, ensure_ascii=False)

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_response},
        ]
    }


def synthesize_all(
    targets: dict[str, int],
    output_path: Path,
    model: str = "gpt-4o",
    seed: int = 42,
    append: bool = False,
    negative_ratio: float = NEGATIVE_RATIO,
) -> int:
    """전체 합성 데이터 생성"""
    random.seed(seed)

    mode = "a" if append else "w"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_success = 0
    total_failed = 0

    # 부정 예시를 위한 저장소
    all_qa_results = []

    with open(output_path, mode, encoding="utf-8") as f:
        for doc_type, count in targets.items():
            print(f"\n  [{doc_type}] {count}건 생성 시작...")
            cat_success = 0
            cat_failed = 0

            for i in range(count):
                industry = random.choice(INDUSTRIES)
                print(f"    [{i+1}/{count}] {industry}", end=" ", flush=True)

                # Step A: QA 쌍 생성
                qa_result = generate_qa_pair(doc_type, industry, model=model)
                if not qa_result:
                    print("- QA 생성 실패")
                    cat_failed += 1
                    continue

                # Step B: 학습 데이터 형식 변환
                sample = build_training_sample(qa_result, is_negative=False)

                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                cat_success += 1
                qa_result["_doc_type"] = doc_type  # 카테고리 교차 매칭용
                all_qa_results.append(qa_result)
                print("- OK")

                # Rate limiting
                if (i + 1) % 10 == 0:
                    time.sleep(1)
                    print(f"    --- {i+1}건 완료 (성공: {cat_success}, 실패: {cat_failed}) ---")

            print(f"  [{doc_type}] 결과: 성공 {cat_success}, 실패 {cat_failed}")
            total_success += cat_success
            total_failed += cat_failed

        # 부정 예시 추가 (카테고리 교차: 다른 doc_type의 질문 + 현재 context)
        neg_count = max(1, int(total_success * negative_ratio))
        if len(all_qa_results) >= 2:
            print(f"\n  [부정 예시 - 카테고리 교차] {neg_count}건 생성...")
            neg_added = 0

            # doc_type별로 그룹핑 (생성 시 doc_type 정보 활용)
            by_doc_type = {}
            for qa in all_qa_results:
                dt = qa.get("_doc_type", "기타")
                by_doc_type.setdefault(dt, []).append(qa)

            doc_types = list(by_doc_type.keys())
            random.shuffle(all_qa_results)

            for i in range(min(neg_count, len(all_qa_results) - 1)):
                current = all_qa_results[i]
                current_dt = current.get("_doc_type", "기타")

                # 다른 doc_type에서 질문 선택
                other_types = [dt for dt in doc_types if dt != current_dt]
                if not other_types:
                    # 같은 타입밖에 없으면 충분히 먼 인덱스에서 가져옴
                    other_idx = (i + len(all_qa_results) // 2) % len(all_qa_results)
                    other_q = all_qa_results[other_idx]["question"]
                else:
                    other_dt = random.choice(other_types)
                    other_q = random.choice(by_doc_type[other_dt])["question"]

                qa_with_wrong_ctx = {
                    "passage": current["passage"],
                    "question": other_q,
                    "answer": "",
                    "citation_text": "",
                }
                sample = build_training_sample(qa_with_wrong_ctx, is_negative=True)
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                neg_added += 1

            total_success += neg_added
            print(f"  부정 예시 추가: {neg_added}건")

    print(f"\n  전체 결과: 성공 {total_success}, 실패 {total_failed}")
    return total_success


def main():
    parser = argparse.ArgumentParser(description="v2_qa 합성 데이터 생성")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR / "synthetic_qa.jsonl"))
    parser.add_argument("--count", type=int, default=0, help="총 생성 수 (0=기본값 300)")
    parser.add_argument("--model", type=str, default="gpt-4o")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--append", action="store_true", help="기존 파일에 추가")
    parser.add_argument("--negative-ratio", type=float, default=NEGATIVE_RATIO, help="부정 예시 비율")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 계획만 확인")
    args = parser.parse_args()

    if not args.dry_run and not os.getenv("OPENAI_API_KEY"):
        print("[오류] OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    # 목표 수 결정
    if args.count > 0:
        ratio = args.count / 300
        targets = {k: max(1, int(v * ratio)) for k, v in DOC_TYPE_TARGETS.items()}
    else:
        targets = dict(DOC_TYPE_TARGETS)

    total_target = sum(targets.values())

    print("=" * 70)
    print("  v2_qa 합성 데이터 생성")
    print("=" * 70)
    print(f"  출력: {args.output}")
    print(f"  모델: {args.model}")
    print(f"  목표: {total_target}건 (+ 부정 예시 {int(total_target * args.negative_ratio)}건)")
    for dt, cnt in targets.items():
        print(f"    {dt}: {cnt}건")

    if args.dry_run:
        neg_count = int(total_target * args.negative_ratio)
        total_calls = total_target  # QA는 1회 호출
        est_cost = total_calls * 0.025
        print(f"\n[DRY RUN]")
        print(f"  예상 API 호출: {total_calls}회")
        print(f"  예상 비용: ~${est_cost:.1f}")
        print(f"  부정 예시: {neg_count}건 (API 호출 불필요)")
        return

    # 생성 시작
    output_path = Path(args.output)
    total_success = synthesize_all(
        targets, output_path,
        model=args.model, seed=args.seed, append=args.append,
        negative_ratio=args.negative_ratio,
    )

    # 결과 요약
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        print(f"\n  [결과 요약]")
        print(f"  총 데이터: {len(lines)}건")

        json_valid = 0
        has_citations = 0
        negative_count = 0
        citation_len_dist = {}

        for line in lines:
            sample = json.loads(line)
            assistant = sample["messages"][2]["content"]
            try:
                parsed = json.loads(assistant)
                json_valid += 1
                if "citations" in parsed and isinstance(parsed["citations"], list):
                    has_citations += 1
                    cit_len = len(parsed["citations"])
                    citation_len_dist[cit_len] = citation_len_dist.get(cit_len, 0) + 1
                    if cit_len == 0:
                        negative_count += 1
            except json.JSONDecodeError:
                pass

        pct = json_valid / len(lines) * 100 if lines else 0
        print(f"  JSON 유효: {json_valid}/{len(lines)} ({pct:.1f}%)")
        print(f"  citations 존재: {has_citations}/{len(lines)}")
        print(f"  not-found (citations=[]): {negative_count}건 ({negative_count/len(lines)*100:.1f}%)")
        print(f"  citations 길이 분포: {dict(sorted(citation_len_dist.items()))}")

    print(f"\n  완료! 총 성공: {total_success}건")


if __name__ == "__main__":
    main()
