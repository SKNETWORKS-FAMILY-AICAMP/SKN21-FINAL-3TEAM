"""
문서 파싱 상태 관리 서비스 (팀원 D 담당)

UI_UX.pdf: "[추가] 파싱 진행 상태 표시 ('파싱 중...' → '파싱 완료')"
요구사항: NF-PRF-002

파싱 상태 플로우:
  uploading → parsing → completed (또는 failed)

현재: 동기 처리이므로 upload_and_parse()에서 바로 completed/failed로 전환됨.
이 서비스는 프론트엔드 폴링용 상태 조회를 담당한다.
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


STATUS_UPLOADING = "uploading"
STATUS_PARSING = "parsing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


async def get_parsing_status(db: AsyncSession, document_id: int) -> dict:
    """
    파싱 상태 조회 (프론트에서 폴링)

    Returns:
        {
            "document_id": 123,
            "status": "completed",
            "progress": 100,
            "detected_template": None
        }
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")

    status = doc.status
    # processing → 매핑
    if status == "processing":
        status = STATUS_PARSING

    progress_map = {
        STATUS_UPLOADING: 0,
        STATUS_PARSING: 50,
        STATUS_COMPLETED: 100,
        STATUS_FAILED: 0,
        "processing": 50,
    }

    return {
        "document_id": doc.id,
        "status": status,
        "progress": progress_map.get(status, 0),
        "detected_template": None,
    }
