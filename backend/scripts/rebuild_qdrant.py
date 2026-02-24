"""
Qdrant 데이터 전체 재정립 스크립트

컬렉션 삭제 후 data/regulations/ 파일 + DB 문서/회의록을 새 메타데이터 구조로 재업로드.

새 메타데이터 구조:
  - source: "documents" | "regulations" (2개 고정)
  - doc_type: 세부 분류 (확장 자유)
    - documents → "general" / "meeting_minutes" / ...
    - regulations → "HR" / "IT" / "governance" 등

사용법:
    cd backend
    python -m scripts.rebuild_qdrant
"""
import asyncio
import re
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# 파일명 → doc_type 매핑
FILE_DOC_TYPE = {
    "dudu_tech_regulations": "IT",
    "개인정보처리규정": "IT",
    "교육훈련규정": "HR",
    "급여규정": "HR",
    "복리후생규정": "HR",
    "출장규정": "HR",
    "징계규정": "HR",
    "윤리강령": "governance",
}


def _classify_doc_type(filename: str) -> str:
    """파일명에서 doc_type 추출"""
    for key, dtype in FILE_DOC_TYPE.items():
        if key in filename:
            return dtype
    return "general"


def _chunk_text(text: str, title: str, doc_type: str, reg_name: str) -> tuple[list[str], list[dict]]:
    """규정 텍스트를 조문 단위로 청크 분할"""
    chunks = []
    metas = []

    # 조문 패턴으로 분할
    re_article = re.compile(r"^(제\s*\d+\s*조(?:의\d+)?)\s*(?:\(([^)]+)\))?\s*(.*)", re.MULTILINE)
    re_chapter = re.compile(r"^(제\s*\d+\s*장)\s*(.*)", re.MULTILINE)

    # 조문별 분할
    articles = re_article.split(text)

    # 조문이 없으면 전체를 하나의 청크로
    if len(articles) <= 1:
        for i in range(0, len(text), 500):
            chunk = text[i:i+500].strip()
            if len(chunk) < 20:
                continue
            chunks.append(chunk)
            metas.append({
                "source": "regulations",
                "doc_type": doc_type,
                "title": title,
                "chapter": "",
                "article": "",
                "category": doc_type,
                "scope": "company",
            })
        return chunks, metas

    # 간단한 청크: 줄 기반으로 분할
    current_chapter = ""
    current_article = ""
    current_article_title = ""
    current_lines = []

    def flush():
        nonlocal current_lines
        if not current_lines:
            return
        text_block = "\n".join(current_lines).strip()
        if len(text_block) < 20:
            current_lines = []
            return

        # 긴 텍스트는 분할
        if len(text_block) > 500:
            for i in range(0, len(text_block), 450):
                sub = text_block[i:i+450].strip()
                if len(sub) < 20:
                    continue
                chunks.append(sub)
                metas.append({
                    "source": "regulations",
                    "doc_type": doc_type,
                    "title": current_article_title or title,
                    "chapter": current_chapter,
                    "article": current_article,
                    "category": doc_type,
                    "scope": "company",
                })
        else:
            chunks.append(text_block)
            metas.append({
                "source": "regulations",
                "doc_type": doc_type,
                "title": current_article_title or title,
                "chapter": current_chapter,
                "article": current_article,
                "category": doc_type,
                "scope": "company",
            })
        current_lines = []

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        # 장 헤더
        m_ch = re_chapter.match(stripped)
        if m_ch:
            flush()
            current_chapter = f"{m_ch.group(1)} {m_ch.group(2)}".strip()
            current_lines = [stripped]
            current_article = ""
            current_article_title = ""
            continue

        # 조문 헤더
        m_art = re_article.match(stripped)
        if m_art:
            flush()
            current_article = m_art.group(1).strip()
            current_article_title = m_art.group(2).strip() if m_art.group(2) else ""
            current_lines = [stripped]
            continue

        current_lines.append(stripped)

    flush()
    return chunks, metas


def ingest_regulations(pipeline) -> int:
    """data/regulations/ 디렉토리에서 규정 파일 로드 → Qdrant 인덱싱"""
    reg_dir = project_root / "data" / "regulations"
    if not reg_dir.exists():
        print("  규정 디렉토리 없음")
        return 0

    all_chunks = []
    all_metas = []

    # 1. TXT 파일들
    for txt_file in sorted(reg_dir.glob("*.txt")):
        text = txt_file.read_text(encoding="utf-8")
        reg_name = txt_file.stem  # e.g. "급여규정_NC-HR-2026-002"
        doc_type = _classify_doc_type(reg_name)
        title = reg_name.split("_")[0]  # "급여규정"

        chunks, metas = _chunk_text(text, title, doc_type, reg_name)
        all_chunks.extend(chunks)
        all_metas.extend(metas)
        print(f"    {txt_file.name}: {len(chunks)}개 청크 (doc_type={doc_type})")

    # 2. PDF 파일 (dudu_tech_regulations.pdf)
    pdf_file = reg_dir / "dudu_tech_regulations.pdf"
    if pdf_file.exists():
        try:
            from ai.document_parser.regulation_parser import parse_regulation_pdf
            chunks, chunk_metas, _ = parse_regulation_pdf(str(pdf_file))

            # chunk_metas의 source를 "regulations"로 통일 (regulation_parser가 이미 수정됨)
            for meta in chunk_metas:
                meta["source"] = "regulations"
                meta["doc_type"] = "IT"
                if "category" not in meta:
                    meta["category"] = "IT"

            all_chunks.extend(chunks)
            all_metas.extend(chunk_metas)
            print(f"    {pdf_file.name}: {len(chunks)}개 청크 (doc_type=IT)")
        except Exception as e:
            print(f"    {pdf_file.name}: 파싱 실패 - {e}")

    if all_chunks:
        pipeline.add_documents(documents=all_chunks, metadatas=all_metas, batch_size=50)

    return len(all_chunks)


