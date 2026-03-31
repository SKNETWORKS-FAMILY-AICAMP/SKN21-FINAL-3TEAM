"""
RAG 검색 품질 Before/After 비교 벤치마크

비교 항목:
  1. [Before] 기존 RAG (RRF만) — use_reranker=False, score_threshold=None
  2. [After]  개선 RAG (Reranker + Score Threshold) — use_reranker=True, score_threshold=0.1

평가 지표:
  - 정답 조항 Hit Rate: 검색된 문서 중 정답 조항(article)이 포함된 비율
  - 평균 정답 조항 순위: 정답 조항이 몇 번째로 검색되었는지
  - 노이즈 비율: 검색된 문서 중 관련 없는 문서 비율
  - 검색 소요시간

실행:
  cd 프로젝트루트
  python -m ai.tests.benchmark_rag_improvement
  python -m ai.tests.benchmark_rag_improvement --top_k 10
  python -m ai.tests.benchmark_rag_improvement --with-hyde   # HyDE도 테스트
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# Windows 인코딩 대응
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── CLI ──
parser = argparse.ArgumentParser(description="RAG 검색 품질 Before/After 비교")
parser.add_argument("--top_k", type=int, default=10, help="검색 결과 수 (기본: 10)")
parser.add_argument("--max_cases", type=int, default=30, help="최대 테스트 케이스 수 (기본: 30)")
parser.add_argument("--with-hyde", action="store_true", help="HyDE도 함께 테스트")
parser.add_argument("--threshold", type=float, default=0.1, help="Score threshold (기본: 0.1)")
args = parser.parse_args()


# ── 출력 헬퍼 ──

def header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def table(headers: list, rows: list, widths: list | None = None):
    if not widths:
        widths = [max(len(str(r[i])) for r in [headers] + rows) + 2 for i in range(len(headers))]
    h = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    s = "|-" + "-|-".join("-" * w for w in widths) + "-|"
    print(h)
    print(s)
    for row in rows:
        print("| " + " | ".join(str(c).ljust(w) for c, w in zip(row, widths)) + " |")


# ── 벤치마크 데이터 로드 ──

def load_benchmark():
    """benchmark_testset.jsonl에서 judgment 카테고리만 로드"""
    path = ROOT / "data" / "evaluation" / "benchmark_testset.jsonl"
    if not path.exists():
        print(f"[ERROR] 벤치마크 파일 없음: {path}")
        sys.exit(1)

    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            # judgment 카테고리만 (정답 조항이 있는 것)
            if item.get("category") == "judgment":
                # 정답 조항 추출
                article = item.get("metadata", {}).get("article", "")
                if article:
                    # input에서 질문만 추출 (마지막 "질문:" 이후)
                    full_input = item.get("input", "")
                    question = full_input
                    if "질문:" in full_input:
                        question = full_input.split("질문:")[-1].strip()

                    cases.append({
                        "test_id": item["test_id"],
                        "question": question,
                        "expected_article": article,
                        "judgment_type": item.get("metadata", {}).get("judgment_type", ""),
                        "subcategory": item.get("subcategory", ""),
                    })

    return cases[:args.max_cases]


# ── 검색 실행 + 평가 ──

def evaluate_search(pipeline, cases, label, **search_kwargs):
    """검색 실행 후 평가 지표 계산"""
    results = []
    total_time = 0

    for i, case in enumerate(cases):
        t = time.time()
        docs = pipeline.retrieve(
            query=case["question"],
            user_id=None,
            top_k=args.top_k,
            filter={"source": "regulations"},
            **search_kwargs,
        )
        elapsed = time.time() - t
        total_time += elapsed

        # 정답 조항 매칭 확인
        expected = case["expected_article"].replace(" ", "").replace("(", "（").replace(")", "）")
        # 조항명에서 괄호 내용 제거하여 매칭 (예: "제4조(채용)" → "제4조")
        expected_short = expected.split("(")[0].split("（")[0]

        hit = False
        hit_rank = -1
        matched_sources = []

        for rank, doc in enumerate(docs):
            content = doc.get("content", "").replace(" ", "")
            source = doc.get("source", "").replace(" ", "")
            article = doc.get("article", "").replace(" ", "")

            # 조항 매칭: content, source, article 중 하나에 포함
            if (expected_short in content or expected_short in source or
                expected_short in article or expected in content):
                if not hit:
                    hit = True
                    hit_rank = rank + 1
                matched_sources.append(f"[{rank+1}] {doc.get('source', '')[:30]}")

        results.append({
            "test_id": case["test_id"],
            "question": case["question"][:40],
            "expected": case["expected_article"],
            "hit": hit,
            "hit_rank": hit_rank,
            "doc_count": len(docs),
            "elapsed": elapsed,
            "matched": matched_sources,
            "top_sources": [d.get("source", "")[:25] for d in docs[:3]],
            "top_scores": [round(d.get("score", 0), 4) for d in docs[:3]],
        })

        # 진행상황
        status = "HIT" if hit else "MISS"
        print(f"  [{label}] {i+1}/{len(cases)} {case['test_id']} {status} "
              f"(rank={hit_rank}, docs={len(docs)}, {elapsed:.2f}s) "
              f"| {case['question'][:35]}...")

    return results, total_time


def compute_metrics(results):
    """평가 지표 계산"""
    total = len(results)
    hits = [r for r in results if r["hit"]]
    hit_rate = len(hits) / total * 100 if total > 0 else 0

    hit_ranks = [r["hit_rank"] for r in results if r["hit_rank"] > 0]
    avg_rank = sum(hit_ranks) / len(hit_ranks) if hit_ranks else float("inf")

    # MRR (Mean Reciprocal Rank)
    rr_sum = sum(1.0 / r["hit_rank"] for r in results if r["hit_rank"] > 0)
    mrr = rr_sum / total if total > 0 else 0

    avg_docs = sum(r["doc_count"] for r in results) / total if total > 0 else 0
    avg_time = sum(r["elapsed"] for r in results) / total if total > 0 else 0

    return {
        "total": total,
        "hits": len(hits),
        "hit_rate": hit_rate,
        "avg_rank": avg_rank,
        "mrr": mrr,
        "avg_docs": avg_docs,
        "avg_time": avg_time,
    }


# ── 메인 ──

def main():
    header("RAG 검색 품질 Before/After 비교 벤치마크")
    print(f"  top_k={args.top_k}, max_cases={args.max_cases}, "
          f"threshold={args.threshold}, hyde={args.with_hyde}")

    # 벤치마크 데이터 로드
    cases = load_benchmark()
    print(f"\n  벤치마크 케이스: {len(cases)}건 (judgment 카테고리)")
    print(f"  유형 분포: {', '.join(set(c['subcategory'] for c in cases))}")

    # RAG 파이프라인 초기화
    print("\n  RAG 파이프라인 초기화 중...")
    from ai.rag.qdrant_pipeline import get_qdrant_pipeline
    pipeline = get_qdrant_pipeline()
    print("  초기화 완료")

    # ── [Before] 기존 RAG ──
    header("[Before] 기존 RAG (RRF만)")
    before_results, before_time = evaluate_search(
        pipeline, cases, "Before",
        use_reranker=False,
        score_threshold=None,
    )
    before_metrics = compute_metrics(before_results)

    # ── [After] 개선 RAG (Reranker + Threshold) ──
    header("[After] 개선 RAG (Reranker + Score Threshold)")
    after_results, after_time = evaluate_search(
        pipeline, cases, "After",
        use_reranker=True,
        score_threshold=args.threshold,
    )
    after_metrics = compute_metrics(after_results)

    # ── [After+HyDE] (선택) ──
    hyde_metrics = None
    if args.with_hyde:
        header("[After+HyDE] 개선 RAG + HyDE")
        hyde_results, hyde_time = evaluate_search(
            pipeline, cases, "HyDE",
            use_reranker=True,
            score_threshold=args.threshold,
            use_hyde=True,
        )
        hyde_metrics = compute_metrics(hyde_results)

    # ── 결과 비교 ──
    header("종합 비교")

    metrics_list = [
        ("Before (RRF만)", before_metrics),
        ("After (Reranker+Threshold)", after_metrics),
    ]
    if hyde_metrics:
        metrics_list.append(("After+HyDE", hyde_metrics))

    rows = []
    for label, m in metrics_list:
        rows.append([
            label,
            f"{m['hits']}/{m['total']}",
            f"{m['hit_rate']:.1f}%",
            f"{m['avg_rank']:.2f}" if m['avg_rank'] != float('inf') else "N/A",
            f"{m['mrr']:.4f}",
            f"{m['avg_docs']:.1f}",
            f"{m['avg_time']:.3f}s",
        ])

    table(
        ["구성", "Hit", "Hit Rate", "평균순위", "MRR", "평균문서수", "평균시간"],
        rows,
        [28, 8, 10, 10, 10, 12, 10],
    )

    # 개선 효과
    header("개선 효과 (After - Before)")
    diff_hit = after_metrics["hit_rate"] - before_metrics["hit_rate"]
    diff_mrr = after_metrics["mrr"] - before_metrics["mrr"]
    diff_time = after_metrics["avg_time"] - before_metrics["avg_time"]

    print(f"  Hit Rate:  {diff_hit:+.1f}%p")
    print(f"  MRR:       {diff_mrr:+.4f}")
    print(f"  응답시간:   {diff_time:+.3f}s")

    if hyde_metrics:
        diff_hit_h = hyde_metrics["hit_rate"] - before_metrics["hit_rate"]
        diff_mrr_h = hyde_metrics["mrr"] - before_metrics["mrr"]
        diff_time_h = hyde_metrics["avg_time"] - before_metrics["avg_time"]
        print(f"\n  [HyDE 추가 효과]")
        print(f"  Hit Rate:  {diff_hit_h:+.1f}%p")
        print(f"  MRR:       {diff_mrr_h:+.4f}")
        print(f"  응답시간:   {diff_time_h:+.3f}s")

    # 개별 케이스 비교 (Before MISS → After HIT)
    header("개선된 케이스 (Before MISS → After HIT)")
    improved = []
    for b, a in zip(before_results, after_results):
        if not b["hit"] and a["hit"]:
            improved.append((b, a))

    if improved:
        for b, a in improved[:10]:
            print(f"  {b['test_id']} | {b['question']}")
            print(f"    Before: MISS | After: HIT (rank={a['hit_rank']})")
            print(f"    기대: {b['expected']}")
            print(f"    After 상위: {a['top_sources']}")
            print()
    else:
        print("  없음 (Before에서 이미 모두 HIT이거나, 개선 없음)")

    # 악화된 케이스 (Before HIT → After MISS)
    header("악화된 케이스 (Before HIT → After MISS)")
    degraded = []
    for b, a in zip(before_results, after_results):
        if b["hit"] and not a["hit"]:
            degraded.append((b, a))

    if degraded:
        for b, a in degraded[:10]:
            print(f"  {b['test_id']} | {b['question']}")
            print(f"    Before: HIT (rank={b['hit_rank']}) | After: MISS")
            print(f"    기대: {b['expected']}")
            print(f"    After 상위: {a['top_sources']}")
            print()
    else:
        print("  없음 (악화된 케이스 없음)")

    # 결과 저장
    output_path = ROOT / "data" / "evaluation" / "benchmark_results" / "rag_improvement_comparison.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "config": {
            "top_k": args.top_k,
            "max_cases": args.max_cases,
            "threshold": args.threshold,
            "with_hyde": args.with_hyde,
        },
        "before": {"metrics": before_metrics, "results": before_results},
        "after": {"metrics": after_metrics, "results": after_results},
    }
    if hyde_metrics:
        output["after_hyde"] = {"metrics": hyde_metrics}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {output_path}")


if __name__ == "__main__":
    main()
