"""
문서 서비스 (팀원 C/D 공동 담당)
- 파일 업로드, 텍스트 추출, 문서 CRUD
"""
import os
import uuid
import logging
from pathlib import Path

from fastapi import UploadFile, HTTPException
from sqlalchemy import select, or_
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
    return "\n".join(p.text for p in doc.paragraphs)


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
    raise ValueError(f"Unable to decode text file. File may be corrupted or in an unsupported encoding.")


async def upload_and_parse(
    db: AsyncSession,
    file: UploadFile,
    scope: str,
    user_id: int,
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
        uploaded_by=user_id,
        status="processing",
    )
    db.add(doc)
    await db.flush()  # id 확보

    # 3. 텍스트 추출
    try:
        with open('/tmp/upload_debug.log', 'a') as log:
            log.write(f"\n[DEBUG] Starting extraction: {saved_path} (type: {file_type})\n")
            log.flush()

        text = extract_text(saved_path, file_type)

        with open('/tmp/upload_debug.log', 'a') as log:
            log.write(f"[DEBUG] Extracted {len(text)} chars\n")
            log.flush()

        doc.content = text
        doc.status = "completed"

        with open('/tmp/upload_debug.log', 'a') as log:
            log.write(f"[DEBUG] Status set to completed\n")
            log.flush()
    except Exception as e:
        with open('/tmp/upload_debug.log', 'a') as log:
            import traceback
            log.write(f"[ERROR] Text extraction failed: {e}\n")
            log.write(traceback.format_exc())
            log.flush()
        doc.status = "failed"

    return doc


async def list_documents(
    db: AsyncSession,
    user_id: int,
    scope: str | None = None,
    keyword: str | None = None,
) -> list[Document]:
    """문서 목록 조회 (scope, keyword 필터)"""
    stmt = select(Document)

    if scope:
        stmt = stmt.where(Document.scope == scope)
    else:
        # scope 미지정 시: 회사 문서 + 본인 개인 문서
        stmt = stmt.where(
            or_(
                Document.scope == "company",
                (Document.scope == "personal") & (Document.uploaded_by == user_id),
            )
        )

    if keyword:
        stmt = stmt.where(Document.title.ilike(f"%{keyword}%"))

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

    await db.delete(doc)
    return {"message": "문서가 삭제되었습니다", "document_id": document_id}
