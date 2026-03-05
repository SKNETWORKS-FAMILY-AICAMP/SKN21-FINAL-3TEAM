"""
Messages API (팀원 D 담당)
- 사용자 간 1:1 쪽지 CRUD
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.message import Message

router = APIRouter()


# ── Schemas ──

class MessageCreate(BaseModel):
    receiver_id: int
    content: str


# ── Endpoints ──

@router.get("/")
async def list_messages(
    box: str = Query("inbox", pattern="^(inbox|sent)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """쪽지 목록 (inbox: 받은 쪽지, sent: 보낸 쪽지)"""
    if box == "inbox":
        query = select(Message).where(Message.receiver_id == current_user.id)
    else:
        query = select(Message).where(Message.sender_id == current_user.id)

    query = query.order_by(Message.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    # 관련 유저 정보 조회
    user_ids = list({i.sender_id for i in items} | {i.receiver_id for i in items})
    users_map = {}
    if user_ids:
        users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in users_result.scalars().all():
            users_map[u.id] = u

    return [
        {
            "id": i.id,
            "sender_id": i.sender_id,
            "sender_name": users_map.get(i.sender_id) and users_map[i.sender_id].name,
            "sender_avatar": users_map.get(i.sender_id) and users_map[i.sender_id].avatar,
            "receiver_id": i.receiver_id,
            "receiver_name": users_map.get(i.receiver_id) and users_map[i.receiver_id].name,
            "receiver_avatar": users_map.get(i.receiver_id) and users_map[i.receiver_id].avatar,
            "content": i.content,
            "is_read": i.is_read,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in items
    ]


@router.get("/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """안 읽은 쪽지 수"""
    result = await db.execute(
        select(func.count(Message.id)).where(
            Message.receiver_id == current_user.id,
            Message.is_read == False,
        )
    )
    count = result.scalar() or 0
    return {"unread_count": count}


@router.post("/", status_code=201)
async def send_message(
    req: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """쪽지 보내기"""
    if req.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="본인에게 쪽지를 보낼 수 없습니다")

    # 수신자 존재 확인
    receiver = await db.execute(select(User).where(User.id == req.receiver_id))
    if not receiver.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="수신자를 찾을 수 없습니다")

    msg = Message(
        sender_id=current_user.id,
        receiver_id=req.receiver_id,
        content=req.content,
    )
    db.add(msg)
    await db.flush()
    return {"id": msg.id, "message": "쪽지를 보냈습니다"}


@router.put("/{message_id}/read")
async def mark_as_read(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """읽음 처리"""
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="쪽지를 찾을 수 없습니다")
    if msg.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인의 쪽지만 읽음 처리할 수 있습니다")

    msg.is_read = True
    await db.flush()
    return {"id": msg.id, "is_read": True}


@router.delete("/{message_id}")
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """쪽지 삭제 (본인이 보냈거나 받은 쪽지만)"""
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="쪽지를 찾을 수 없습니다")
    if msg.sender_id != current_user.id and msg.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인 관련 쪽지만 삭제할 수 있습니다")

    await db.delete(msg)
    await db.flush()
    return {"deleted": True, "id": message_id}
