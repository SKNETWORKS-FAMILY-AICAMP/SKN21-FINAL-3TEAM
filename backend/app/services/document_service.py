"""
문서 서비스 (팀원 C/D 공동 담당)
- 파일 업로드, 텍스트 추출, 문서 CRUD
- Qdrant 인덱싱 (업로드 시 자동), RAG 검색 (내용)
"""
import os
import re
import uuid
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

from fastapi import UploadFile, HTTPException
from sqlalchemy import select, or_, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.config import get_settings

# PDF/DOCX 라이브러리 미리 import
try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

logger = logging.getLogger(__name__)


async def save_file(file: UploadFile, upload_dir: str) -> tuple[str, str]:
    """
    UploadFile을 디스크에 저장한다.

    Returns:
        (saved_path, file_type)
    """
    os.makedirs(upload_dir, exist_ok=True)

    original = file.filename or "unknown"
    ext = Path(original).suffix.lower()  # .pdf, .docx, .txt
    file_type = ext.lstrip(".")

    if file_type not in ("pdf", "docx", "txt"):
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식입니다: {ext}")

    unique_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(upload_dir, unique_name)

    content = await file.read()
    with open(saved_path, "wb") as f:
        f.write(content)

    return saved_path, file_type


def extract_text(file_path: str, file_type: str) -> str:
    """
    PDF / DOCX / TXT 파일에서 텍스트를 추출한다.
    """
    if file_type == "pdf":
        return _extract_pdf(file_path)
    elif file_type == "docx":
        return _extract_docx(file_path)
    elif file_type == "txt":
        return _extract_txt(file_path)
    else:
        raise ValueError(f"지원하지 않는 파일 타입: {file_type}")


def _extract_pdf(file_path: str) -> str:
    if not PDF_AVAILABLE:
        raise ImportError("PyMuPDF (fitz) is not installed. Please install it with: pip install PyMuPDF")

    try:
        text_parts: list[str] = []
        doc = fitz.open(file_path)

        for page in doc:
            text = page.get_text()
            text_parts.append(text)

        doc.close()
        result = "\n".join(text_parts)

        if not result.strip():
            raise ValueError("PDF extracted but content is empty")

        return result
    except Exception as e:
        raise ValueError(f"PDF extraction failed: {e}") from e


def _extract_docx(file_path: str) -> str:
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx is not installed. Please install it with: pip install python-docx")

    doc = DocxDocument(file_path)
    parts = []

    # 문단 텍스트 추출 (빈 문단 제외)
    para_texts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    parts.extend(para_texts)

    # 테이블 텍스트 추출 (doc.paragraphs는 테이블 내부 텍스트를 포함하지 않음)
    table_parts = []
    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                table_parts.append(" | ".join(row_cells))
    parts.extend(table_parts)

    result = "\n".join(parts)

    # DEBUG: python-docx 파싱 결과 출력
    print(f"\n{'='*60}")
    print(f"[DocxParser] DEBUG 파일: {file_path}")
    print(f"[DocxParser] 전체 단락 수: {len(doc.paragraphs)}, 비어있지 않은 단락: {len(para_texts)}")
    print(f"[DocxParser] 테이블 수: {len(doc.tables)}, 테이블 행 수: {len(table_parts)}")
    print(f"[DocxParser] 추출된 텍스트 총 길이: {len(result)}자")
    print(f"[DocxParser] 추출 내용 미리보기 (앞 500자):\n{result[:500]}")
    print(f"{'='*60}\n")

    return result


