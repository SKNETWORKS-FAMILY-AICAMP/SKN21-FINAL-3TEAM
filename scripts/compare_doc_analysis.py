"""
문서 분석 성능 비교: GPT API vs sLLM (Kanana-1.5-8B)

DB에 저장된 GPT 분석 결과(summary, category, tags)를 정답으로 놓고,
같은 문서를 sLLM으로 분석해서 비교한다.

사용법:
  # EC2에서 실행 (프로젝트 루트)
  python scripts/compare_doc_analysis.py

  # 특정 문서만 테스트
  python scripts/compare_doc_analysis.py --doc-id 3

환경변수:
  DATABASE_URL: PostgreSQL 연결 (필수)
  VLLM_BASE_URL: vLLM 서버 주소 (기본: http://localhost:8000/v1)
  VLLM_MODEL: 모델명 (기본: kakaocorp/kanana-1.5-8b-instruct-2505)
"""

import asyncio
import argparse
import json
import os
import sys
import time

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── 색상 출력 ──
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def colored(text, color):
    return f"{color}{text}{RESET}"


# ── DB에서 문서 가져오기 ──
async def get_documents_from_db(doc_id=None):
    """DB에서 GPT 분석 완료된 문서 목록 조회"""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print(colored("ERROR: DATABASE_URL 환경변수가 설정되지 않았습니다.", RED))
        return []

    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        from app.models.document import Document

        query = select(Document).where(
            Document.status == "completed",
            Document.content.isnot(None),
            Document.category.isnot(None),  # GPT 분석 완료된 것만
        )
        if doc_id:
            query = query.where(Document.id == doc_id)
        query = query.order_by(Document.created_at.desc())

        result = await session.execute(query)
        docs = result.scalars().all()

    await engine.dispose()
    return docs


# ── sLLM으로 분석 ──
async def analyze_with_sllm(text: str, title: str) -> dict:
    """sLLM(vLLM)으로 문서 분석"""
    from ai.serving.vllm_client import VLLMProvider

    llm = VLLMProvider()
    truncated = text[:3000]

    prompt = f"""다음 문서를 분석해주세요.

문서 제목: {title}
문서 내용:
{truncated}

다음 JSON 형식으로 응답해주세요:
{{
  "summary": "2-3문장으로 문서의 핵심 내용을 요약",
  "category": "다음 중 하나 선택: 계약서, 회의록, 제안서, 정책문서, 인사문서, 보고서, 기타",
  "tags": ["관련 키워드 태그 3-5개, 예: 마케팅, 계약, 2025"]
}}"""

    system_prompt = "당신은 문서 분석 전문가입니다. 주어진 문서를 분석하여 요약, 분류, 태그를 JSON으로 반환합니다.\n\n반드시 유효한 JSON만 출력하세요. 설명이나 마크다운 없이 JSON 객체만 반환합니다."

    t_start = time.time()
    response = await llm.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        json_mode=True,
        temperature=0.2,
    )
    elapsed = time.time() - t_start

    # JSON 파싱 시도
    try:
        # 마크다운 코드블록 제거
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        result = json.loads(content)
        result["_elapsed"] = elapsed
        result["_model"] = response.model
        result["_raw"] = response.content
        return result
    except json.JSONDecodeError:
        return {
            "summary": "",
            "category": "",
            "tags": [],
            "_elapsed": elapsed,
            "_model": response.model,
            "_raw": response.content,
            "_parse_error": True,
        }


# ── 비교 메트릭 ──
def compute_tags_f1(gpt_tags: list, sllm_tags: list) -> dict:
    """태그 F1 스코어 계산"""
    gpt_set = set(t.lower() for t in gpt_tags)
    sllm_set = set(t.lower() for t in sllm_tags)

    if not gpt_set and not sllm_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not sllm_set:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    if not gpt_set:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    tp = len(gpt_set & sllm_set)
    precision = tp / len(sllm_set) if sllm_set else 0
    recall = tp / len(gpt_set) if gpt_set else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def compare_summary(gpt_summary: str, sllm_summary: str) -> float:
    """요약 유사도 (키워드 겹침 비율)"""
    if not gpt_summary or not sllm_summary:
        return 0.0

    gpt_words = set(gpt_summary.replace(",", " ").replace(".", " ").split())
    sllm_words = set(sllm_summary.replace(",", " ").replace(".", " ").split())

    # 2글자 이상 단어만
    gpt_words = {w for w in gpt_words if len(w) >= 2}
    sllm_words = {w for w in sllm_words if len(w) >= 2}

    if not gpt_words:
        return 0.0

    overlap = len(gpt_words & sllm_words)
    return round(overlap / len(gpt_words), 3)


