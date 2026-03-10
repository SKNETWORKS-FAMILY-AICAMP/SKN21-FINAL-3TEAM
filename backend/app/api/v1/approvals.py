"""
Approval Request API (팀원 D 담당)
- 결재/승인 요청 CRUD
- 같은 팀 소속끼리 공유
- AI 기반 요청 추천
"""
import json
import logging
import mimetypes
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.approval_request import ApprovalRequest
from app.models.pipeline_task import PipelineTask
from app.models.schedule import Schedule

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "approvals"
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _serialize_approval(i, users_map=None):
    """공통 직렬화 헬퍼"""
    user = (users_map or {}).get(i.requester_id)
    target_user = (users_map or {}).get(i.target_user_id) if i.target_user_id else None
    return {
        "id": i.id,
        "type": i.type,
        "title": i.title,
        "detail": i.detail,
        "status": i.status,
        "requester_id": i.requester_id,
        "requester_name": user.name if user else None,
        "requester_avatar": user.avatar if user else None,
        "target_team": i.target_team,
        "target_user_id": i.target_user_id,
        "target_user_name": target_user.name if target_user else None,
        "target_user_avatar": target_user.avatar if target_user else None,
        "file_name": i.file_name,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


async def _get_users_map(db, items):
    user_ids = set()
    for i in items:
        user_ids.add(i.requester_id)
        if i.target_user_id:
            user_ids.add(i.target_user_id)
    user_ids = list(user_ids)
    users_map = {}
    if user_ids:
        users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in users_result.scalars().all():
            users_map[u.id] = u
    return users_map


# ── Endpoints ──

@router.get("/")
async def list_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내가 받은 pending 요청 목록 (나에게 보내진 것 또는 내 팀/전체 대상)"""
    query = (
        select(ApprovalRequest)
        .where(
            ApprovalRequest.status == "pending",
            ApprovalRequest.requester_id != current_user.id,  # 내가 보낸 건 제외
            or_(
                ApprovalRequest.target_user_id == current_user.id,  # 나에게 직접 보낸 것
                and_(
                    ApprovalRequest.target_user_id.is_(None),
                    or_(
                        ApprovalRequest.target_team == current_user.team,  # 내 팀 대상
                        ApprovalRequest.target_team.is_(None),  # 전체 대상
                    ),
                ),
            ),
        )
        .order_by(ApprovalRequest.created_at.desc())
    )
    result = await db.execute(query)
    items = result.scalars().all()
    users_map = await _get_users_map(db, items)
    return [_serialize_approval(i, users_map) for i in items]


@router.get("/history")
async def list_approval_history(
    status: str = "approved",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내가 보낸 요청 중 처리 완료된 목록 (approved / rejected)"""
    if status not in ("approved", "rejected"):
        status = "approved"
    query = (
        select(ApprovalRequest)
        .where(
            ApprovalRequest.status == status,
            ApprovalRequest.requester_id == current_user.id,  # 내가 보낸 것만
        )
        .order_by(ApprovalRequest.updated_at.desc())
    )
    result = await db.execute(query)
    items = result.scalars().all()
    users_map = await _get_users_map(db, items)
    return [_serialize_approval(i, users_map) for i in items]


@router.post("/", status_code=201)
async def create_approval(
    type: str = Form(...),
    title: str = Form(...),
    detail: Optional[str] = Form(None),
    target_team: Optional[str] = Form(None),
    target_user_id: Optional[int] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """새 결재/승인 요청 생성 (파일 첨부 가능, 대상 팀/팀원 지정)"""
    saved_path = None
    saved_name = None

    if file and file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"허용되지 않는 파일 형식입니다: {ext}")
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        saved_path = str(UPLOAD_DIR / unique_name)
        content = await file.read()
        with open(saved_path, "wb") as f:
            f.write(content)
        saved_name = file.filename

    approval = ApprovalRequest(
        type=type,
        title=title,
        detail=detail,
        status="pending",
        requester_id=current_user.id,
        target_team=target_team or current_user.team,
        target_user_id=target_user_id,
        file_path=saved_path,
        file_name=saved_name,
    )
    db.add(approval)
    await db.flush()
    return {
        "id": approval.id,
        "type": approval.type,
        "title": approval.title,
        "status": approval.status,
        "file_name": approval.file_name,
    }


@router.get("/{approval_id}/file")
async def download_approval_file(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """첨부파일 다운로드"""
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    if not approval.file_path or not os.path.exists(approval.file_path):
        raise HTTPException(status_code=404, detail="첨부파일이 없습니다")

    mime_type, _ = mimetypes.guess_type(approval.file_name or "")
    return FileResponse(
        path=approval.file_path,
        filename=approval.file_name or "attachment",
        media_type=mime_type or "application/octet-stream",
    )


@router.put("/{approval_id}/approve")
async def approve_request(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """요청 승인"""
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="이미 처리된 요청입니다")

    approval.status = "approved"
    await db.flush()
    return {"id": approval.id, "status": "approved"}


@router.put("/{approval_id}/reject")
async def reject_request(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """요청 거절"""
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="이미 처리된 요청입니다")

    approval.status = "rejected"
    await db.flush()
    return {"id": approval.id, "status": "rejected"}


@router.delete("/{approval_id}")
async def delete_approval(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """요청 삭제 (본인이 올린 요청만)"""
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    if approval.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인이 올린 요청만 삭제할 수 있습니다")

    # 첨부파일도 삭제
    if approval.file_path and os.path.exists(approval.file_path):
        os.remove(approval.file_path)

    await db.delete(approval)
    await db.flush()
    return {"deleted": True, "id": approval_id}


@router.put("/{approval_id}")
async def update_approval(
    approval_id: int,
    title: str = Form(None),
    detail: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """요청 수정 (본인이 올린 요청만)"""
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    if approval.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인이 올린 요청만 수정할 수 있습니다")

    if title is not None:
        approval.title = title
    if detail is not None:
        approval.detail = detail
    await db.flush()

    users_map = await _get_users_map(db, [approval])
    return _serialize_approval(approval, users_map)


@router.post("/seed", status_code=201)
async def seed_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """초기 샘플 데이터 시드 (기존 pending 없을 때만) — 윤경은(영업팀)이 보낸 것으로 생성"""
    existing = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.status == "pending").limit(1)
    )
    if existing.scalar_one_or_none():
        return {"seeded": 0, "message": "이미 pending 데이터가 있습니다"}

    # 윤경은 계정 찾기 (없으면 현재 사용자로 폴백)
    sender = current_user
    kyeongeun_result = await db.execute(
        select(User).where(User.name == "윤경은").limit(1)
    )
    kyeongeun = kyeongeun_result.scalar_one_or_none()
    if kyeongeun:
        sender = kyeongeun

    samples = [
        {"type": "leave", "title": "연차 신청서", "detail": "3일 (Feb 12 - Feb 14)"},
        {"type": "review", "title": "PR 리뷰 요청", "detail": "feat/auth-module #42"},
        {"type": "budget", "title": "품의서 결재", "detail": "디자인 에셋 구매 (₩150,000)"},
    ]
    for s in samples:
        db.add(ApprovalRequest(
            type=s["type"],
            title=s["title"],
            detail=s["detail"],
            status="pending",
            requester_id=sender.id,
            target_team=sender.team or "영업",
        ))
    await db.flush()
    return {"seeded": len(samples), "sender": sender.name}


@router.post("/checklist")
async def generate_checklist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI가 일정 + 파이프라인을 분석하여 할 일 체크리스트 생성"""
    from datetime import datetime, timedelta

    pipeline_tasks = []
    schedules = []
    stage_counts = {"todo": 0, "in_progress": 0, "review": 0, "done": 0}

    # 1. 데이터 수집
    try:
        task_query = select(PipelineTask).order_by(PipelineTask.created_at.desc())
        if current_user.team:
            task_query = task_query.where(
                or_(
                    PipelineTask.team == current_user.team,
                    PipelineTask.assignee == current_user.name,
                )
            )
        else:
            task_query = task_query.where(
                or_(
                    PipelineTask.created_by == current_user.id,
                    PipelineTask.assignee == current_user.name,
                )
            )
        task_result = await db.execute(task_query)
        pipeline_tasks = task_result.scalars().all()
    except Exception as e:
        logger.error(f"체크리스트: 파이프라인 조회 실패: {e}")

    try:
        now = datetime.now()
        week_later = now + timedelta(days=7)
        schedule_query = (
            select(Schedule)
            .where(
                Schedule.user_id == current_user.id,
                Schedule.start_time >= now,
                Schedule.start_time <= week_later,
            )
            .order_by(Schedule.start_time)
        )
        schedule_result = await db.execute(schedule_query)
        schedules = schedule_result.scalars().all()
    except Exception as e:
        logger.error(f"체크리스트: 일정 조회 실패: {e}")

    # 2. 컨텍스트 구성
    now = datetime.now()
    task_summary = []
    for t in pipeline_tasks:
        stage_counts[t.stage] = stage_counts.get(t.stage, 0) + 1
        task_summary.append({
            "title": t.title,
            "stage": t.stage,
            "priority": t.priority,
            "assignee": t.assignee,
            "due_date": t.due_date.strftime("%Y-%m-%d") if t.due_date else None,
            "project": t.project,
        })

    schedule_summary = []
    for s in schedules:
        schedule_summary.append({
            "title": s.title,
            "start": s.start_time.strftime("%Y-%m-%d %H:%M") if s.start_time else None,
            "end": s.end_time.strftime("%Y-%m-%d %H:%M") if s.end_time else None,
            "type": s.schedule_type,
        })

    context = f"""## 현재 사용자 정보
- 이름: {current_user.name}
- 팀: {current_user.team or '없음'}
- 오늘 날짜: {now.strftime('%Y-%m-%d %A')}

## 파이프라인 태스크 현황
- 전체: {len(pipeline_tasks)}개
- To Do: {stage_counts['todo']}개, In Progress: {stage_counts['in_progress']}개, Review: {stage_counts['review']}개, Done: {stage_counts['done']}개
- 태스크 상세 (진행 중 + 리뷰 + 할 일):
{json.dumps([t for t in task_summary if t['stage'] != 'done'][:15], ensure_ascii=False, indent=2)}

## 향후 7일 캘린더 일정
{json.dumps(schedule_summary, ensure_ascii=False, indent=2) if schedule_summary else '예정된 일정 없음'}
"""

    # 3. LLM 호출
    try:
        from ai.llm import get_llm
        from ai.llm.prompts import SCHEDULE_CHECKLIST_SYSTEM_PROMPT

        llm = get_llm()
        response = await llm.generate(
            prompt=context,
            system_prompt=SCHEDULE_CHECKLIST_SYSTEM_PROMPT,
            json_mode=True,
            temperature=0.3,
            max_tokens=1500,
        )

        result = json.loads(response.content)
        return {
            "checklist": result.get("checklist", []),
            "context": {
                "total_tasks": len(pipeline_tasks),
                "stage_counts": stage_counts,
                "upcoming_events": len(schedule_summary),
            },
        }
    except Exception as e:
        logger.error(f"체크리스트 AI 생성 실패: {e}", exc_info=True)

    # 4. LLM 실패 시 규칙 기반 폴백
    fallback = []

    # 오늘 일정 기반
    today_str = now.strftime("%Y-%m-%d")
    for s in schedule_summary:
        if s["start"] and s["start"].startswith(today_str):
            fallback.append({
                "title": f"{s['title']} 참석 준비",
                "category": "meeting",
                "priority": "high",
                "due": "오늘",
                "related": s["title"],
            })

    # 리뷰 태스크
    for t in task_summary:
        if t["stage"] == "review":
            fallback.append({
                "title": f"리뷰 확인: {t['title']}",
                "category": "review",
                "priority": "high",
                "due": "오늘",
                "related": t["title"],
            })

    # 진행 중 태스크
    for t in task_summary:
        if t["stage"] == "in_progress":
            fallback.append({
                "title": f"진행 상황 업데이트: {t['title']}",
                "category": "task",
                "priority": "medium",
                "due": t.get("due_date") or "이번 주",
                "related": t["title"],
            })

    # 할 일 태스크
    for t in task_summary:
        if t["stage"] == "todo":
            fallback.append({
                "title": f"시작하기: {t['title']}",
                "category": "task",
                "priority": t.get("priority", "medium"),
                "due": t.get("due_date") or "이번 주",
                "related": t["title"],
            })

    if not fallback:
        fallback.append({
            "title": "오늘의 업무 계획 정리하기",
            "category": "prepare",
            "priority": "low",
            "due": "오늘",
        })

    return {
        "checklist": fallback[:10],
        "context": {
            "total_tasks": len(pipeline_tasks),
            "stage_counts": stage_counts,
            "upcoming_events": len(schedule_summary),
        },
        "fallback": True,
    }


@router.post("/suggest-schedules")
async def suggest_schedules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI가 일정 + 파이프라인 + 프로젝트를 분석하여 추천 일정 생성"""
    from datetime import datetime, timedelta

    pipeline_tasks = []
    schedules = []
    stage_counts = {"todo": 0, "in_progress": 0, "review": 0, "done": 0}

    # 1. 데이터 수집
    try:
        task_query = select(PipelineTask).order_by(PipelineTask.created_at.desc())
        if current_user.team:
            task_query = task_query.where(
                or_(
                    PipelineTask.team == current_user.team,
                    PipelineTask.assignee == current_user.name,
                )
            )
        else:
            task_query = task_query.where(
                or_(
                    PipelineTask.created_by == current_user.id,
                    PipelineTask.assignee == current_user.name,
                )
            )
        task_result = await db.execute(task_query)
        pipeline_tasks = task_result.scalars().all()
    except Exception as e:
        logger.error(f"일정추천: 파이프라인 조회 실패: {e}")

    try:
        now = datetime.now()
        week_later = now + timedelta(days=7)
        schedule_query = (
            select(Schedule)
            .where(
                Schedule.user_id == current_user.id,
                Schedule.start_time >= now - timedelta(days=1),
                Schedule.start_time <= week_later,
            )
            .order_by(Schedule.start_time)
        )
        schedule_result = await db.execute(schedule_query)
        schedules = schedule_result.scalars().all()
    except Exception as e:
        logger.error(f"일정추천: 일정 조회 실패: {e}")

    # 2. 컨텍스트 구성
    now = datetime.now()
    task_summary = []
    for t in pipeline_tasks:
        stage_counts[t.stage] = stage_counts.get(t.stage, 0) + 1
        task_summary.append({
            "title": t.title,
            "stage": t.stage,
            "priority": t.priority,
            "assignee": t.assignee,
            "due_date": t.due_date.strftime("%Y-%m-%d") if t.due_date else None,
            "project": t.project,
        })

    schedule_summary = []
    for s in schedules:
        schedule_summary.append({
            "title": s.title,
            "start": s.start_time.strftime("%Y-%m-%d %H:%M") if s.start_time else None,
            "end": s.end_time.strftime("%Y-%m-%d %H:%M") if s.end_time else None,
            "type": s.schedule_type,
        })

    total_tasks = len(pipeline_tasks)
    done_pct = round(stage_counts["done"] / total_tasks * 100) if total_tasks > 0 else 0

    context = f"""## 현재 사용자 정보
- 이름: {current_user.name}
- 팀: {current_user.team or '없음'}
- 오늘 날짜: {now.strftime('%Y-%m-%d %A')}

## 파이프라인 태스크 현황
- 전체: {total_tasks}개
- To Do: {stage_counts['todo']}개, In Progress: {stage_counts['in_progress']}개, Review: {stage_counts['review']}개, Done: {stage_counts['done']}개
- 완료율: {done_pct}%
- 태스크 상세 (진행 중 + 리뷰 + 할 일):
{json.dumps([t for t in task_summary if t['stage'] != 'done'][:15], ensure_ascii=False, indent=2)}

## 현재 캘린더 일정 (향후 7일)
{json.dumps(schedule_summary, ensure_ascii=False, indent=2) if schedule_summary else '예정된 일정 없음'}
"""

    # 3. LLM 호출
    try:
        from ai.llm import get_llm
        from ai.llm.prompts import SCHEDULE_SUGGEST_SYSTEM_PROMPT

        llm = get_llm()
        response = await llm.generate(
            prompt=context,
            system_prompt=SCHEDULE_SUGGEST_SYSTEM_PROMPT,
            json_mode=True,
            temperature=0.4,
            max_tokens=1500,
        )

        result = json.loads(response.content)
        return {
            "suggestions": result.get("suggestions", []),
            "context": {
                "total_tasks": total_tasks,
                "done_pct": done_pct,
                "upcoming_events": len(schedule_summary),
            },
        }
    except Exception as e:
        logger.error(f"일정 추천 AI 실패: {e}", exc_info=True)

    # 4. 폴백
    fallback = []
    if stage_counts.get("review", 0) > 0:
        fallback.append({
            "title": "코드 리뷰 시간",
            "description": f"Review 단계 태스크 {stage_counts['review']}개 확인",
            "schedule_type": "review",
            "priority": "high",
            "suggested_day": "today",
            "duration_minutes": 60,
            "reason": "리뷰 대기 중인 태스크가 있습니다.",
        })
    if stage_counts.get("in_progress", 0) > 2:
        fallback.append({
            "title": "팀 진행 상황 점검",
            "description": f"진행 중 태스크 {stage_counts['in_progress']}개 점검",
            "schedule_type": "meeting",
            "priority": "medium",
            "suggested_day": "tomorrow",
            "duration_minutes": 30,
            "reason": "진행 중인 태스크가 많아 점검이 필요합니다.",
        })
    if done_pct >= 70:
        fallback.append({
            "title": "프로젝트 회고 & 배포 준비",
            "description": f"완료율 {done_pct}%, 배포 준비 논의",
            "schedule_type": "milestone",
            "priority": "medium",
            "suggested_day": "this_week",
            "duration_minutes": 60,
            "reason": f"프로젝트 완료율이 {done_pct}%로 높습니다.",
        })
    deadline_tasks = [t for t in task_summary if t.get("due_date")]
    for t in deadline_tasks[:2]:
        fallback.append({
            "title": f"집중 작업: {t['title']}",
            "description": f"마감일: {t['due_date']}",
            "schedule_type": "task",
            "priority": t.get("priority", "medium"),
            "suggested_day": "today",
            "duration_minutes": 120,
            "reason": f"마감이 다가오는 태스크입니다.",
        })
    if not fallback:
        fallback.append({
            "title": "업무 계획 정리",
            "description": "이번 주 업무 우선순위 정리 시간",
            "schedule_type": "task",
            "priority": "low",
            "suggested_day": "today",
            "duration_minutes": 30,
            "reason": "업무 계획을 세우면 생산성이 높아집니다.",
        })
    return {
        "suggestions": fallback[:5],
        "context": {
            "total_tasks": total_tasks,
            "done_pct": done_pct,
            "upcoming_events": len(schedule_summary),
        },
        "fallback": True,
    }


@router.post("/suggest")
async def suggest_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캘린더 일정 + 파이프라인 태스크를 분석하여 AI 기반 승인 요청 추천"""
    from datetime import datetime, timedelta

    pipeline_tasks = []
    schedules = []
    stage_counts = {"todo": 0, "in_progress": 0, "review": 0, "done": 0}
    schedule_summary = []
    total_tasks = 0
    done_pct = 0

    # 1. 데이터 수집 (실패해도 fallback으로 넘어감)
    try:
        task_query = select(PipelineTask).order_by(PipelineTask.created_at.desc())
        if current_user.team:
            task_query = task_query.where(
                or_(
                    PipelineTask.team == current_user.team,
                    PipelineTask.assignee == current_user.name,
                )
            )
        else:
            task_query = task_query.where(
                or_(
                    PipelineTask.created_by == current_user.id,
                    PipelineTask.assignee == current_user.name,
                )
            )
        task_result = await db.execute(task_query)
        pipeline_tasks = task_result.scalars().all()
    except Exception as e:
        logger.error(f"파이프라인 태스크 조회 실패: {e}")

    try:
        now = datetime.now()
        week_later = now + timedelta(days=7)
        schedule_query = (
            select(Schedule)
            .where(
                Schedule.user_id == current_user.id,
                Schedule.start_time >= now,
                Schedule.start_time <= week_later,
            )
            .order_by(Schedule.start_time)
        )
        schedule_result = await db.execute(schedule_query)
        schedules = schedule_result.scalars().all()
    except Exception as e:
        logger.error(f"일정 조회 실패: {e}")

    # 2. 컨텍스트 구성
    now = datetime.now()
    task_summary = []
    for t in pipeline_tasks:
        stage_counts[t.stage] = stage_counts.get(t.stage, 0) + 1
        task_summary.append({
            "title": t.title,
            "stage": t.stage,
            "priority": t.priority,
            "assignee": t.assignee,
            "due_date": t.due_date.strftime("%Y-%m-%d") if t.due_date else None,
            "project": t.project,
            "tags": t.tags,
        })

    for s in schedules:
        schedule_summary.append({
            "title": s.title,
            "start": s.start_time.strftime("%Y-%m-%d %H:%M") if s.start_time else None,
            "end": s.end_time.strftime("%Y-%m-%d %H:%M") if s.end_time else None,
            "type": s.schedule_type,
        })

    total_tasks = len(pipeline_tasks)
    done_pct = round(stage_counts["done"] / total_tasks * 100) if total_tasks > 0 else 0

    context = f"""## 현재 사용자 정보
- 이름: {current_user.name}
- 팀: {current_user.team or '없음'}
- 오늘 날짜: {now.strftime('%Y-%m-%d')}

## 파이프라인 태스크 현황
- 전체: {total_tasks}개
- To Do: {stage_counts['todo']}개, In Progress: {stage_counts['in_progress']}개, Review: {stage_counts['review']}개, Done: {stage_counts['done']}개
- 완료율: {done_pct}%
- 태스크 상세 (최근 20개):
{json.dumps(task_summary[:20], ensure_ascii=False, indent=2)}

## 향후 7일 캘린더 일정
{json.dumps(schedule_summary, ensure_ascii=False, indent=2) if schedule_summary else '예정된 일정 없음'}
"""

    # 3. LLM 호출
    try:
        from ai.llm import get_llm
        from ai.llm.prompts import APPROVAL_SUGGEST_SYSTEM_PROMPT

        llm = get_llm()
        response = await llm.generate(
            prompt=context,
            system_prompt=APPROVAL_SUGGEST_SYSTEM_PROMPT,
            json_mode=True,
            temperature=0.4,
            max_tokens=1500,
        )

        result = json.loads(response.content)
        return {
            "suggestions": result.get("suggestions", []),
            "context": {
                "total_tasks": total_tasks,
                "stage_counts": stage_counts,
                "done_pct": done_pct,
                "upcoming_events": len(schedule_summary),
            },
        }
    except Exception as e:
        logger.error(f"AI 추천 실패: {e}", exc_info=True)

    # 4. LLM 실패 시 규칙 기반 폴백 (항상 도달)
    fallback = []
    if stage_counts.get("review", 0) > 0:
        review_tasks = [t for t in pipeline_tasks if t.stage == "review"]
        if review_tasks:
            fallback.append({
                "type": "review",
                "title": f"PR 리뷰 요청 - {review_tasks[0].title}",
                "detail": f"현재 Review 단계 태스크 {stage_counts['review']}개가 대기 중입니다.",
                "reason": "Review 단계에 있는 태스크가 있어 리뷰 요청이 필요합니다.",
                "priority": "high",
                "related_project": review_tasks[0].project,
            })
    if done_pct >= 80 and total_tasks > 0:
        # 가장 많은 프로젝트 찾기
        proj_counts = {}
        for t in pipeline_tasks:
            if t.project:
                proj_counts[t.project] = proj_counts.get(t.project, 0) + 1
        top_project = max(proj_counts, key=proj_counts.get) if proj_counts else None
        fallback.append({
            "type": "deploy",
            "title": "배포 승인 요청",
            "detail": f"프로젝트 완료율 {done_pct}%. 배포 준비가 필요합니다.",
            "reason": f"태스크 완료율이 {done_pct}%로 높아 배포를 고려할 시점입니다.",
            "priority": "medium",
            "related_project": top_project,
        })
    if stage_counts.get("in_progress", 0) > 0:
        in_progress_tasks = [t for t in pipeline_tasks if t.stage == "in_progress"]
        if in_progress_tasks:
            fallback.append({
                "type": "budget",
                "title": f"진행 중 태스크 비용 결재 - {in_progress_tasks[0].title}",
                "detail": f"현재 In Progress 태스크 {stage_counts['in_progress']}개 진행 중입니다.",
                "reason": "진행 중인 태스크 관련 비용 결재가 필요할 수 있습니다.",
                "priority": "medium",
                "related_project": in_progress_tasks[0].project,
            })
    if schedule_summary:
        fallback.append({
            "type": "room",
            "title": f"회의실 예약 - {schedule_summary[0]['title']}",
            "detail": f"일정: {schedule_summary[0]['start']}",
            "reason": "예정된 회의가 있어 회의실 예약이 필요할 수 있습니다.",
            "priority": "medium",
            "related_project": None,
        })
    if not fallback:
        fallback.append({
            "type": "budget",
            "title": "프로젝트 비용 결재",
            "detail": "진행 중인 프로젝트 관련 비용 결재를 확인하세요.",
            "reason": "정기적인 비용 결재 확인을 추천합니다.",
            "priority": "low",
            "related_project": None,
        })
    return {
        "suggestions": fallback,
        "context": {
            "total_tasks": total_tasks,
            "stage_counts": stage_counts,
            "done_pct": done_pct,
            "upcoming_events": len(schedule_summary),
        },
        "fallback": True,
    }
