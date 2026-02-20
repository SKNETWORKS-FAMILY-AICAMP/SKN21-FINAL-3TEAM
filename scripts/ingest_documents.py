"""
문서 Ingestion 스크립트 — 파일 파싱 → 청킹 → Qdrant RAG 적재

사용법:
    cd SKN21-FINAL-3TEAM

    # 단일 파일 적재
    python scripts/ingest_documents.py data/regulations/dudu_tech_regulations.pdf

    # 디렉토리 내 모든 문서 적재
    python scripts/ingest_documents.py data/regulations/

    # 개인 문서 (scope=personal, user_id 지정)
    python scripts/ingest_documents.py my_doc.pdf --scope personal --user-id 1

    # 기존 데이터 삭제 후 재적재
    python scripts/ingest_documents.py data/regulations/ --force

    # 적재 후 검색 테스트
    python scripts/ingest_documents.py data/regulations/ --test "연차 휴가 몇 일"

지원 형식: .pdf, .docx, .txt
"""

import argparse
import sys
import os
import time
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# 지원하는 파일 확장자
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def collect_files(path: str) -> list[Path]:
    """파일 또는 디렉토리에서 지원 형식 파일 목록 수집"""
    target = Path(path)

    if target.is_file():
        if target.suffix.lower() in SUPPORTED_EXTENSIONS:
            return [target]
        else:
            print(f"[ERROR] 지원하지 않는 형식: {target.suffix}")
            sys.exit(1)

    if target.is_dir():
        files = []
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(target.glob(f"*{ext}"))
            files.extend(target.glob(f"**/*{ext}"))  # 하위 디렉토리 포함
        # 중복 제거 + 정렬
        files = sorted(set(files))
        if not files:
            print(f"[ERROR] {target} 에서 지원 형식 파일을 찾지 못했습니다.")
            sys.exit(1)
        return files

    print(f"[ERROR] 경로를 찾을 수 없습니다: {path}")
    sys.exit(1)


def parse_and_chunk(file_path: Path, scope: str, user_id: int | None) -> tuple[list[str], list[dict]]:
    """파일 파싱 + 청킹 → (documents, metadatas) 반환"""
    from ai.document_parser.parser import DocumentParser

    parser = DocumentParser()
    source = file_path.stem

    ext = file_path.suffix.lower()

    if ext == ".pdf":
        # PDF: Docling 파싱 → 조항 단위 청킹
        chunks = parser.parse_and_chunk(str(file_path))
    else:
        # DOCX/TXT: 파싱 → 단락 단위 청킹
        chunks = parser.parse_and_chunk(str(file_path))

    documents = []
    metadatas = []

    for chunk in chunks:
        documents.append(chunk["text"])
        meta = {
            "source": chunk.get("source", source),
            "scope": scope,
            "title": chunk.get("title", source),
            "chapter": chunk.get("chapter", ""),
            "article": chunk.get("article", ""),
        }
        if user_id is not None:
            meta["user_id"] = user_id
        metadatas.append(meta)

    return documents, metadatas


def ingest(
    files: list[Path],
    scope: str,
    user_id: int | None,
    force: bool,
    batch_size: int,
):
    """파일 목록을 파싱 → Qdrant에 적재"""
    from ai.rag.qdrant_pipeline import get_qdrant_pipeline, reset_qdrant_pipeline

    # 강제 재적재 시 파이프라인 리셋
    if force:
        print("[INFO] --force: 기존 파이프라인 리셋")
        reset_qdrant_pipeline()

    all_documents = []
    all_metadatas = []

    for i, file_path in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] 파싱 중: {file_path.name}")
        _t = time.time()

        try:
            docs, metas = parse_and_chunk(file_path, scope, user_id)
            all_documents.extend(docs)
            all_metadatas.extend(metas)
            elapsed = time.time() - _t
            print(f"  → {len(docs)}개 청크 ({elapsed:.1f}s)")
        except Exception as e:
            print(f"  [ERROR] 파싱 실패: {e}")
            continue

    if not all_documents:
        print("\n[ERROR] 적재할 문서가 없습니다.")
        return 0

    # 청크 통계
    lengths = [len(d) for d in all_documents]
    print(f"\n{'='*50}")
    print(f"총 {len(all_documents)}개 청크 준비 완료")
    print(f"  평균: {sum(lengths)//len(lengths)}자")
    print(f"  최소: {min(lengths)}자 / 최대: {max(lengths)}자")
    print(f"{'='*50}")

    # Qdrant 적재
    print("\n[INFO] Qdrant 적재 시작...")
    _t = time.time()

    pipeline = get_qdrant_pipeline()
    pipeline.add_documents(
        documents=all_documents,
        metadatas=all_metadatas,
        batch_size=batch_size,
    )

    elapsed = time.time() - _t
    print(f"[INFO] Qdrant 적재 완료: {len(all_documents)}개 문서 ({elapsed:.1f}s)")

    return len(all_documents)


def test_search(query: str, top_k: int = 5):
    """적재 후 검색 테스트"""
    from ai.rag.qdrant_pipeline import get_qdrant_pipeline

    print(f"\n{'='*50}")
    print(f"검색 테스트: '{query}'")
    print(f"{'='*50}")

    pipeline = get_qdrant_pipeline()
    results = pipeline.retrieve(query=query, top_k=top_k)

    if not results:
        print("  검색 결과 없음")
        return

    for i, r in enumerate(results, 1):
        source = r.get("source", "?")
        score = r.get("score", 0)
        content = r.get("content", "")[:150]
        print(f"\n  [{i}] {source} (score: {score:.4f})")
        print(f"      {content}...")


def main():
    parser = argparse.ArgumentParser(
        description="문서 파싱 → Qdrant RAG 적재",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/ingest_documents.py data/regulations/
  python scripts/ingest_documents.py doc.pdf --scope personal --user-id 1
  python scripts/ingest_documents.py data/regulations/ --force --test "연차 휴가"
        """,
    )
    parser.add_argument("path", help="파일 또는 디렉토리 경로")
    parser.add_argument("--scope", default="company", choices=["company", "personal"],
                        help="문서 범위 (기본: company)")
    parser.add_argument("--user-id", type=int, default=None,
                        help="개인 문서일 경우 user_id")
    parser.add_argument("--force", action="store_true",
                        help="기존 데이터 삭제 후 재적재")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="배치 크기 (기본: 50)")
    parser.add_argument("--test", type=str, default=None,
                        help="적재 후 검색 테스트 쿼리")

    args = parser.parse_args()

    # scope=personal인데 user-id 없으면 경고
    if args.scope == "personal" and args.user_id is None:
        print("[WARN] --scope personal에는 --user-id를 지정하는 것을 권장합니다.")

    print("="*50)
    print("문서 Ingestion 스크립트")
    print("="*50)

    # 1. 파일 수집
    files = collect_files(args.path)
    print(f"\n대상 파일 {len(files)}개:")
    for f in files:
        print(f"  - {f.name} ({f.suffix})")

    # 2. 파싱 + 적재
    count = ingest(
        files=files,
        scope=args.scope,
        user_id=args.user_id,
        force=args.force,
        batch_size=args.batch_size,
    )

    if count == 0:
        sys.exit(1)

    # 3. 검색 테스트 (선택)
    if args.test:
        test_search(args.test)

    print(f"\n완료!")


if __name__ == "__main__":
    main()
