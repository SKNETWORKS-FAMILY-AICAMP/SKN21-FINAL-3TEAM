"""
Gmail 서비스 (팀원 D 담당)
- 담당자 기한 알림 메일 발송
- 회의 초대 메일 (Meet 링크 포함) 발송
"""
import base64
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Optional

from fastapi import HTTPException, status
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_item import ActionItem
from app.services.google_base_service import GoogleBaseService


class GmailService(GoogleBaseService):
    """Gmail 발송 서비스"""

    required_scope = "gmail_send"

    def _build_service(self, creds):
        return build("gmail", "v1", credentials=creds)

    def _create_message(self, to: str, subject: str, html_body: str) -> dict:
        """MIME 메시지 생성"""
        msg = MIMEText(html_body, "html", "utf-8")
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        return {"raw": raw}

    async def send_reminder(
        self, db: AsyncSession, user_id: int, action_item_id: int, recipient_email: str
    ) -> dict:
        """기한 알림 메일 발송"""
        result = await db.execute(
            select(ActionItem).where(ActionItem.id == action_item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action Item을 찾을 수 없습니다")

        due_str = item.due_date.strftime("%Y-%m-%d") if item.due_date else "미정"
        html = f"""
        <h3>Action Item 기한 알림</h3>
        <table border="1" cellpadding="8" style="border-collapse:collapse;">
            <tr><th>내용</th><td>{item.content}</td></tr>
            <tr><th>담당자</th><td>{item.assignee or '미지정'}</td></tr>
            <tr><th>마감일</th><td>{due_str}</td></tr>
            <tr><th>우선순위</th><td>{item.priority}</td></tr>
            <tr><th>상태</th><td>{item.status}</td></tr>
        </table>
        <p style="color:gray;font-size:12px;">WorkFlow Agent에서 자동 발송된 메일입니다.</p>
        """

        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)
        message = self._create_message(
            to=recipient_email,
            subject=f"[기한 알림] {item.content[:50]}",
            html_body=html,
        )
        sent = service.users().messages().send(userId="me", body=message).execute()

        item.email_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)

        return {"message_id": sent["id"], "recipient": recipient_email}

    async def send_meeting_invite(
        self,
        db: AsyncSession,
        user_id: int,
        recipient_emails: list[str],
        meeting_title: str,
        meeting_time: str,
        meet_link: Optional[str] = None,
    ) -> dict:
        """회의 초대 메일 발송 (Meet 링크 포함)"""
        # ISO 형식 → 읽기 좋은 한국어 시간 포맷
        try:
            parsed = datetime.fromisoformat(meeting_time.replace("Z", "+00:00"))
            formatted_time = parsed.strftime("%Y년 %m월 %d일 %H:%M")
        except (ValueError, AttributeError):
            formatted_time = meeting_time

        meet_section = f'<p><a href="{meet_link}">Google Meet 참여</a></p>' if meet_link else ""
        html = f"""
        <h3>회의 초대: {meeting_title}</h3>
        <p><strong>일시:</strong> {formatted_time}</p>
        {meet_section}
        <p style="color:gray;font-size:12px;">WorkFlow Agent에서 자동 발송된 메일입니다.</p>
        """

        creds = await self.get_credentials(db, user_id)
        service = self._build_service(creds)

        results = []
        for email in recipient_emails:
            message = self._create_message(
                to=email,
                subject=f"[회의 초대] {meeting_title}",
                html_body=html,
            )
            try:
                sent = service.users().messages().send(userId="me", body=message).execute()
                results.append({"recipient": email, "success": True, "message_id": sent["id"]})
            except Exception as e:
                results.append({"recipient": email, "success": False, "error": str(e)})

        return {"sent_count": sum(1 for r in results if r["success"]), "results": results}

    async def send_bulk_reminders(
        self,
        db: AsyncSession,
        user_id: int,
        days_before: int = 3,
        recipient_map: Optional[dict[str, str]] = None,
    ) -> dict:
        """마감 임박 Action Item 일괄 알림 발송"""
        deadline = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days_before)
        result = await db.execute(
            select(ActionItem).where(
                ActionItem.due_date <= deadline,
                ActionItem.status != "done",
            )
        )
        items = result.scalars().all()

        if not recipient_map:
            recipient_map = {}

        results = []
        for item in items:
            email = recipient_map.get(item.assignee)
            if not email:
                continue
            try:
                r = await self.send_reminder(db, user_id, item.id, email)
                results.append({"recipient": email, "success": True, "message_id": r["message_id"]})
            except Exception as e:
                results.append({"recipient": email, "success": False, "error": str(e)})

        return {"sent_count": sum(1 for r in results if r["success"]), "results": results}
