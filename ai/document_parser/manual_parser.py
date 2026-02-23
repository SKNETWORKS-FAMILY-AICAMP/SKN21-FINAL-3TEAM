"""
매뉴얼/설명서 전용 섹션 분할기

마크다운 헤딩(#, ##, ###), 숫자 헤딩(1장, Chapter 1),
굵은 텍스트 헤딩(**제목**) 기반으로 섹션을 분할합니다.

규정 문서(제N조 패턴)가 아닌 일반 매뉴얼/설명서 PDF에 사용됩니다.
"""

import logging
import re

logger = logging.getLogger(__name__)

# 긴 섹션 서브 분할 기준 (자)
_MAX_CHUNK_LENGTH = 400


class ManualParser:
    """매뉴얼/설명서 마크다운을 섹션 단위로 분할"""

    # 표지/목차 스킵 패턴 (DoclingParser와 동일)
    _toc_patterns = re.compile(
        r"(목\s*차|table\s*of\s*contents|\.{3,}|\.\.\.\s*\d+)",
        re.IGNORECASE,
    )

    # 마크다운 헤딩: # ~ ###
    _md_heading = re.compile(r"^(#{1,3})\s+(.+)")

    # 숫자 헤딩: 1장, 2장, Chapter 1 등
    _numbered_heading = re.compile(
        r"^(\d+)\s*[장부편]\s*(.*)|^[Cc]hapter\s+(\d+)\s*(.*)",
    )

    # 굵은 텍스트 헤딩: **제목** (줄 전체가 볼드)
    _bold_heading = re.compile(r"^\*\*(.+?)\*\*\s*$")

    def split_by_sections(self, markdown_text: str) -> list[dict]:
        """
        마크다운 텍스트를 섹션 단위로 분할

        Returns:
            list[dict]: [{"text": ..., "section": ..., "title": ..., "chapter": ...}, ...]
        """
        lines = markdown_text.split("\n")
        chunks: list[dict] = []

        current_section = ""   # 상위 섹션 (# 레벨)
        current_title = ""     # 현재 헤딩
        current_chapter = ""   # 장 번호
        current_lines: list[str] = []

        skip_until_content = True

        for line in lines:
            stripped = line.strip()

            # 표지/목차 스킵
            if skip_until_content:
                if self._is_heading(stripped):
                    skip_until_content = False
                elif self._toc_patterns.search(stripped):
                    continue
                elif not stripped:
                    continue
                else:
                    if len(stripped) > 20:
                        skip_until_content = False
                    else:
                        continue

            # 헤딩 감지
            heading_info = self._parse_heading(stripped)
            if heading_info:
                level, title, chapter = heading_info

                # 이전 섹션 저장
                if current_lines:
                    self._flush_section(
                        chunks, current_lines,
                        current_section, current_title, current_chapter,
                    )
                    current_lines = []

                # 상위 섹션 갱신 (# 레벨 or 장 헤딩)
                if level <= 1 or chapter:
                    current_section = title
                    if chapter:
                        current_chapter = chapter

                current_title = title
                continue

            # 일반 라인
            if stripped:
                current_lines.append(stripped)

        # 마지막 섹션
        if current_lines:
            self._flush_section(
                chunks, current_lines,
                current_section, current_title, current_chapter,
            )

        logger.info(
            "매뉴얼 섹션 분할 완료: %d개 청크 (평균 %d자)",
            len(chunks),
            sum(len(c["text"]) for c in chunks) // max(len(chunks), 1),
        )
        return chunks

    def _is_heading(self, line: str) -> bool:
        """헤딩인지 판별"""
        return bool(
            self._md_heading.match(line)
            or self._numbered_heading.match(line)
            or self._bold_heading.match(line)
        )

    def _parse_heading(self, line: str) -> tuple[int, str, str] | None:
        """
        헤딩 파싱 → (level, title, chapter) 또는 None

        level: 0=볼드/숫자, 1=#, 2=##, 3=###
        chapter: 장 번호 문자열 (없으면 "")
        """
        # 마크다운 헤딩
        m = self._md_heading.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            # 마크다운 헤딩 안에 숫자 장 패턴이 있는지 확인
            chapter = self._extract_chapter(title)
            return (level, title, chapter)

        # 숫자 헤딩 (1장 소개, Chapter 1 ...)
        m = self._numbered_heading.match(line)
        if m:
            if m.group(1):
                chapter = m.group(1)
                title = line.strip()
            else:
                chapter = m.group(3)
                title = line.strip()
            return (0, title, chapter)

        # 굵은 텍스트 헤딩
        m = self._bold_heading.match(line)
        if m:
            title = m.group(1).strip()
            chapter = self._extract_chapter(title)
            return (0, title, chapter)

        return None

    def _extract_chapter(self, text: str) -> str:
        """텍스트에서 장 번호 추출"""
        m = re.search(r"(\d+)\s*[장부편]", text)
        if m:
            return m.group(1)
        m = re.search(r"[Cc]hapter\s+(\d+)", text)
        if m:
            return m.group(1)
        return ""

    def _flush_section(
        self,
        chunks: list[dict],
        lines: list[str],
        section: str,
        title: str,
        chapter: str,
    ):
        """섹션 저장. 400자 초과 시 단락(\n\n) 기준 서브 분할"""
        text = "\n".join(lines)

        if len(text) <= _MAX_CHUNK_LENGTH:
            chunks.append({
                "text": text,
                "section": section,
                "title": title or section,
                "chapter": chapter,
                "article": "",
            })
            return

        # 긴 섹션 → 단락(\n\n) 기준 서브 분할
        paragraphs = re.split(r"\n{2,}", text)
        sub_text = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if sub_text and len(sub_text) + len(para) + 1 > _MAX_CHUNK_LENGTH:
                # 현재까지 모은 텍스트 저장
                chunks.append({
                    "text": sub_text,
                    "section": section,
                    "title": title or section,
                    "chapter": chapter,
                    "article": "",
                })
                sub_text = para
            else:
                sub_text = f"{sub_text}\n{para}" if sub_text else para

        # 나머지 저장
        if sub_text.strip():
            chunks.append({
                "text": sub_text,
                "section": section,
                "title": title or section,
                "chapter": chapter,
                "article": "",
            })
