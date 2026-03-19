"""
문서 Agent (팀원 C 담당) — Facade

기능별 구현은 ai/agents/document/ 패키지에 분리.
이 파일은 기존 import 경로 호환을 위한 re-export만 담당한다.
"""
from ai.agents.document._entry import document_agent
from ai.agents.document._summary import summarize_document, parse_summary_output
from ai.agents.document._generate import generate_document
from ai.agents.document._common import _call_llm

__all__ = [
    "document_agent",
    "summarize_document",
    "parse_summary_output",
    "generate_document",
    "_call_llm",
]