# ── 메인 ──
async def main():
    parser = argparse.ArgumentParser(description="문서 분석 성능 비교: GPT vs sLLM")
    parser.add_argument("--doc-id", type=int, help="특정 문서 ID만 테스트")
    args = parser.parse_args()

    print(colored("=" * 70, CYAN))
    print(colored("  문서 분석 성능 비교: GPT API vs sLLM (Kanana-1.5-8B)", BOLD))
    print(colored("=" * 70, CYAN))

    # vLLM 서버 확인
    vllm_url = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    vllm_model = os.getenv("VLLM_MODEL", "kakaocorp/kanana-1.5-8b-instruct-2505")
    print(f"\nvLLM 서버: {vllm_url}")
    print(f"모델: {vllm_model}")

    # DB에서 문서 가져오기
    print("\nDB에서 문서 로드 중...")
    docs = await get_documents_from_db(args.doc_id)
    if not docs:
        print(colored("분석 가능한 문서가 없습니다.", RED))
        return

    print(f"총 {len(docs)}개 문서 비교 시작\n")

    # 결과 수집
    results = []
    category_match = 0
    total_f1 = 0
    total_summary_sim = 0
    json_parse_errors = 0

    for i, doc in enumerate(docs):
        print(colored(f"─── [{i+1}/{len(docs)}] {doc.title} ───", BOLD))

        # GPT 결과 (DB에 저장된 값)
        gpt_category = doc.category or ""
        gpt_tags = doc.tags or []
        gpt_summary = doc.summary or ""

        print(f"  GPT category: {gpt_category}")
        print(f"  GPT tags:     {gpt_tags}")
        print(f"  GPT summary:  {gpt_summary[:80]}...")

        # sLLM 분석
        print(f"  sLLM 분석 중...", end=" ", flush=True)
        try:
            sllm_result = await analyze_with_sllm(doc.content or "", doc.title)
        except Exception as e:
            print(colored(f"실패: {e}", RED))
            json_parse_errors += 1
            results.append({"doc": doc.title, "error": str(e)})
            continue

        elapsed = sllm_result.get("_elapsed", 0)
        print(f"({elapsed:.1f}s)")

        if sllm_result.get("_parse_error"):
            print(colored(f"  ⚠ JSON 파싱 실패! 원문: {sllm_result['_raw'][:200]}", RED))
            json_parse_errors += 1
            results.append({"doc": doc.title, "parse_error": True, "raw": sllm_result["_raw"][:200]})
            continue

        sllm_category = sllm_result.get("category", "")
        sllm_tags = sllm_result.get("tags", [])
        sllm_summary = sllm_result.get("summary", "")

        print(f"  sLLM category: {sllm_category}")
        print(f"  sLLM tags:     {sllm_tags}")
        print(f"  sLLM summary:  {sllm_summary[:80]}...")

        # 비교
        cat_match = gpt_category.strip() == sllm_category.strip()
        tags_f1 = compute_tags_f1(gpt_tags, sllm_tags)
        summary_sim = compare_summary(gpt_summary, sllm_summary)

        category_match += int(cat_match)
        total_f1 += tags_f1["f1"]
        total_summary_sim += summary_sim

        cat_icon = colored("✅", GREEN) if cat_match else colored("❌", RED)
        f1_color = GREEN if tags_f1["f1"] >= 0.7 else YELLOW if tags_f1["f1"] >= 0.4 else RED
        sim_color = GREEN if summary_sim >= 0.5 else YELLOW if summary_sim >= 0.3 else RED

        f1_val = tags_f1["f1"]
        f1_str = colored(f"{f1_val:.0%}", f1_color)
        sim_str = colored(f"{summary_sim:.0%}", sim_color)
        print(f"  결과: category {cat_icon}  tags F1={f1_str}  summary 유사도={sim_str}")
        print()

        results.append({
            "doc": doc.title,
            "category_match": cat_match,
            "tags_f1": tags_f1["f1"],
            "summary_sim": summary_sim,
            "elapsed": elapsed,
        })

    # 종합 결과
    valid = len(results) - json_parse_errors
    print(colored("=" * 70, CYAN))
    print(colored("  종합 결과", BOLD))
    print(colored("=" * 70, CYAN))

    if valid > 0:
        cat_acc = category_match / valid
        avg_f1 = total_f1 / valid
        avg_sim = total_summary_sim / valid

        cat_color = GREEN if cat_acc >= 0.8 else YELLOW if cat_acc >= 0.5 else RED
        f1_color = GREEN if avg_f1 >= 0.7 else YELLOW if avg_f1 >= 0.4 else RED
        sim_color = GREEN if avg_sim >= 0.5 else YELLOW if avg_sim >= 0.3 else RED

        print(f"  문서 수:        {len(docs)}개 (성공 {valid}개, JSON 파싱 실패 {json_parse_errors}개)")
        print(f"  Category 일치: {colored(f'{cat_acc:.0%}', cat_color)} ({category_match}/{valid})")
        print(f"  Tags F1 평균:  {colored(f'{avg_f1:.0%}', f1_color)}")
        print(f"  Summary 유사도: {colored(f'{avg_sim:.0%}', sim_color)}")
        print()

        if cat_acc >= 0.8 and avg_f1 >= 0.5:
            print(colored("  → sLLM base 모델로도 충분히 사용 가능합니다!", GREEN))
        elif cat_acc >= 0.5:
            print(colored("  → 파인튜닝하면 품질 개선 가능합니다.", YELLOW))
        else:
            print(colored("  → 파인튜닝이 필요합니다. base 모델 품질이 부족합니다.", RED))
    else:
        print(colored("  유효한 결과가 없습니다.", RED))

    # JSON 결과 저장
    output_path = os.path.join(os.path.dirname(__file__), "doc_analysis_comparison.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  상세 결과 저장: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
