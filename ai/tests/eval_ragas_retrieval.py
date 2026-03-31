"""
RAGAS 검색 품질 전용 평가

RAG의 본질 = 검색을 잘 하느냐.
LLM 답변 포맷(JSON 등)과 무관하게 검색 품질만 측정.

지표:
  - Context Precision: 검색된 컨텍스트 중 정답에 관련있는 비율
  - Context Recall: 정답에 필요한 정보가 검색 결과에 포함되었는지

데이터:
  - benchmark_testset.jsonl (670건) — 질문 + 정답 조항 + 기대 답변
  - 실제 RAG 검색 수행 → 검색된 컨텍스트로 평가

실행:
  # 기본 (30건, gpt-4o-mini)
  python -m ai.tests.eval_ragas_retrieval

  # 전체 670건
  python -m ai.tests.eval_ragas_retrieval --max-cases 0

  # Reranker 비교
  python -m ai.tests.eval_ragas_retrieval --no-reranker

  # HyDE 활성화
  python -m ai.tests.eval_ragas_retrieval --use-hyde
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── CLI ──
parser = argparse.ArgumentParser(description="RAGAS 검색 품질 전용 평가")
parser.add_argument("--max-cases", type=int, default=30, help="최대 평가 건수 (기본: 30, 0=전체)")
parser.add_argument("--model", type=str, default="gpt-4o-mini", help="RAGAS 평가용 LLM")
parser.add_argument("--top-k", type=int, default=10, help="검색 결과 수")
parser.add_argument("--use-reranker", action="store_true", default=True)
parser.add_argument("--no-reranker", action="store_true", help="Reranker 비활성화")
parser.add_argument("--use-hyde", action="store_true", help="HyDE 활성화")
parser.add_argument("--threshold", type=float, default=0.1, help="Score threshold")
args = parser.parse_args()

if args.no_reranker:
    args.use_reranker = False

OUTPUT_DIR = ROOT / "outputs" / "ragas_eval"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_benchmark(max_cases: int) -> list[dict]:
    """benchmark_testset.jsonl 로드"""
    bench_path = ROOT / "data" / "evaluation" / "benchmark_testset.jsonl"
    samples = []
    with open(bench_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            # 질문 추출
            inp = item["input"]
            if "질문:" in inp:
                question = inp.split("질문:")[-1].strip()
            else:
                question = inp.strip()

            # 정답 조항 + 정답 텍스트
            article = item.get("metadata", {}).get("article", "")
            reference = item.get("reference_output", "")

            # 정답에 포함된 규정 컨텍스트 (input에서 추출)
            ref_context = ""
            if "관련 규정:" in inp:
                ref_context = inp.split("관련 규정:")[1]
                if "질문:" in ref_context:
                    ref_context = ref_context.split("질문:")[0].strip()

            samples.append({
                "test_id": item["test_id"],
                "question": question,
                "article": article,
                "reference": reference,
                "reference_context": ref_context,
            })

            if max_cases > 0 and len(samples) >= max_cases:
                break

    return samples


async def run_rag_search(samples: list[dict]) -> list[dict]:
    """실제 RAG 파이프라인으로 검색"""
    from ai.rag.qdrant_pipeline import get_qdrant_pipeline
    pipeline = get_qdrant_pipeline()

    results = []
    for i, s in enumerate(samples):
        try:
            docs = pipeline.retrieve(
                query=s["question"],
                top_k=args.top_k,
                filter={"source": "regulations"},
                use_reranker=args.use_reranker,
                score_threshold=args.threshold,
                use_hyde=args.use_hyde,
            )
            retrieved_contexts = []
            for doc in docs:
                content = doc.get("content", "")
                title = doc.get("title", "")
                article = doc.get("article", "")
                source = doc.get("source", "")
                ctx = f"{source} — {title}\n{content}" if title else content
                retrieved_contexts.append(ctx)

            # Hit check
            hit = False
            hit_rank = -1
            article_key = re.match(r"(제\d+조)", s["article"])
            if article_key:
                key = article_key.group(1)
                for rank, ctx in enumerate(retrieved_contexts):
                    if key in ctx:
                        hit = True
                        hit_rank = rank + 1
                        break

            s["retrieved_contexts"] = retrieved_contexts
            s["hit"] = hit
            s["hit_rank"] = hit_rank
            s["doc_count"] = len(docs)

        except Exception as e:
            print(f"  [WARN] 검색 실패 #{i}: {e}")
            s["retrieved_contexts"] = []
            s["hit"] = False
            s["hit_rank"] = -1
            s["doc_count"] = 0

        results.append(s)
        if (i + 1) % 10 == 0:
            print(f"  검색 진행: {i+1}/{len(samples)}")

    return results


def run_ragas_retrieval_eval(samples: list[dict]) -> dict:
    """RAGAS Context Precision + Context Recall 평가"""
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from ragas import evaluate, EvaluationDataset, SingleTurnSample
    from ragas.metrics import context_precision, context_recall
    from ragas.llms import LangchainLLMWrapper
    from langchain_openai import ChatOpenAI

    llm = LangchainLLMWrapper(ChatOpenAI(model=args.model, temperature=0))

    eval_samples = []
    for s in samples:
        if not s["retrieved_contexts"]:
            continue
        eval_samples.append(SingleTurnSample(
            user_input=s["question"],
            retrieved_contexts=s["retrieved_contexts"],
            response=s["reference"],        # 정답 텍스트
            reference=s["reference_context"],  # 정답 규정 컨텍스트
        ))

    if not eval_samples:
        print("  [ERROR] 평가 가능한 샘플 없음")
        return {}

    dataset = EvaluationDataset(samples=eval_samples)

    metrics = [context_precision, context_recall]

    print(f"\n  RAGAS 검색 품질 평가 ({len(eval_samples)}건)...")
    print(f"  지표: Context Precision, Context Recall")
    start = time.time()

    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=llm,
        show_progress=True,
    )

    elapsed = time.time() - start
    print(f"  평가 완료: {elapsed:.1f}초")
    return result


def main():
    print("\n" + "=" * 60)
    print("  RAGAS 검색 품질 전용 평가")
    print(f"  Reranker: {'ON' if args.use_reranker else 'OFF'}")
    print(f"  HyDE: {'ON' if args.use_hyde else 'OFF'}")
    print(f"  Top-K: {args.top_k}  |  Threshold: {args.threshold}")
    print("=" * 60)

    # 1. 벤치마크 로드
    print("\n[1/4] 벤치마크 데이터 로드")
    samples = load_benchmark(args.max_cases)
    print(f"  {len(samples)}건 로드")

    # 2. RAG 검색 수행
    print("\n[2/4] RAG 검색 수행")
    loop = asyncio.new_event_loop()
    samples = loop.run_until_complete(run_rag_search(samples))
    loop.close()

    # 3. 커스텀 검색 지표 (Hit Rate, MRR)
    print("\n[3/4] 검색 지표 계산")
    hits = sum(1 for s in samples if s["hit"])
    total = len(samples)
    hit_rate = hits / total if total else 0

    mrr_sum = 0
    for s in samples:
        if s["hit"] and s["hit_rank"] > 0:
            mrr_sum += 1.0 / s["hit_rank"]
    mrr = mrr_sum / total if total else 0

    avg_rank = 0
    hit_samples = [s for s in samples if s["hit"]]
    if hit_samples:
        avg_rank = sum(s["hit_rank"] for s in hit_samples) / len(hit_samples)

    print(f"\n  ┌─────────────────────────────────────┐")
    print(f"  │  Hit Rate:  {hits}/{total} ({hit_rate:.1%})")
    print(f"  │  MRR:       {mrr:.4f}")
    print(f"  │  Avg Rank:  {avg_rank:.2f}")
    print(f"  └─────────────────────────────────────┘")

    # 4. RAGAS 평가
    print("\n[4/4] RAGAS Context Precision / Recall 평가")
    result = run_ragas_retrieval_eval(samples)

    # 결과 추출
    ragas_scores = {}
    try:
        for key in ["context_precision", "context_recall"]:
            try:
                ragas_scores[key] = float(result[key])
            except (KeyError, TypeError):
                pass
    except Exception:
        pass

    if not ragas_scores:
        try:
            df = result.to_pandas()
            for col in ["context_precision", "context_recall"]:
                if col in df.columns:
                    ragas_scores[col] = float(df[col].mean())
        except Exception:
            pass

    # 최종 출력
    print("\n" + "=" * 60)
    print("  RAG 검색 품질 평가 결과")
    print("=" * 60)
    print(f"  {'Hit Rate':40s} {hit_rate:.4f}  {'█' * int(hit_rate * 20)}{'░' * (20 - int(hit_rate * 20))}")
    print(f"  {'MRR (Mean Reciprocal Rank)':40s} {mrr:.4f}  {'█' * int(mrr * 20)}{'░' * (20 - int(mrr * 20))}")

    for key, display in [("context_precision", "Context Precision (RAGAS)"),
                         ("context_recall", "Context Recall (RAGAS)")]:
        val = ragas_scores.get(key, "N/A")
        if isinstance(val, float):
            bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
            print(f"  {display:40s} {val:.4f}  {bar}")
        else:
            print(f"  {display:40s} {val}")
    print("=" * 60)

    # 저장
    output = {
        "config": {
            "max_cases": args.max_cases,
            "top_k": args.top_k,
            "use_reranker": args.use_reranker,
            "use_hyde": args.use_hyde,
            "threshold": args.threshold,
            "model": args.model,
        },
        "retrieval_metrics": {
            "hit_rate": hit_rate,
            "mrr": mrr,
            "avg_rank": avg_rank,
            "total": total,
            "hits": hits,
        },
        "ragas_scores": ragas_scores,
        "per_sample": [
            {
                "test_id": s["test_id"],
                "question": s["question"][:60],
                "article": s["article"],
                "hit": s["hit"],
                "hit_rank": s["hit_rank"],
                "doc_count": s["doc_count"],
            }
            for s in samples
        ],
    }

    suffix = "reranker" if args.use_reranker else "basic"
    if args.use_hyde:
        suffix += "_hyde"
    out_path = OUTPUT_DIR / f"ragas_retrieval_{suffix}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {out_path}")


if __name__ == "__main__":
    main()
