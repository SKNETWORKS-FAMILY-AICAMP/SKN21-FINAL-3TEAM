"""
source="documents"이지만 document_id=None인 Qdrant 포인트를 DB와 매핑하여 재인덱싱하는 스크립트

실행 방법 (프로젝트 루트에서):
    python -m ai.tests.reindex_documents

동작:
  1. Qdrant에서 source="documents" & document_id=None 포인트 수집
  2. DB에서 status="completed" 문서 조회 → title 기준 매핑
  3. 매핑 성공: 기존 포인트 삭제 → document_id 포함 재인덱싱
  4. 매핑 실패(DB 없음): DB Document 레코드 신규 생성 → 인덱싱
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backend"))

from dotenv import load_dotenv
load_dotenv()

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointIdsList

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "documents"

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def fetch_orphaned_points() -> list:
    """document_id=None인 source='documents' 포인트 전체 수집"""
    source_filter = Filter(
        must=[FieldCondition(key="source", match=MatchValue(value="documents"))]
    )
    all_points = []
    offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=source_filter,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        all_points.extend(points)
        if next_offset is None:
            break
        offset = next_offset

    return [p for p in all_points if not p.payload.get("document_id")]


async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.models.document import Document

    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/workflow_agent")
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # ── 1. 고아 포인트 수집 ──────────────────────────────────────────
    print("=" * 60)
    print("1. Qdrant 고아 포인트(document_id=None) 수집 중...")
    orphaned = fetch_orphaned_points()
    print(f"   고아 포인트 수: {len(orphaned)}")
    if not orphaned:
        print("   재인덱싱할 포인트 없음. 종료.")
        await engine.dispose()
        return

    # title 기준으로 그룹화
    title_to_points: dict[str, list] = {}
    for p in orphaned:
        title = p.payload.get("title", "")
        title_to_points.setdefault(title, []).append(p)
    print(f"   고유 title 수: {len(title_to_points)}")

    # ── 2. DB 문서 조회 ──────────────────────────────────────────────
    print("\n2. DB 완료 문서 조회 중...")
    async with async_session() as session:
        result = await session.execute(
            select(Document).where(Document.status == "completed")
        )
        db_docs = result.scalars().all()
    db_title_map = {doc.title: doc for doc in db_docs}
    print(f"   DB 완료 문서 수: {len(db_docs)}")

    # ── 3. Qdrant 파이프라인 초기화 ──────────────────────────────────
    print("\n3. Qdrant 파이프라인 초기화 중...")
    from ai.rag.qdrant_pipeline import get_qdrant_pipeline
    pipeline = get_qdrant_pipeline()
    print("   초기화 완료")

    # ── 4. 매핑 및 재인덱싱 ──────────────────────────────────────────
    print("\n4. 재인덱싱 시작...")
    matched_count = 0
    created_count = 0
    skipped_count = 0

    async with async_session() as session:
        for title, points in title_to_points.items():
            point_ids = [p.id for p in points]
            # 대표 포인트에서 payload 추출
            payload = points[0].payload
            content = payload.get("content", "")
            scope = payload.get("scope", "company")
            uid_str = payload.get("user_id", "1")

            if not content:
                print(f"   [SKIP] '{title}' — content 없음")
                skipped_count += 1
                continue

            # DB에서 title 매핑 시도
            db_doc = db_title_map.get(title)

            if db_doc is None:
                # DB 레코드 없음 → 신규 생성
                try:
                    user_id_int = int(uid_str) if uid_str else 1
                except ValueError:
                    user_id_int = 1

                new_doc = Document(
                    title=title,
                    file_path="qdrant_reimport",
                    file_type="txt",
                    content=content,
                    scope=scope,
                    uploaded_by=user_id_int,
                    status="completed",
                )
                session.add(new_doc)
                await session.flush()  # id 확보
                db_doc = new_doc
                created_count += 1
                print(f"   [CREATE] '{title}' -> document_id={db_doc.id}")
            else:
                matched_count += 1
                print(f"   [MATCH]  '{title}' -> document_id={db_doc.id}")

            # 기존 고아 포인트 삭제
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=PointIdsList(points=point_ids),
            )

            # document_id 포함하여 재인덱싱
            pipeline.add_documents(
                documents=[content],
                metadatas=[{
                    "source": "documents",
                    "doc_type": "general",
                    "title": db_doc.title,
                    "scope": db_doc.scope,
                    "user_id": str(db_doc.uploaded_by),
                    "document_id": db_doc.id,
                }],
            )

        await session.commit()

    # ── 5. 결과 요약 ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"완료!")
    print(f"  DB 매핑 성공  : {matched_count}개")
    print(f"  DB 레코드 신규 생성: {created_count}개")
    print(f"  content 없어 스킵: {skipped_count}개")
    print(f"  총 재인덱싱   : {matched_count + created_count}개")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
