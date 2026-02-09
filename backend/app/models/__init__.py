"""
SQLAlchemy ORM 모델 (팀원 D 담당)
모든 모델을 여기서 import하여 Alembic이 인식하게 합니다.
"""
from app.models.user import User
from app.models.document import Document
from app.models.regulation import Regulation
from app.models.meeting import Meeting
from app.models.action_item import ActionItem
from app.models.schedule import Schedule
from app.models.judgment import Judgment
from app.models.chat_log import ChatLog
from app.models.oauth_token import OAuthToken

__all__ = [
    "User",
    "Document",
    "Regulation",
    "Meeting",
    "ActionItem",
    "Schedule",
    "Judgment",
    "ChatLog",
    "OAuthToken",
]
