"""
Qdrant 컬렉션에 저장된 source 종류 조회 스크립트

사용법:
    python ai/rag/inspect_sources.py
    python ai/rag/inspect_sources.py --detail      # source별 문서 수 + 샘플 출력
    python ai/rag/inspect_sources.py --source dudu_tech_regulations  # 특정 source 샘플만
"""

import argparse
import os
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

COLLECTION_NAME = "documents"
SCROLL_LIMIT = 100  # 한 번에 가져올 문서 수


def get_client() -> QdrantClient:
    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")
    if not url or not api_key:
        raise ValueError(".env에 QDRANT_URL과 QDRANT_API_KEY를 설정해주세요.")
    return QdrantClient(url=url, api_key=api_key)


def fetch_all_payloads(client: QdrantClient) -> list[dict]:
    """컬렉션 전체 payload 스크롤로 가져오기"""
    payloads = []
    offset = None

    while True:
        results, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=SCROLL_LIMIT,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        payloads.extend([r.payload for r in results])

        if next_offset is None:
            break
        offset = next_offset

    return payloads


def main():
    parser = argparse.ArgumentParser(description="Qdrant source 종류 조회")
    parser.add_argument("--detail", action="store_true", help="source별 문서 수 + 샘플 출력")
    parser.add_argument("--source", type=str, default=None, help="특정 source의 샘플 출력")
    args = parser.parse_args()

    client = get_client()

    # 컬렉션 정보
    info = client.get_collection(COLLECTION_NAME)
    total = info.points_count
    print(f"\n컬렉션: {COLLECTION_NAME}")
    print(f"전체 문서 수: {total}건")

    payloads = fetch_all_payloads(client)
    print(f"로드된 문서 수: {len(payloads)}건\n")

    # source 집계
    sources = [p.get("source", "(없음)") for p in payloads]
    counter = Counter(sources)

    print("=" * 50)
    print("  source 종류 목록")
    print("=" * 50)
    for source, count in sorted(counter.items(), key=lambda x: -x[1]):
        print(f"  {source:<40} {count}건")
    print(f"\n  총 {len(counter)}종류")

    # 특정 source 샘플 출력
    if args.source:
        print(f"\n\n=== '{args.source}' 샘플 5건 ===")
        samples = [p for p in payloads if p.get("source") == args.source][:5]
        for i, p in enumerate(samples, 1):
            print(f"\n[{i}]")
            for k, v in p.items():
                val = str(v)[:100] + "..." if len(str(v)) > 100 else v
                print(f"  {k}: {val}")

    # 상세 출력 (source별 샘플 1건씩)
    elif args.detail:
        print("\n\n=== source별 샘플 1건 ===")
        seen = set()
        for p in payloads:
            src = p.get("source", "(없음)")
            if src in seen:
                continue
            seen.add(src)
            print(f"\n[{src}]")
            content = p.get("content", "")
            print(f"  content : {content[:80]}...")
            print(f"  scope   : {p.get('scope', '')}")
            print(f"  title   : {p.get('title', '')}")
            print(f"  chapter : {p.get('chapter', '')}")
            print(f"  article : {p.get('article', '')}")


if __name__ == "__main__":
    main()