def _extract_txt(file_path: str) -> str:
    # UTF-8 시도, 실패하면 여러 인코딩 시도
    encodings = ['utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'cp949', 'euc-kr', 'latin-1']
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
                # 빈 문자열이 아닌 경우에만 반환
                if content.strip():
                    return content
        except (UnicodeDecodeError, UnicodeError):
            continue

    # 모든 인코딩 실패 시 에러
    raise ValueError("Unable to decode text file. File may be corrupted or in an unsupported encoding.")


async def upload_and_parse(
    db: AsyncSession,
    file: UploadFile,
    scope: str,
    user_id: int,
    team_name: str | None = None,
) -> Document:
    """
    파일 업로드 → 텍스트 추출 → DB 저장

    동기적으로 텍스트를 추출하고 status를 바로 completed로 변경한다.
    (Celery 없이 단순 처리)
    """
    settings = get_settings()

    # 1. 파일 저장
    saved_path, file_type = await save_file(file, settings.UPLOAD_DIR)

    title = Path(file.filename or "untitled").stem

    # 2. DB 레코드 생성 (status: processing)
    doc = Document(
        title=title,
        file_path=saved_path,
        file_type=file_type,
        scope=scope,
        team_name=team_name if scope == "team" else None,
        uploaded_by=user_id,
        status="processing",
    )
    db.add(doc)
    await db.flush()  # id 확보

    # 3. 텍스트 추출
    try:
        text = extract_text(saved_path, file_type)
        logger.info(f"텍스트 추출 완료: {len(text)}자, file={saved_path}")

        doc.content = text
        doc.status = "completed"

        # Qdrant에 인덱싱 (RAG 검색용)
        try:
            from ai.rag.qdrant_pipeline import get_qdrant_pipeline
            pipeline = get_qdrant_pipeline()
            pipeline.add_documents(
                documents=[text],
                metadatas=[{
                    "source": "documents",
                    "doc_type": "general",
                    "title": doc.title,
                    "scope": doc.scope,
                    "team_name": doc.team_name or "",
                    "user_id": str(user_id),
                    "document_id": doc.id,
                }],
            )
            logger.info(f"문서 Qdrant 인덱싱 완료: document_id={doc.id}, title={doc.title}")
        except Exception as qdrant_err:
            logger.warning(f"Qdrant 인덱싱 실패 (문서는 정상 저장됨): {qdrant_err}")

    except Exception as e:
        logger.error(f"텍스트 추출 실패: {e}", exc_info=True)
        doc.status = "failed"

    return doc


def _parse_date_query(keyword: str) -> tuple[date | None, date | None]:
    """날짜 검색 키워드를 파싱하여 (start_date, end_date) 반환.

    지원 형식:
    - 2026-02-24 / 2026.02.24 → 해당 일
    - 2026-02 / 2026.02 → 해당 월 전체
    - 2026 → 해당 연도 전체
    - 2월 → 현재 연도 해당 월
    """
    keyword = keyword.strip()

    # 2026-02-24 또는 2026.02.24
    m = re.match(r"^(\d{4})[-./](\d{1,2})[-./](\d{1,2})$", keyword)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            day = date(y, mo, d)
            return day, day
        except ValueError:
            return None, None

    # 2026-02 또는 2026.02
    m = re.match(r"^(\d{4})[-./](\d{1,2})$", keyword)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        try:
            start = date(y, mo, 1)
            # 다음 달 1일 - 1일 = 이번 달 마지막 날
            if mo == 12:
                end = date(y, 12, 31)
            else:
                end = date(y, mo + 1, 1)
                end = end - timedelta(days=1)
            return start, end
        except ValueError:
            return None, None

    # 2026
    m = re.match(r"^(\d{4})$", keyword)
    if m:
        y = int(m.group(1))
        return date(y, 1, 1), date(y, 12, 31)

    # N월 (현재 연도)
    m = re.match(r"^(\d{1,2})월$", keyword)
    if m:
        mo = int(m.group(1))
        y = datetime.now().year
        try:
            start = date(y, mo, 1)
            if mo == 12:
                end = date(y, 12, 31)
            else:
                end = date(y, mo + 1, 1)
                end = end - timedelta(days=1)
            return start, end
        except ValueError:
            return None, None

    return None, None


async def list_documents(
    db: AsyncSession,
    user_id: int,
    scope: str | None = None,
    keyword: str | None = None,
    search_type: str = "title",
    user_team: str | None = None,
) -> list[Document]:
    """문서 목록 조회 (scope, keyword, search_type 필터)

    Args:
        search_type: "title" (제목 ILIKE), "title_content" (제목+내용 ILIKE), "date" (날짜 범위)
        user_team: 유저 소속 팀 (team scope 필터링용)
    """
    stmt = select(Document)

    if scope == "team":
        # 팀 문서: 같은 팀의 team scope 문서만
        if user_team:
            stmt = stmt.where(
                (Document.scope == "team") & (Document.team_name == user_team)
            )
        else:
            # 팀 없는 유저는 빈 결과
            stmt = stmt.where(Document.id < 0)
    elif scope:
        stmt = stmt.where(Document.scope == scope)
    else:
        # scope 미지정 시: 회사 문서 + 본인 개인 문서 + 본인 팀 문서
        conditions = [
            Document.scope == "company",
            (Document.scope == "personal") & (Document.uploaded_by == user_id),
        ]
        if user_team:
            conditions.append(
                (Document.scope == "team") & (Document.team_name == user_team)
            )
        stmt = stmt.where(or_(*conditions))

    if keyword:
        if search_type == "title":
            stmt = stmt.where(Document.title.ilike(f"%{keyword}%"))

        elif search_type == "title_content":
            stmt = stmt.where(
                or_(
                    Document.title.ilike(f"%{keyword}%"),
                    Document.content.ilike(f"%{keyword}%"),
                )
            )

        elif search_type == "date":
            start_date, end_date = _parse_date_query(keyword)
            if start_date and end_date:
                stmt = stmt.where(
                    cast(Document.created_at, Date) >= start_date,
                    cast(Document.created_at, Date) <= end_date,
                )
            else:
                # 파싱 실패 시 빈 결과
                stmt = stmt.where(Document.id < 0)

    stmt = stmt.order_by(Document.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_document(db: AsyncSession, document_id: int) -> Document:
    """문서 상세 조회"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
    return doc


async def delete_document(
    db: AsyncSession,
    document_id: int,
    user_id: int,
) -> dict:
    """문서 삭제 (업로드한 사용자만 가능)"""
    doc = await get_document(db, document_id)

    if doc.uploaded_by != user_id:
        raise HTTPException(status_code=403, detail="본인이 업로드한 문서만 삭제할 수 있습니다")

    # 파일 삭제
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    # Qdrant에서 벡터 삭제
    try:
        from ai.rag.qdrant_pipeline import get_qdrant_pipeline
        pipeline = get_qdrant_pipeline()
        pipeline.vector_store.delete_by_filter({"document_id": document_id})
        pipeline.searcher.build_bm25_index()
        logger.info(f"Qdrant 문서 삭제 완료: document_id={document_id}")
    except Exception as e:
        logger.warning(f"Qdrant 문서 삭제 실패 (DB 삭제는 진행): {e}")

    await db.delete(doc)
    return {"message": "문서가 삭제되었습니다", "document_id": document_id}


async def generate_and_save(
    db: AsyncSession,
    user_input: str,
    user_id: int,
    template_type: str | None = None,
    template_id: int | None = None,
) -> tuple[Document, dict]:
    """
    Document Agent를 호출하여 문서를 생성하고 DB에 저장한다.

    Returns:
        (Document, agent_response)
    """
    import json as _json

    settings = get_settings()

    # 1. AgentState 구성
    state = {
        "user_input": user_input,
        "user_id": user_id,
        "intent": "doc_generate",
        "stream_mode": False,
        "template_type": template_type,
        "template_id": template_id,
        "context": [],
        "agent_response": {},
        "confidence": 0.0,
    }

    # 2. Document Agent 호출 (lazy import — backend 실행 시 ai/ 의존 최소화)
    from ai.agents.document_agent import document_agent
    state = await document_agent(state)

    agent_response = state.get("agent_response", {})

    # Agent가 에러를 반환한 경우
    if "error" in agent_response:
        raise HTTPException(status_code=500, detail=agent_response["error"])

    # 3. 생성된 데이터를 JSON 파일로 저장
    generated_dir = os.path.join(settings.UPLOAD_DIR, "generated")
    os.makedirs(generated_dir, exist_ok=True)

    file_name = f"{uuid.uuid4().hex}.json"
    file_path = os.path.join(generated_dir, file_name)

    data = agent_response.get("data", agent_response)
    with open(file_path, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)

    # 4. Document 레코드 생성
    resolved_type = agent_response.get("template_type", template_type or "report")
    title = data.get("title", f"{resolved_type} 문서")

    doc = Document(
        title=title,
        file_path=file_path,
        file_type="json",
        content=agent_response.get("preview", ""),
        scope="personal",
        uploaded_by=user_id,
        status="completed",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # agent_response의 mock ID를 실제 ID로 교체
    agent_response["document_id"] = doc.id
    agent_response["download_url"] = f"/api/v1/documents/{doc.id}/download"

    logger.info(f"문서 생성 완료: document_id={doc.id}, template_type={resolved_type}")
    return doc, agent_response
