"""
RAGAS 평가: RAG 파이프라인 품질 측정

RAGAS (Retrieval Augmented Generation Assessment) 4대 지표:
  - Faithfulness: 답변이 검색된 컨텍스트에 근거하는지
  - Answer Relevancy: 답변이 질문에 관련있는지
  - Context Precision: 검색된 컨텍스트 중 관련 있는 비율
  - Context Recall: 정답에 필요한 컨텍스트가 검색되었는지

실행:
  # 하드코딩 컨텍스트 기준 (API 비용 발생 — OpenAI)
  python -m ai.tests.eval_ragas

  # 샘플 수 제한
  python -m ai.tests.eval_ragas --max-cases 20

  # 실제 RAG 검색 컨텍스트 사용
  python -m ai.tests.eval_ragas --use-rag

  # 결과만 확인 (이전 결과 로드)
  python -m ai.tests.eval_ragas --load-only
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
parser = argparse.ArgumentParser(description="RAGAS 평가")
parser.add_argument("--max-cases", type=int, default=50, help="최대 평가 건수 (기본: 50)")
parser.add_argument("--use-rag", action="store_true", help="실제 RAG 검색 사용 (기본: 하드코딩 컨텍스트)")
parser.add_argument("--model", type=str, default="gpt-4o-mini", help="RAGAS 평가용 LLM (기본: gpt-4o-mini)")
parser.add_argument("--load-only", action="store_true", help="이전 결과만 로드")
parser.add_argument("--eval-data", type=str, default="v1_judgment_v3",
                    help="평가 데이터 디렉토리 (기본: v1_judgment_v3)")
args = parser.parse_args()

OUTPUT_DIR = ROOT / "outputs" / "ragas_eval"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ── 데이터 파싱 ──

def extract_question(user_content: str) -> str:
    """user 메시지에서 질문 추출"""
    if "## 사용자 질문" in user_content:
        return user_content.split("## 사용자 질문")[-1].strip()
    return user_content.strip()


def extract_contexts(user_content: str) -> list[str]:
    """user 메시지에서 규정 컨텍스트 추출 (### 단위 분리)"""
    contexts = []
    if "## 관련 규정 문서" not in user_content:
        return [user_content]

    doc_section = user_content.split("## 관련 규정 문서")[1]
    if "## 사용자 질문" in doc_section:
        doc_section = doc_section.split("## 사용자 질문")[0]

    # ### 단위로 분리
    parts = re.split(r"\n###\s+", doc_section)
    for part in parts:
        part = part.strip()
        if part and len(part) > 10:
            contexts.append(part)

    return contexts if contexts else [doc_section.strip()]


def extract_answer(assistant_content: str) -> str:
    """assistant 응답에서 답변 텍스트 추출"""
    try:
        data = json.loads(assistant_content)
        # 판단 결과를 자연어로 변환
        result = data.get("result", "")
        reasoning = data.get("reasoning", "")
        conditions = data.get("conditions", "")

        answer_parts = [f"판단: {result}"]
        if reasoning:
            answer_parts.append(f"근거: {reasoning}")
        if conditions:
            answer_parts.append(f"조건: {conditions}")

        regs = data.get("regulations", [])
        for reg in regs:
            article = reg.get("article", "")
            content = reg.get("content", "")
            if article:
                answer_parts.append(f"관련 규정: {article} - {content}")

        return "\n".join(answer_parts)
    except json.JSONDecodeError:
        return assistant_content


def load_eval_data(max_cases: int = 50) -> list[dict]:
    """평가 데이터 로드"""
    eval_path = ROOT / "data" / "training" / args.eval_data / "eval.jsonl"
    if not eval_path.exists():
        # fallback
        eval_path = ROOT / "data" / "training" / "v1_judgment" / "eval.jsonl"

    print(f"  데이터: {eval_path}")
    samples = []
    with open(eval_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            sample = json.loads(line)
            messages = sample["messages"]
            if len(messages) < 3:
                continue

            user_content = messages[1]["content"]
            assistant_content = messages[2]["content"]

            question = extract_question(user_content)
            contexts = extract_contexts(user_content)
            answer = extract_answer(assistant_content)
            reference = extract_answer(assistant_content)  # gold answer

            samples.append({
                "user_input": question,
                "retrieved_contexts": contexts,
                "response": answer,
                "reference": reference,
            })

            if max_cases > 0 and len(samples) >= max_cases:
                break

    print(f"  로드 완료: {len(samples)}건")
    return samples


async def run_rag_retrieval(samples: list[dict]) -> list[dict]:
    """실제 RAG 파이프라인으로 컨텍스트 교체"""
    try:
        from ai.rag.qdrant_pipeline import get_qdrant_pipeline
    except ImportError:
        print("  [WARN] RAG 파이프라인 import 실패 — 하드코딩 컨텍스트 사용")
        return samples

    pipeline = get_qdrant_pipeline()
    updated = []

    for i, s in enumerate(samples):
        try:
            results = await pipeline.search(s["user_input"], top_k=10)
            rag_contexts = [doc.get("content", "") for doc in results if doc.get("content")]
            if rag_contexts:
                s["retrieved_contexts"] = rag_contexts
        except Exception as e:
            print(f"  [WARN] RAG 검색 실패 (#{i}): {e}")

        updated.append(s)
        if (i + 1) % 10 == 0:
            print(f"  RAG 검색 진행: {i+1}/{len(samples)}")

    return updated


def run_ragas_evaluation(samples: list[dict]) -> dict:
    """RAGAS 평가 실행"""
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from ragas import evaluate, EvaluationDataset, SingleTurnSample
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    # LLM & Embeddings
    llm = LangchainLLMWrapper(ChatOpenAI(model=args.model, temperature=0))
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))

    # Build evaluation dataset
    eval_samples = []
    for s in samples:
        eval_samples.append(SingleTurnSample(
            user_input=s["user_input"],
            retrieved_contexts=s["retrieved_contexts"],
            response=s["response"],
            reference=s["reference"],
        ))

    dataset = EvaluationDataset(samples=eval_samples)

    # Metrics (old-style — compatible with evaluate())
    metrics = [
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ]

    print(f"\n  RAGAS 평가 시작 ({len(samples)}건, 모델: {args.model})...")
    print(f"  지표: Faithfulness, Answer Relevancy, Context Precision, Context Recall")
    start = time.time()

    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        show_progress=True,
    )

    elapsed = time.time() - start
    print(f"  평가 완료: {elapsed:.1f}초")

    return result


