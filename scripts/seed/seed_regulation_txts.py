"""
규정 txt 파일 → DB + Qdrant 인제스트 스크립트

data/regulations/*.txt 파일을 파싱하여:
1. PostgreSQL regulations 테이블에 조항별 삽입 (멱등)
2. Qdrant에 RAG용 청크 인덱싱

※ 인사규정(NC-HR-2026-001)은 이미 seed_regulations.py로 DB에 들어가 있으므로 스킵
※ IT보안규정(NC-IT-2026-002)은 인사규정 PDF의 13~30조와 내용 동일하므로 스킵

실행: python scripts/seed/seed_regulation_txts.py (프로젝트 루트에서)
"""
import asyncio
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# 스킵할 파일 (이미 DB에 있는 데이터)
SKIP_FILES = {
    "인사규정_NC-HR-2026-001.txt",   # seed_regulations.py로 이미 삽입
    "IT보안규정_NC-IT-2026-002.txt",  # 인사규정 PDF 13~30조와 동일
}

# 조항 파싱 정규식
RE_ARTICLE = re.compile(r"^(제\s*\d+(?:조의?\d*)?)\s*(?:\(([^)]+)\))?\s*(.*)")
RE_CHAPTER = re.compile(r"^(제\s*\d+\s*장)\s*(.*)")
RE_APPENDIX = re.compile(r"^(부\s*칙)")


def parse_txt_file(filepath: Path) -> dict:
    """txt 파일을 파싱하여 규정명, 문서번호, 조항 리스트 반환"""
    lines = filepath.read_text(encoding="utf-8").splitlines()

    # 헤더 파싱 (1~4줄)
    reg_name = lines[0].strip() if len(lines) > 0 else ""
    doc_number = ""
    for line in lines[1:5]:
        if line.strip().startswith("문서번호:"):
            doc_number = line.strip().replace("문서번호:", "").strip()
            break

    # 조항 파싱
    articles = []
    current_chapter = ""
    current_article_num = ""
    current_article_title = ""
    current_lines = []

    def flush():
        nonlocal current_lines
        if not current_lines or not current_article_num:
            current_lines = []
            return

        content = "\n".join(current_lines).strip()
        if len(content) < 10:
            current_lines = []
            return

        articles.append({
            "article_number": current_article_num,
            "article_title": current_article_title,
            "chapter": current_chapter,
            "content": content,
        })
        current_lines = []

    for line in lines[4:]:  # 헤더 스킵
        stripped = line.strip()
        if not stripped:
            continue

        # 부칙
        if RE_APPENDIX.match(stripped):
            flush()
            current_article_num = "부칙"
            current_article_title = "부칙"
            current_lines = [stripped]
            continue

        # 장 헤더
        m_ch = RE_CHAPTER.match(stripped)
        if m_ch:
            flush()
            current_chapter = f"{m_ch.group(1)} {m_ch.group(2)}".strip()
            current_article_num = ""
            current_article_title = ""
            continue

        # 조항 헤더
        m_art = RE_ARTICLE.match(stripped)
        if m_art:
            flush()
            current_article_num = m_art.group(1).replace(" ", "")  # "제 1 조" → "제1조"
            current_article_title = m_art.group(2) or ""
            current_lines = [stripped]
            continue

        current_lines.append(stripped)

    flush()

    return {
        "reg_name": reg_name,
        "doc_number": doc_number,
        "articles": articles,
    }


async def seed_db(all_regulations: list):
    """DB에 규정 조항 삽입 (멱등: article_number 중복 시 스킵)"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from app.models.regulation import Regulation

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL을 .env에 설정해야 합니다.")

    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)

    # asyncpg는 ?ssl=require 쿼리 파라미터를 직접 처리 못함 → connect_args로 전달
    connect_args = {}
    if "ssl=require" in database_url:
        database_url = database_url.replace("?ssl=require", "").replace("&ssl=require", "")
        connect_args["ssl"] = "require"

    engine = create_async_engine(database_url, echo=False, connect_args=connect_args)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    inserted = 0
    skipped = 0

    async with async_session() as session:
        for reg_data in all_regulations:
            reg_name = reg_data["reg_name"]

            for art in reg_data["articles"]:
                # 고유 article_number: "윤리강령 제1조"
                qualified_num = f"{reg_name} {art['article_number']}"

                # 중복 체크
                result = await session.execute(
                    select(Regulation).where(Regulation.article_number == qualified_num)
                )
                if result.scalar_one_or_none():
                    skipped += 1
                    continue

                # title: "윤리강령 제1조 (목적)" — 문서번호 없이 깔끔하게
                if art["article_title"]:
                    title = f"{reg_name} {art['article_number']} ({art['article_title']})"
                else:
                    title = f"{reg_name} {art['article_number']}"

                reg = Regulation(
                    title=title,
                    category=reg_name,
                    article_number=qualified_num,
                    content=art["content"],
                    version="1.0",
                )
                session.add(reg)
                inserted += 1

        await session.commit()

    await engine.dispose()
    print(f"[DB] 삽입: {inserted}개, 스킵(중복): {skipped}개")
    return inserted


def seed_qdrant(all_regulations: list):
    """Qdrant에 규정 조항 인덱싱"""
    from ai.rag.qdrant_pipeline import get_qdrant_pipeline

    pipeline = get_qdrant_pipeline()

    documents = []
    metadatas = []

    for reg_data in all_regulations:
        reg_name = reg_data["reg_name"]

        for art in reg_data["articles"]:
            documents.append(art["content"])
            metadatas.append({
                "source": "regulations",
                "title": f"{reg_name} {art['article_number']}",
                "article_number": f"{reg_name} {art['article_number']}",
                "category": reg_name,
                "chapter": art.get("chapter", ""),
                "scope": "company",
            })

    if documents:
        pipeline.add_documents(documents=documents, metadatas=metadatas)
        print(f"[Qdrant] {len(documents)}개 규정 조항 인덱싱 완료")
    else:
        print("[Qdrant] 인덱싱할 조항 없음")


async def main():
    data_dir = PROJECT_ROOT / "data" / "regulations"
    txt_files = sorted(data_dir.glob("*.txt"))

    if not txt_files:
        print("txt 파일이 없습니다.")
        return

    print("=== 규정 txt 인제스트 시작 ===\n")

    all_regulations = []
    for f in txt_files:
        if f.name in SKIP_FILES:
            print(f"  [스킵] {f.name} (이미 DB에 존재)")
            continue

        reg_data = parse_txt_file(f)
        print(f"  [파싱] {f.name} → {reg_data['reg_name']} ({len(reg_data['articles'])}개 조항)")
        all_regulations.append(reg_data)

    if not all_regulations:
        print("\n인제스트할 규정이 없습니다.")
        return

    total_articles = sum(len(r["articles"]) for r in all_regulations)
    print(f"\n총 {len(all_regulations)}개 규정, {total_articles}개 조항\n")

    # DB 삽입
    print("[DB] 삽입 시작...")
    await seed_db(all_regulations)

    # Qdrant 인덱싱
    print("\n[Qdrant] 인덱싱 시작...")
    try:
        seed_qdrant(all_regulations)
    except Exception as e:
        print(f"[Qdrant] 오류 (나중에 재시도): {e}")

    print("\n=== 인제스트 완료 ===")
    print("검증:")
    print("  - GET /api/v1/regulations → 새 규정 포함 확인")
    print("  - 챗봇에 '윤리강령 알려줘' 질문 → RAG 검색 확인")


if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
