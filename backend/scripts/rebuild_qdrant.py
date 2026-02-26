"""
Qdrant 데이터 전체 재정립 스크립트

컬렉션 삭제 후 data/regulations/ 파일 + DB 문서/회의록을 새 메타데이터 구조로 재업로드.
원본과 동일한 세밀한 조문 기반 청킹 적용.

새 메타데이터 구조:
  - source: "documents" | "regulations" (2개 고정)
  - doc_type: 세부 분류 (확장 자유)

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

# 파싱용 정규식
RE_CHAPTER = re.compile(r"^(제\s*\d+\s*장)\s*(.*)")
RE_ARTICLE = re.compile(r"^(제\s*\d+\s*조(?:의\d+)?)\s*(?:\(([^)]+)\))?\s*(.*)")
RE_APPENDIX = re.compile(r"^(부\s*칙|별\s*표|부록)")
RE_TOC_LINE = re.compile(r"^제\s*\d+\s*[조장절]\s")


def _classify_doc_type(filename: str) -> str:
    for key, dtype in FILE_DOC_TYPE.items():
        if key in filename:
            return dtype
    return "general"


def _split_by_bullets(text: str) -> list[str]:
    """● 불릿 기준으로 분할, 각 서브청크 200~400자 목표"""
    parts = re.split(r"(?=●)", text)
    if len(parts) <= 1:
        parts = re.split(r"(?<=다\.)\s*\n|(?<=한다\.)\s*\n|(?<=된다\.)\s*\n", text)

    result = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(current) + len(part) > 400 and current:
            result.append(current)
            current = part
        else:
            current = current + "\n" + part if current else part
    if current.strip():
        result.append(current)
    return result if result else [text]


def _chunk_by_articles(full_text: str, doc_type: str, reg_name: str) -> tuple[list[str], list[dict]]:
    """원본과 동일한 세밀한 조문 기반 청킹 (test_e2e_judgment.py 로직)"""
    lines = full_text.split("\n")
    chunks = []
    chunk_metas = []

    current_chapter = ""
    current_article = ""
    current_article_title = ""
    current_lines = []
    in_toc = False

    def _flush():
        nonlocal current_lines
        if not current_lines:
            return

        text = "\n".join(current_lines).strip()
        if len(text) < 30:
            current_lines = []
            return

        # 목차 감지
        non_empty = [l for l in current_lines if l.strip()]
        if non_empty:
            toc_ratio = sum(1 for l in non_empty if RE_TOC_LINE.match(l.strip())) / len(non_empty)
            if toc_ratio > 0.5 and len(non_empty) > 3:
                current_lines = []
                return

        title = current_article_title or current_chapter or reg_name

        # 긴 청크는 불릿 기준으로 서브 분할
        if len(text) > 400:
            sub_chunks = _split_by_bullets(text)
            for sub in sub_chunks:
                if len(sub.strip()) < 20:
                    continue
                chunks.append(sub.strip())
                chunk_metas.append({
                    "source": "regulations",
                    "doc_type": doc_type,
                    "scope": "company",
                    "title": title,
                    "chapter": current_chapter,
                    "article": current_article,
                    "category": doc_type,
                })
        else:
            chunks.append(text)
            chunk_metas.append({
                "source": "regulations",
                "doc_type": doc_type,
                "scope": "company",
                "title": title,
                "chapter": current_chapter,
                "article": current_article,
                "category": doc_type,
            })

        current_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 표지 감지
        if "듀듀 테크놀로지" in stripped or "Duedue Technology" in stripped:
            in_toc = True
            continue
        if in_toc and ("목 차" in stripped or "목차" in stripped):
            continue

        # 부록/부칙
        if RE_APPENDIX.match(stripped):
            _flush()
            current_article = stripped[:20]
            current_article_title = stripped[:20]
            current_lines = [stripped]
            continue

        # 장 헤더
        m_ch = RE_CHAPTER.match(stripped)
        if m_ch:
            _flush()
            current_chapter = f"{m_ch.group(1)} {m_ch.group(2)}".strip()
            in_toc = False
            current_lines = [stripped]
            current_article = ""
            current_article_title = ""
            continue

        # 조 헤더
        m_art = RE_ARTICLE.match(stripped)
        if m_art:
            _flush()
            current_article = m_art.group(1)
            current_article_title = m_art.group(2) or ""
            in_toc = False
            current_lines = [stripped]
            continue

        current_lines.append(stripped)

    _flush()
    return chunks, chunk_metas


def ingest_regulations(pipeline) -> int:
    """data/regulations/ 디렉토리에서 규정 파일 로드 → Qdrant 인덱싱"""
    reg_dir = project_root / "data" / "regulations"
    if not reg_dir.exists():
        print("  규정 디렉토리 없음")
        return 0

    all_chunks = []
    all_metas = []

    # 1. TXT 파일들 (조문 기반 세밀한 청킹)
    for txt_file in sorted(reg_dir.glob("*.txt")):
        text = txt_file.read_text(encoding="utf-8")
        reg_name = txt_file.stem
        doc_type = _classify_doc_type(reg_name)

        chunks, metas = _chunk_by_articles(text, doc_type, reg_name)
        all_chunks.extend(chunks)
        all_metas.extend(metas)
        print(f"    {txt_file.name}: {len(chunks)}개 청크 (doc_type={doc_type})")

    # 2. PDF 파일 (동일한 조문 기반 청킹)
    pdf_file = reg_dir / "dudu_tech_regulations.pdf"
    if pdf_file.exists():
        try:
            import fitz
            doc = fitz.open(str(pdf_file))
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            doc.close()

            chunks, metas = _chunk_by_articles(full_text, "IT", "듀듀테크 사내규정")
            all_chunks.extend(chunks)
            all_metas.extend(metas)
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

    # 3-1. 규정 (파일 기반, 세밀한 조문 청킹)
    print("  [규정] data/regulations/ 파일 로드 (조문 기반 세밀한 청킹)...")
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
