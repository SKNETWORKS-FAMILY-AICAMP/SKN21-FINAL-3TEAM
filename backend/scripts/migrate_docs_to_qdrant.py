"""
기존 DB 문서를 Qdrant에 인덱싱하는 일회성 마이그레이션 스크립트.

사용법:
    cd backend
    python -m scripts.migrate_docs_to_qdrant

환경:
    .env에 QDRANT_URL, QDRANT_API_KEY, DATABASE_URL 필요
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")


async def main():
    from sqlalchemy import select
    from app.db.session import async_session
    from app.models.document import Document
    from ai.rag.qdrant_pipeline import get_qdrant_pipeline

    print("[마이그레이션] Qdrant 파이프라인 초기화 중...")
    pipeline = get_qdrant_pipeline()

    print("[마이그레이션] DB에서 content가 있는 문서 조회 중...")
    async with async_session() as db:
        result = await db.execute(
            select(Document).where(
                Document.content.isnot(None),
                Document.status == "completed",
            )
        )
        docs = list(result.scalars().all())

    if not docs:
        print("[마이그레이션] 인덱싱할 문서가 없습니다.")
        return

    print(f"[마이그레이션] {len(docs)}개 문서 인덱싱 시작...")

    documents = []
    metadatas = []
    for doc in docs:
        if not doc.content or not doc.content.strip():
            print(f"  건너뜀: document_id={doc.id} (빈 content)")
            continue
        documents.append(doc.content)
        metadatas.append({
            "source": "documents",
            "title": doc.title,
            "scope": doc.scope,
            "user_id": str(doc.uploaded_by),
            "document_id": doc.id,
        })

    if documents:
        pipeline.add_documents(documents=documents, metadatas=metadatas)
        print(f"[마이그레이션] {len(documents)}개 문서 Qdrant 인덱싱 완료!")
    else:
        print("[마이그레이션] 유효한 문서가 없습니다.")


if __name__ == "__main__":
    asyncio.run(main())
