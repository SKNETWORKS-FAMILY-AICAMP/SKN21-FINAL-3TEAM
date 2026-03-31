"""
학습 데이터 재생성 — 하드코딩 컨텍스트를 실제 RAG 검색 결과로 교체

목적:
  - 기존 eval.jsonl/train.jsonl의 하드코딩 규정 컨텍스트 → 실제 RAG 검색 결과로 교체
  - 모델이 RAG 파이프라인이 주는 실제 형식에 맞춰 학습하도록 함
  - baseline 83.3% → RAG 환경에서도 80%+ 목표

동작:
  1. eval.jsonl/train.jsonl에서 질문 + gold 라벨 추출
  2. 각 질문으로 Qdrant RAG 검색 실행
  3. RAG 결과를 학습 데이터 헤더 형식으로 변환
  4. 새로운 user prompt 생성 → 저장

실행:
  python scripts/rebuild_train_with_rag.py                    # train + eval 모두
  python scripts/rebuild_train_with_rag.py --eval-only         # eval만
  python scripts/rebuild_train_with_rag.py --max-samples 10    # 테스트 (10건만)
  python scripts/rebuild_train_with_rag.py --dry-run           # 검색만 확인 (저장 안 함)

환경:
  .env에 QDRANT_URL, QDRANT_API_KEY 필요
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# 프로젝트 루트
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


def parse_args():
    parser = argparse.ArgumentParser(description="학습 데이터 RAG 컨텍스트로 재생성")
    parser.add_argument("--eval-only", action="store_true", help="eval.jsonl만 처리")
    parser.add_argument("--train-only", action="store_true", help="train.jsonl만 처리")
    parser.add_argument("--max-samples", type=int, default=0, help="최대 처리 건수 (0=전체)")
    parser.add_argument("--top-k", type=int, default=10, help="RAG 검색 결과 수")
    parser.add_argument("--dry-run", action="store_true", help="검색만 확인 (저장 안 함)")
    parser.add_argument("--output-suffix", default="_rag", help="출력 파일 접미사 (기본: _rag)")
    return parser.parse_args()


def extract_question(user_content: str) -> str:
    """user message에서 순수 질문만 추출 (규정 컨텍스트 제거)"""
    if "## 사용자 질문" in user_content:
        return user_content.split("## 사용자 질문")[-1].strip()
    if "질문:" in user_content:
        return user_content.split("질문:")[-1].strip()
    return user_content


def build_rag_user_prompt(question: str, rag_results: list[dict]) -> str:
    """RAG 검색 결과 → 학습 데이터와 동일한 형식의 user prompt 생성

    학습 데이터 헤더 패턴:
      - 단일 규정: ### 제9조 (원격근무)
      - 교차 규정: ### 개인정보처리규정 — 제5조 (개인정보 수집 원칙)
    """
    if not rag_results:
        return f"## 관련 규정 문서\n(관련 규정을 찾지 못했습니다)\n\n## 사용자 질문\n{question}"

    context_parts = []
    for doc in rag_results:
        source = doc.get("source", "")
        title = doc.get("title", "")
        article = doc.get("article", "")
        content = doc.get("content", "")

        # .pdf 확장자 제거
        source = re.sub(r"\.pdf$", "", source)

        # 학습 데이터와 동일한 헤더 형식 구성
        if article and title and title != article:
            # 교차 규정 패턴: ### 개인정보처리규정 — 제5조 (개인정보 수집 원칙)
            # title이 규정명이고 article이 조항인 경우
            if re.match(r"제\d+조", article):
                # article = "제5조", title = "개인정보처리규정" 또는 title = "개인정보 수집 원칙"
                # title이 규정명 느낌이면: ### 규정명 — 제N조 (...)
                # title이 조항 제목 느낌이면: ### 제N조 (title)
                if "규정" in title or "규칙" in title or "강령" in title:
                    header = f"### {title} — {article}"
                else:
                    header = f"### {article} ({title})"
            else:
                header = f"### {title} — {article}"
        elif article:
            header = f"### {article}"
        elif title:
            header = f"### {title}"
        else:
            header = "### 규정"

        context_parts.append(f"{header}\n{content}")

    context_text = "\n\n".join(context_parts)
    return f"## 관련 규정 문서\n{context_text}\n\n## 사용자 질문\n{question}"


def process_file(
    input_path: Path,
    output_path: Path,
    rag_pipeline,
    top_k: int = 10,
    max_samples: int = 0,
    dry_run: bool = False,
):
    """하나의 jsonl 파일 처리"""
    # 로드
    samples = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    if max_samples > 0:
        samples = samples[:max_samples]

    print(f"\n  입력: {input_path.name} ({len(samples)}건)")

    results = []
    rag_empty_count = 0
    total_rag_time = 0

    for i, sample in enumerate(samples, 1):
        messages = sample["messages"]
        system_prompt = messages[0]["content"]
        original_user = messages[1]["content"]
        assistant_response = messages[2]["content"]

        # 질문 추출
        question = extract_question(original_user)

        # gold label 추출 (no_regulation이면 RAG 결과 비움)
        gold_result = None
        try:
            gold_parsed = json.loads(assistant_response) if assistant_response.strip().startswith("{") else None
            if not gold_parsed:
                _m = re.search(r"\{.*\}", assistant_response, re.DOTALL)
                if _m:
                    gold_parsed = json.loads(_m.group())
            if gold_parsed:
                gold_result = gold_parsed.get("result", "")
        except Exception:
            pass

        # no_regulation → RAG 결과 비움 (규정 10개 + "규정없음" 라벨은 모순)
        if gold_result == "no_regulation":
            rag_results = []
            rag_time = 0
        else:
            # RAG 검색
            t0 = time.time()
            try:
                rag_results = rag_pipeline.retrieve(
                    query=question,
                    user_id=None,
                    top_k=top_k,
                    filter={"source": "regulations"},
                )
            except Exception as e:
                print(f"  [{i}] RAG 에러: {e}")
                rag_results = []
            rag_time = time.time() - t0
        total_rag_time += rag_time

        if not rag_results:
            rag_empty_count += 1

        # 새 user prompt 생성
        new_user = build_rag_user_prompt(question, rag_results)

        # dry-run 모드: 처음 3건만 출력
        if dry_run and i <= 3:
            print(f"\n  --- [{i}] ---")
            print(f"  질문: {question[:80]}...")
            print(f"  RAG 결과: {len(rag_results)}건 ({rag_time:.2f}s)")
            if rag_results:
                for j, r in enumerate(rag_results[:3]):
                    print(f"    [{j}] {r.get('article', '?')} / {r.get('title', '?')}")
            print(f"  헤더 미리보기:")
            for line in new_user.split("\n")[:6]:
                print(f"    {line}")

        # 새 sample 구성
        new_sample = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": new_user},
                {"role": "assistant", "content": assistant_response},
            ]
        }
        results.append(new_sample)

        # 진행 로그
        if i <= 3 or i % 100 == 0 or i == len(samples):
            print(f"  [{i:04d}/{len(samples)}] "
                  f"RAG={len(rag_results)}건 ({rag_time:.2f}s) "
                  f"Q: {question[:50]}...")

    # 통계
    avg_rag_time = total_rag_time / len(samples) if samples else 0
    print(f"\n  통계:")
    print(f"    처리: {len(results)}건")
    print(f"    RAG 빈 결과: {rag_empty_count}건 ({rag_empty_count/len(results)*100:.1f}%)")
    print(f"    평균 RAG 시간: {avg_rag_time:.3f}s")

    # 저장
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for sample in results:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        print(f"    저장: {output_path}")
    else:
        print(f"    (dry-run: 저장 안 함)")

    return results


def main():
    args = parse_args()

    print("=" * 60)
    print("  학습 데이터 RAG 컨텍스트 재생성")
    print("=" * 60)
    print(f"  top_k: {args.top_k}")
    print(f"  max_samples: {args.max_samples or '전체'}")
    print(f"  dry_run: {args.dry_run}")

    # RAG 파이프라인 초기화
    print("\n  RAG 파이프라인 초기화...")
    from ai.rag.qdrant_pipeline import get_qdrant_pipeline
    pipeline = get_qdrant_pipeline()

    # Qdrant 상태 확인
    info = pipeline.vector_store.client.get_collection(
        pipeline.vector_store.collection_name
    )
    print(f"  Qdrant 컬렉션: {pipeline.vector_store.collection_name}")
    print(f"  포인트 수: {info.points_count}")

    if info.points_count == 0:
        print("  ⚠ Qdrant에 문서가 없습니다! 먼저 ingest를 실행하세요.")
        return

    # 파일 처리
    data_dir = ROOT / "data" / "training" / "v1_judgment"
    suffix = args.output_suffix

    files_to_process = []
    if not args.train_only:
        files_to_process.append(("eval.jsonl", f"eval{suffix}.jsonl"))
    if not args.eval_only:
        files_to_process.append(("train.jsonl", f"train{suffix}.jsonl"))

    for input_name, output_name in files_to_process:
        input_path = data_dir / input_name
        output_path = data_dir / output_name

        if not input_path.exists():
            print(f"\n  ⚠ {input_path} 없음, 스킵")
            continue

        process_file(
            input_path=input_path,
            output_path=output_path,
            rag_pipeline=pipeline,
            top_k=args.top_k,
            max_samples=args.max_samples,
            dry_run=args.dry_run,
        )

    print("\n" + "=" * 60)
    print("  완료!")
    if not args.dry_run:
        print(f"\n  생성된 파일:")
        for _, output_name in files_to_process:
            p = data_dir / output_name
            if p.exists():
                count = sum(1 for line in open(p, encoding="utf-8") if line.strip())
                print(f"    {p.name}: {count}건")

        print(f"\n  다음 단계:")
        print(f"    1. 생성된 데이터 검증: head -1 data/training/v1_judgment/eval{suffix}.jsonl | python -m json.tool")
        print(f"    2. RunPod에 업로드 후 재학습:")
        print(f"       - train{suffix}.jsonl → train.jsonl로 교체")
        print(f"       - python3 ai/finetuning/train_v1_judgment.py --mode train")
        print(f"    3. 재평가:")
        print(f"       - python3 scripts/eval_lora_v1_rag_improved.py --mode all")
    print("=" * 60)


if __name__ == "__main__":
    main()