def print_results(result_dict: dict):
    """결과 출력"""
    print("\n" + "=" * 60)
    print("  RAGAS 평가 결과")
    print("=" * 60)

    metric_names = {
        "faithfulness": "Faithfulness (충실도)",
        "answer_relevancy": "Answer Relevancy (답변 관련성)",
        "context_precision": "Context Precision (컨텍스트 정밀도)",
        "context_recall": "Context Recall (컨텍스트 재현율)",
    }

    for key, display in metric_names.items():
        val = result_dict.get(key, "N/A")
        if isinstance(val, float):
            bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
            print(f"  {display:40s} {val:.4f}  {bar}")
        else:
            print(f"  {display:40s} {val}")

    print("=" * 60)


def main():
    print("\n" + "=" * 60)
    print("  RAGAS 평가 — RAG 파이프라인 품질 측정")
    print("=" * 60)

    result_file = OUTPUT_DIR / "ragas_results.json"

    if args.load_only:
        if result_file.exists():
            with open(result_file, encoding="utf-8") as f:
                saved = json.load(f)
            print_results(saved["scores"])
            return
        else:
            print("  이전 결과 없음")
            return

    # 1. 데이터 로드
    print("\n[1/3] 데이터 로드")
    samples = load_eval_data(args.max_cases)

    # 2. RAG 검색 (선택)
    if args.use_rag:
        print("\n[2/3] RAG 검색")
        samples = asyncio.run(run_rag_retrieval(samples))
    else:
        print("\n[2/3] 하드코딩 컨텍스트 사용 (--use-rag 미지정)")

    # 3. RAGAS 평가
    print("\n[3/3] RAGAS 평가")
    result = run_ragas_evaluation(samples)

    # 결과 저장 — EvaluationResult 구조 탐색
    scores = {}
    print(f"  result type: {type(result)}")
    print(f"  result dir: {[a for a in dir(result) if not a.startswith('_')]}")

    # Try multiple access patterns
    try:
        # Pattern 1: dict-like access
        for key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            try:
                val = result[key]
                scores[key] = float(val)
            except (KeyError, TypeError):
                pass
    except Exception:
        pass

    if not scores:
        # Pattern 2: .scores dict
        if hasattr(result, 'scores') and isinstance(result.scores, dict):
            scores = {k: float(v) for k, v in result.scores.items() if isinstance(v, (int, float))}

    if not scores:
        # Pattern 3: to_pandas
        try:
            df = result.to_pandas()
            for col in df.columns:
                if col in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
                    scores[col] = float(df[col].mean())
        except Exception:
            pass

    print(f"  Extracted scores: {scores}")

    output = {
        "config": {
            "max_cases": args.max_cases,
            "use_rag": args.use_rag,
            "model": args.model,
            "eval_data": args.eval_data,
        },
        "scores": scores,
        "sample_count": len(samples),
    }

    # Per-sample scores
    try:
        df = result.to_pandas()
        per_sample = df.to_dict(orient="records")
        output["per_sample"] = per_sample
    except Exception:
        pass

    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {result_file}")

    print_results(scores)


if __name__ == "__main__":
    main()