async def ingest_db_data(pipeline) -> tuple[int, int]:
    """DB에서 문서/회의록 로드 → Qdrant 인덱싱"""
    from sqlalchemy import select
    from app.db.session import async_session
    from app.models.document import Document
    from app.models.meeting import Meeting

    doc_count = 0
    mtg_count = 0

    async with async_session() as db:
        # 문서
        result = await db.execute(
            select(Document).where(
                Document.content.isnot(None),
                Document.status == "completed",
            )
        )
        documents = list(result.scalars().all())

        if documents:
            doc_texts = []
            doc_metas = []
            for doc in documents:
                if not doc.content or not doc.content.strip():
                    continue
                doc_texts.append(doc.content)
                doc_metas.append({
                    "source": "documents",
                    "doc_type": "general",
                    "title": doc.title,
                    "scope": doc.scope,
                    "user_id": str(doc.uploaded_by),
                    "document_id": doc.id,
                })
            if doc_texts:
                pipeline.add_documents(documents=doc_texts, metadatas=doc_metas)
                doc_count = len(doc_texts)

        # 회의록
        result = await db.execute(select(Meeting))
        meetings = list(result.scalars().all())

        if meetings:
            mtg_docs = []
            mtg_metas = []
            for mtg in meetings:
                content = mtg.raw_content or ""
                if mtg.summary:
                    content = f"{content}\n\n요약: {mtg.summary}"
                if not content.strip():
                    continue
                mtg_docs.append(content)
                mtg_metas.append({
                    "source": "documents",
                    "doc_type": "meeting_minutes",
                    "title": mtg.title,
                    "scope": "company",
                    "user_id": str(mtg.created_by),
                    "meeting_id": mtg.id,
                })
            if mtg_docs:
                pipeline.add_documents(documents=mtg_docs, metadatas=mtg_metas)
                mtg_count = len(mtg_docs)

    return doc_count, mtg_count


async def main():
    from ai.rag.qdrant_pipeline import get_qdrant_pipeline, reset_qdrant_pipeline
    import os
    import requests

    print("=" * 60)
    print("  Qdrant 데이터 전체 재정립")
    print("  source 2개 (documents / regulations) + doc_type")
    print("=" * 60)

    # 1. 파이프라인 초기화
    print("\n[1/4] Qdrant 파이프라인 초기화...")
    pipeline = get_qdrant_pipeline()

    # 2. 기존 데이터 전체 삭제 + 컬렉션 재생성
    print("[2/4] 기존 컬렉션 삭제 + 재생성...")
    pipeline.vector_store.delete_collection()
    reset_qdrant_pipeline()
    pipeline = get_qdrant_pipeline()
    print("  완료")

    # 3. 데이터 인덱싱
    print("\n[3/4] 데이터 인덱싱...")

    # 3-1. 규정 (파일 기반)
    print("  [규정] data/regulations/ 파일 로드...")
    reg_count = ingest_regulations(pipeline)
    print(f"  → 규정 총 {reg_count}개 청크 인덱싱 완료")

    # 3-2. 문서 + 회의록 (DB 기반)
    print("  [문서/회의록] DB 로드...")
    doc_count, mtg_count = await ingest_db_data(pipeline)
    print(f"  → 문서 {doc_count}건, 회의록 {mtg_count}건 인덱싱 완료")

    # 4. 검증
    print("\n[4/4] 검증...")
    total = pipeline.vector_store.count()
    print(f"  총 포인트: {total}")

    url = os.getenv("QDRANT_URL")
    key = os.getenv("QDRANT_API_KEY")
    headers = {"api-key": key, "Content-Type": "application/json"}

    for src in ["documents", "regulations"]:
        r = requests.post(
            f"{url}/collections/documents/points/count",
            headers=headers,
            json={"filter": {"must": [{"key": "source", "match": {"value": src}}]}},
            timeout=10,
        )
        cnt = r.json()["result"]["count"]
        print(f"  source={src}: {cnt}건")

    # doc_type별 카운트
    for dtype in ["HR", "IT", "governance", "general", "meeting_minutes"]:
        r = requests.post(
            f"{url}/collections/documents/points/count",
            headers=headers,
            json={"filter": {"must": [{"key": "doc_type", "match": {"value": dtype}}]}},
            timeout=10,
        )
        cnt = r.json()["result"]["count"]
        if cnt > 0:
            print(f"    doc_type={dtype}: {cnt}건")

    print("\n완료!")


if __name__ == "__main__":
    asyncio.run(main())
