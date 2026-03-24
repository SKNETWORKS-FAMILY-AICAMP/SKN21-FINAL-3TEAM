"""
규정 데이터 시드 스크립트
- DB에 30개 조항 삽입 (멱등: article_number 중복 시 스킵)
- Qdrant에 재인덱싱 (source="regulations" 포인트 전체 삭제 후 재삽입)

실행 방법: python scripts/seed_regulations.py (프로젝트 루트에서)
"""
import asyncio
import os
import re
import sys

# 프로젝트 루트와 backend/ 디렉토리를 sys.path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))

from dotenv import load_dotenv

load_dotenv()


# 조항 번호 → 카테고리 분류
def get_category(article_name: str) -> str:
    match = re.search(r"제(\d+)조", article_name)
    if not match:
        return "기타"
    num = int(match.group(1))
    if num <= 3:
        return "총칙"
    elif num <= 9:
        return "인사"
    elif num <= 12:
        return "복무"
    elif num <= 29:
        return "정보보안"
    else:
        return "제재"


async def seed_db():
    """DB에 30개 규정 조항 삽입 (멱등)"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select

    # 여기서 import하여 sys.path 설정 이후에 로드
    from app.models.regulation import Regulation
    from scripts.benchmark.regulation_texts import REGULATION_TEXTS

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL을 .env에 설정해야 합니다.")

    # asyncpg 드라이버 사용
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    inserted = 0
    skipped = 0

    async with async_session() as session:
        for article_name, content in REGULATION_TEXTS.items():
            # article_number 추출 (예: "제1조")
            m = re.search(r"제\d+조", article_name)
            article_number = m.group(0) if m else article_name

            # 중복 체크
            result = await session.execute(
                select(Regulation).where(Regulation.article_number == article_number)
            )
            existing = result.scalar_one_or_none()
            if existing:
                skipped += 1
                continue

            category = get_category(article_name)
            reg = Regulation(
                title=article_name,
                category=category,
                article_number=article_number,
                content=content,
                version="1.0",
            )
            session.add(reg)
            inserted += 1

        await session.commit()

    print(f"[DB] 삽입: {inserted}개, 스킵(중복): {skipped}개")
    return inserted + skipped  # 전체 행 수


def seed_qdrant():
    """Qdrant에 규정 조항 재인덱싱 (source='regulations' 전체 삭제 후 재삽입)"""
    from ai.rag.qdrant_pipeline import get_qdrant_pipeline
    from scripts.benchmark.regulation_texts import REGULATION_TEXTS

    pipeline = get_qdrant_pipeline()

    # 기존 regulations 포인트 전체 삭제
    print("[Qdrant] source='regulations' 포인트 삭제 중...")
    pipeline.vector_store.delete_by_filter({"source": "regulations"})
    print("[Qdrant] 기존 규정 포인트 삭제 완료")

    documents = []
    metadatas = []

    for article_name, content in REGULATION_TEXTS.items():
        m = re.search(r"제\d+조", article_name)
        article_number = m.group(0) if m else article_name
        category = get_category(article_name)

        documents.append(content)
        metadatas.append({
            "source": "regulations",
            "title": article_name,
            "article_number": article_number,
            "category": category,
            "scope": "company",
        })

    pipeline.add_documents(documents=documents, metadatas=metadatas)
    print(f"[Qdrant] {len(documents)}개 규정 조항 인덱싱 완료")


async def main():
    print("=== 규정 데이터 시드 시작 ===")
    total = await seed_db()
    print(f"[DB] 총 {total}개 조항 확인 완료")

    print("\n[Qdrant] 재인덱싱 시작...")
    seed_qdrant()

    print("\n=== 시드 완료 ===")
    print("검증:")
    print("  - GET /api/v1/regulations 호출 → 30개 JSON 확인")
    print("  - Admin 페이지 → 규정 목록 확인")


if __name__ == "__main__":
    asyncio.run(main())
