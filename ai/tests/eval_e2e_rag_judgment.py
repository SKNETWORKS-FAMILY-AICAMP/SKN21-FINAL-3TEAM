"""
E2E 평가: 개선된 RAG + LLM API로 judgment 정확도 측정

목적:
  기존 LoRA v1 (86.6%)과 비교하기 위해,
  개선된 RAG 파이프라인으로 검색한 컨텍스트를 LLM API에 전달하여
  판단 정확도를 측정합니다.

평가 단계:
  1. eval.jsonl에서 질문 + gold label 추출
  2. 개선된 RAG로 규정 문서 검색
  3. (선택) LLM API로 판단 수행
  4. gold label과 비교하여 정확도 측정

실행:
  # RAG 컨텍스트 품질만 측정 (빠름, API 비용 없음)
  python -m ai.tests.eval_e2e_rag_judgment --rag-only

  # RAG + LLM 판단 정확도 측정 (API 비용 발생)
  python -m ai.tests.eval_e2e_rag_judgment

  # 샘플 수 제한
  python -m ai.tests.eval_e2e_rag_judgment --max-cases 50

  # GPT-4o 사용
  python -m ai.tests.eval_e2e_rag_judgment --model gpt-4o
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

# 프로젝트 루트
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# Windows 인코딩
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── CLI ──
parser = argparse.ArgumentParser(description="E2E RAG + Judgment 평가")
parser.add_argument("--max-cases", type=int, default=0, help="최대 평가 건수 (0=전체)")
parser.add_argument("--model", type=str, default="gpt-4o-mini", help="LLM 모델 (기본: gpt-4o-mini)")
parser.add_argument("--rag-only", action="store_true", help="RAG 컨텍스트 품질만 측정 (LLM 호출 안 함)")
parser.add_argument("--top-k", type=int, default=10, help="RAG 검색 결과 수 (기본: 10)")
parser.add_argument("--use-reranker", action="store_true", default=True, help="Reranker 사용 (기본: True)")
parser.add_argument("--no-reranker", action="store_true", help="Reranker 비활성화")
parser.add_argument("--score-threshold", type=float, default=0.1, help="Score threshold (기본: 0.1)")
parser.add_argument("--use-hyde", action="store_true", help="HyDE 활성화")
parser.add_argument("--save-details", action="store_true", help="개별 케이스 상세 결과 저장")
args = parser.parse_args()

if args.no_reranker:
    args.use_reranker = False

VALID_RESULTS = {"yes", "no", "conditional", "no_regulation"}


# ── 헬퍼 함수 ──

def header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def parse_judgment_json(text: str) -> dict | None:
    """텍스트에서 judgment JSON 추출"""
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


def extract_question_from_user_msg(user_content: str) -> str:
    """user 메시지에서 사용자 질문만 추출 (## 사용자 질문 이후)"""
    if "## 사용자 질문" in user_content:
        return user_content.split("## 사용자 질문")[-1].strip()
    if "질문:" in user_content:
        return user_content.split("질문:")[-1].strip()
    return user_content.strip()


def extract_baked_articles(user_content: str) -> list[str]:
    """user 메시지에서 baked-in 규정 조항명 추출"""
    articles = []
    # "### 제N조 (...)" or "### XX규정 — 제N조 (...)" 패턴
    for match in re.finditer(r"###\s+(?:[\w]+\s*—\s*)?(제\d+조[^)\n]*(?:\([^)]*\))?)", user_content):
        articles.append(match.group(1).strip())
    # fallback: "## 관련 규정 문서" 아래 "### " 뒤의 헤딩
    if not articles:
        for match in re.finditer(r"###\s+(.+)", user_content):
            articles.append(match.group(1).strip())
    return articles


def check_article_hit(expected_articles: list[str], rag_docs: list[dict]) -> dict:
    """baked-in 조항이 RAG 검색 결과에 포함되는지 확인"""
    hits = 0
    hit_details = []

    for article in expected_articles:
        # 조항명에서 핵심 부분 추출 (제N조)
        article_short = re.match(r"(제\d+조)", article)
        if article_short:
            article_key = article_short.group(1)
        else:
            article_key = article[:10]

        found = False
        found_rank = -1
        for rank, doc in enumerate(rag_docs):
            content = doc.get("content", "")
            source = doc.get("source", "")
            title = doc.get("title", "")
            article_field = doc.get("article", "")

            if (article_key in content or article_key in source or
                article_key in title or article_key in article_field):
                found = True
                found_rank = rank + 1
                break

        if found:
            hits += 1
        hit_details.append({
            "article": article,
            "found": found,
            "rank": found_rank,
        })

    return {
        "total": len(expected_articles),
        "hits": hits,
        "hit_rate": hits / len(expected_articles) if expected_articles else 0,
        "details": hit_details,
    }


def build_rag_prompt(question: str, rag_docs: list[dict]) -> str:
    """RAG 검색 결과로 user prompt 구성 (학습 데이터와 동일한 형식)"""
    context_parts = []
    for doc in rag_docs:
        source = doc.get("source", "알 수 없음")
        title = doc.get("title", "")
        content = doc.get("content", "")
        if title:
            context_parts.append(f"### {source} — {title}\n{content}")
        else:
            context_parts.append(f"### {source}\n{content}")

    context_text = "\n\n".join(context_parts)
    return f"## 관련 규정 문서\n{context_text}\n\n## 사용자 질문\n{question}"


# ── 데이터 로드 ──

def load_eval_data(max_cases: int = 0) -> list[dict]:
    """eval.jsonl에서 평가 데이터 로드"""
    eval_path = ROOT / "data" / "training" / "v1_judgment" / "eval.jsonl"
    samples = []
    with open(eval_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            sample = json.loads(line)
            messages = sample["messages"]

            # gold label 추출
            gold_parsed = parse_judgment_json(messages[2]["content"])
            if not gold_parsed:
                continue

            gold_result = gold_parsed.get("result", "")
            if gold_result not in VALID_RESULTS:
                continue

            # 질문 추출
            user_content = messages[1]["content"]
            question = extract_question_from_user_msg(user_content)
            baked_articles = extract_baked_articles(user_content)

            samples.append({
                "system_prompt": messages[0]["content"],
                "user_content": user_content,
                "question": question,
                "gold_result": gold_result,
                "gold_parsed": gold_parsed,
                "baked_articles": baked_articles,
            })

    if max_cases > 0:
        samples = samples[:max_cases]

    return samples


# ── 메인 평가 ──

async def run_evaluation():
    header("E2E RAG + Judgment 평가")
    print(f"  모델: {args.model}")
    print(f"  RAG: top_k={args.top_k}, reranker={args.use_reranker}, "
          f"threshold={args.score_threshold}, hyde={args.use_hyde}")
    print(f"  RAG-only: {args.rag_only}")

    # 데이터 로드
    samples = load_eval_data(args.max_cases)
    print(f"\n  평가 데이터: {len(samples)}건")
    gold_dist = Counter(s["gold_result"] for s in samples)
    print(f"  분포: {dict(gold_dist)}")

    # RAG 파이프라인 초기화
    print("\n  RAG 파이프라인 초기화 중...")
    from ai.rag.qdrant_pipeline import get_qdrant_pipeline
    pipeline = get_qdrant_pipeline()
    print("  초기화 완료")

    # LLM 클라이언트 (RAG-only가 아닌 경우)
    llm_client = None
    if not args.rag_only:
        from openai import AsyncOpenAI
        llm_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        print(f"  LLM 클라이언트 초기화 완료 ({args.model})")

    # ── 평가 루프 ──
    rag_context_stats = {
        "total_articles": 0,
        "found_articles": 0,
        "per_case_hit_rates": [],
    }

    judgment_stats = {
        "total": 0,
        "json_valid": 0,
        "correct": 0,
        "category_stats": {},
    }

    details = []
    total_rag_time = 0
    total_llm_time = 0
    total_tokens = 0

    for i, sample in enumerate(samples):
        # Step 1: RAG 검색
        t_rag = time.time()
        rag_docs = pipeline.retrieve(
            query=sample["question"],
            user_id=None,
            top_k=args.top_k,
            filter={"source": "regulations"},
            use_reranker=args.use_reranker,
            score_threshold=args.score_threshold,
            use_hyde=args.use_hyde,
        )
        rag_elapsed = time.time() - t_rag
        total_rag_time += rag_elapsed

        # Step 2: 컨텍스트 품질 평가
        article_check = check_article_hit(sample["baked_articles"], rag_docs)
        rag_context_stats["total_articles"] += article_check["total"]
        rag_context_stats["found_articles"] += article_check["hits"]
        rag_context_stats["per_case_hit_rates"].append(article_check["hit_rate"])

        detail = {
            "idx": i,
            "question": sample["question"][:80],
            "gold_result": sample["gold_result"],
            "baked_articles": sample["baked_articles"],
            "rag_article_hit": article_check,
            "rag_doc_count": len(rag_docs),
            "rag_top_sources": [d.get("source", "")[:30] for d in rag_docs[:3]],
            "rag_top_scores": [round(d.get("score", 0), 3) for d in rag_docs[:3]],
            "rag_time": round(rag_elapsed, 3),
        }

        # Step 3: LLM 판단 (RAG-only가 아닌 경우)
        pred_result = None
        if llm_client:
            rag_prompt = build_rag_prompt(sample["question"], rag_docs)

            t_llm = time.time()
            try:
                response = await llm_client.chat.completions.create(
                    model=args.model,
                    messages=[
                        {"role": "system", "content": sample["system_prompt"]},
                        {"role": "user", "content": rag_prompt},
                    ],
                    max_tokens=512,
                    temperature=0.1,
                )
                llm_elapsed = time.time() - t_llm
                total_llm_time += llm_elapsed

                pred_text = response.choices[0].message.content or ""
                if response.usage:
                    total_tokens += response.usage.total_tokens

                pred_parsed = parse_judgment_json(pred_text)

                judgment_stats["total"] += 1
                gold = sample["gold_result"]

                if gold not in judgment_stats["category_stats"]:
                    judgment_stats["category_stats"][gold] = {"correct": 0, "total": 0}
                judgment_stats["category_stats"][gold]["total"] += 1

                if pred_parsed:
                    judgment_stats["json_valid"] += 1
                    pred_result = pred_parsed.get("result", "")

                    if pred_result == gold:
                        judgment_stats["correct"] += 1
                        judgment_stats["category_stats"][gold]["correct"] += 1

                detail["pred_result"] = pred_result
                detail["pred_match"] = pred_result == gold if pred_result else None
                detail["llm_time"] = round(llm_elapsed, 3)

            except Exception as e:
                detail["llm_error"] = str(e)
                judgment_stats["total"] += 1

        details.append(detail)

        # 진행상황 출력
        status_parts = [f"[{i+1:03d}/{len(samples)}]"]
        status_parts.append(f"gold={sample['gold_result']}")

        rag_hit = f"ctx={article_check['hits']}/{article_check['total']}"
        status_parts.append(rag_hit)

        if pred_result is not None:
            match = "OK" if pred_result == sample["gold_result"] else "MISS"
            status_parts.append(f"pred={pred_result} {match}")

        status_parts.append(f"({rag_elapsed:.2f}s)")
        status_parts.append(f"| {sample['question'][:40]}...")
        print(f"  {'  '.join(status_parts)}")

    # ── 결과 출력 ──
    header("RAG 컨텍스트 품질 평가")
    total_a = rag_context_stats["total_articles"]
    found_a = rag_context_stats["found_articles"]
    overall_hit = found_a / total_a * 100 if total_a > 0 else 0
    avg_case_hit = (sum(rag_context_stats["per_case_hit_rates"]) /
                    len(rag_context_stats["per_case_hit_rates"]) * 100
                    if rag_context_stats["per_case_hit_rates"] else 0)

    print(f"  전체 조항 적중률:  {found_a}/{total_a} ({overall_hit:.1f}%)")
    print(f"  케이스별 평균 적중률:  {avg_case_hit:.1f}%")
    print(f"  평균 RAG 검색 시간:  {total_rag_time / len(samples):.3f}s")

    # 미적중 케이스 분석
    miss_cases = [d for d in details if d["rag_article_hit"]["hit_rate"] < 1.0]
    if miss_cases:
        print(f"\n  조항 미적중 케이스: {len(miss_cases)}건")
        for mc in miss_cases[:5]:
            missed = [a["article"] for a in mc["rag_article_hit"]["details"] if not a["found"]]
            print(f"    [{mc['idx']:03d}] {mc['question'][:50]}...")
            print(f"         미적중 조항: {', '.join(missed)}")

    if not args.rag_only and judgment_stats["total"] > 0:
        header("LLM 판단 정확도 (개선된 RAG 컨텍스트 기반)")
        total = judgment_stats["total"]
        valid = judgment_stats["json_valid"]
        correct = judgment_stats["correct"]

        print(f"  총 평가 건수:   {total}")
        print(f"  JSON 유효율:    {valid}/{total} ({valid/total*100:.1f}%)")
        print(f"  판단 정확도:    {correct}/{total} ({correct/total*100:.1f}%)")
        print()
        print(f"  {'카테고리':<15} {'정확도':>10} {'건수':>8}")
        print("  " + "-" * 35)
        for cat in sorted(judgment_stats["category_stats"].keys()):
            stats = judgment_stats["category_stats"][cat]
            acc = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f"  {cat:<15} {acc:>9.1f}% {stats['total']:>7}건")

        # LoRA v1과 비교
        header("LoRA v1 (86.6%) 대비 비교")
        lora_v1 = {
            "overall": 86.6,
            "no": 82.0,
            "no_regulation": 97.0,
            "yes": 85.0,
            "conditional": 84.0,
        }
        current_overall = correct / total * 100 if total > 0 else 0
        diff = current_overall - lora_v1["overall"]
        print(f"  {'지표':<20} {'LoRA v1':>10} {'RAG+{}'.format(args.model):>15} {'차이':>10}")
        print("  " + "-" * 58)
        print(f"  {'전체 정확도':<20} {lora_v1['overall']:>9.1f}% {current_overall:>14.1f}% {diff:>+9.1f}%p")

        for cat in ["yes", "no", "conditional", "no_regulation"]:
            if cat in judgment_stats["category_stats"]:
                stats = judgment_stats["category_stats"][cat]
                cat_acc = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
                cat_diff = cat_acc - lora_v1.get(cat, 0)
                print(f"  {cat:<20} {lora_v1.get(cat, 0):>9.1f}% {cat_acc:>14.1f}% {cat_diff:>+9.1f}%p")

        print(f"\n  LLM 평균 응답시간: {total_llm_time / total:.3f}s")
        print(f"  총 토큰 사용량: {total_tokens:,}")

        # 의미 해석
        print()
        if diff > 3:
            print("  >> 개선된 RAG가 LoRA v1 대비 유의미한 성능 향상을 제공합니다.")
            print("  >> RAG 개선 환경에서 LoRA v1 재평가 시 90%+ 달성 가능성 높음")
        elif diff > 0:
            print("  >> 소폭 개선. RAG 품질 향상이 판단 정확도에 긍정적 영향.")
            print("  >> v2 보강 데이터 학습 병행 시 추가 향상 기대")
        else:
            print("  >> RAG 개선만으로는 부족. v2 보강 데이터 학습이 필수적.")
            print("  >> no/conditional 경계 보강 데이터 생성 후 LoRA v2 학습 권장")

    # ── 결과 저장 ──
    output_dir = ROOT / "outputs" / "v1_judgment"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "config": {
            "model": args.model,
            "top_k": args.top_k,
            "use_reranker": args.use_reranker,
            "score_threshold": args.score_threshold,
            "use_hyde": args.use_hyde,
            "total_samples": len(samples),
        },
        "rag_context_quality": {
            "total_articles": total_a,
            "found_articles": found_a,
            "overall_hit_rate": round(overall_hit, 2),
            "avg_case_hit_rate": round(avg_case_hit, 2),
            "avg_rag_time": round(total_rag_time / len(samples), 4),
        },
    }

    if not args.rag_only and judgment_stats["total"] > 0:
        total = judgment_stats["total"]
        result["judgment_accuracy"] = {
            "total": total,
            "json_valid": judgment_stats["json_valid"],
            "json_valid_rate": round(judgment_stats["json_valid"] / total, 4),
            "result_accuracy": round(judgment_stats["correct"] / total, 4),
            "category_stats": judgment_stats["category_stats"],
            "total_tokens": total_tokens,
            "avg_llm_time": round(total_llm_time / total, 4),
        }

    if args.save_details:
        result["details"] = details

    result_path = output_dir / "eval_e2e_rag_judgment.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {result_path}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
