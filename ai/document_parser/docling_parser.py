"""
Docling PDF 파서 (팀원 C 담당)

기능: PDF의 테이블, 헤더, 본문 구조를 인식하여 마크다운으로 변환
규정 문서처럼 조항 구조가 있는 문서에 최적

참고: test_docling_parse.py PoC 기반 구현
"""

import logging
import re

logger = logging.getLogger(__name__)

# 긴 조항 서브 분할 기준 (자)
_MAX_CHUNK_LENGTH = 400


class DoclingParser:
    """Docling 기반 PDF 구조화 파싱"""

    def __init__(self, do_ocr: bool = True, do_table_structure: bool = True):
        self.do_ocr = do_ocr
        self.do_table_structure = do_table_structure

    def parse(self, file_path: str, max_pages: int = 0) -> str:
        """
        PDF -> 마크다운 변환 (테이블, 헤더 구조 유지)

        Args:
            file_path: PDF 파일 경로
            max_pages: 최대 페이지 수 (0이면 전체)

        Returns:
            마크다운 형식의 구조화된 텍스트
        """
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

        pipeline_options = PdfPipelineOptions(
            do_ocr=self.do_ocr,
            do_table_structure=self.do_table_structure,
        )

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                    backend=PyPdfiumDocumentBackend,
                )
            }
        )

        kwargs = {}
        if max_pages > 0:
            kwargs["page_range"] = (1, max_pages)

        logger.info("Docling 변환 시작: %s (max_pages=%s)", file_path, max_pages or "전체")
        result = converter.convert(file_path, **kwargs)
        markdown_text = result.document.export_to_markdown()
        logger.info("Docling 변환 완료: %d자", len(markdown_text))

        return markdown_text

    def split_by_sections(self, markdown_text: str) -> list[dict]:
        """
        마크다운을 조항 단위로 분할 (청킹용)

        규정 문서 구조:
          제N장 → chapter 메타데이터
          제N조 → 새 청크 시작
          긴 조항(>400자) → 불릿(●) 기준 서브 분할

        Returns:
            list[dict]: [{"text": ..., "chapter": ..., "article": ..., "title": ...}, ...]
        """
        lines = markdown_text.split("\n")
        chunks = []
        current_chapter = ""
        current_article = ""
        current_title = ""
        current_lines = []

        # 표지/목차 스킵 패턴
        toc_patterns = re.compile(r"(목\s*차|table\s*of\s*contents|\.{3,}|\.\.\.\s*\d+)", re.IGNORECASE)

        # 장/조 패턴
        chapter_pattern = re.compile(r"^#+\s*(제\s*\d+\s*[장편절관])\s*(.*)")
        article_pattern = re.compile(r"^#+\s*(제\s*\d+\s*조(?:의\d+)?)\s*(.*)")
        # 마크다운 헤딩 없이 본문에 바로 나오는 경우
        article_inline_pattern = re.compile(r"^(제\s*\d+\s*조(?:의\d+)?)\s*(.*)")

        skip_until_content = True  # 표지/목차 스킵 플래그

        for line in lines:
            stripped = line.strip()

            # 표지/목차 스킵
            if skip_until_content:
                if chapter_pattern.match(stripped) or article_pattern.match(stripped):
                    skip_until_content = False
                elif toc_patterns.search(stripped):
                    continue
                elif not stripped:
                    continue
                else:
                    # 본문 시작 판단: 제N장/조가 아닌 실질 텍스트
                    if len(stripped) > 20:
                        skip_until_content = False
                    else:
                        continue

            # 장(chapter) 감지
            ch_match = chapter_pattern.match(stripped)
            if ch_match:
                current_chapter = ch_match.group(1).strip()
                chapter_title = ch_match.group(2).strip()
                if chapter_title:
                    current_chapter = f"{current_chapter} {chapter_title}"
                continue

            # 조(article) 감지 — 새 청크 시작
            art_match = article_pattern.match(stripped) or article_inline_pattern.match(stripped)
            if art_match:
                # 이전 청크 저장
                if current_lines:
                    self._flush_chunk(chunks, current_lines, current_chapter, current_article, current_title)
                    current_lines = []

                current_article = art_match.group(1).strip()
                current_title = art_match.group(2).strip().strip("()（）")
                current_lines.append(stripped)
                continue

            # 일반 라인
            if stripped:
                current_lines.append(stripped)

        # 마지막 청크
        if current_lines:
            self._flush_chunk(chunks, current_lines, current_chapter, current_article, current_title)

        logger.info("조항 분할 완료: %d개 청크 (평균 %d자)",
                     len(chunks),
                     sum(len(c["text"]) for c in chunks) // max(len(chunks), 1))
        return chunks

    def _flush_chunk(self, chunks: list, lines: list[str], chapter: str, article: str, title: str):
        """청크 저장. 긴 조항은 불릿 기준 서브 분할"""
        text = "\n".join(lines)

        if len(text) <= _MAX_CHUNK_LENGTH:
            chunks.append({
                "text": text,
                "chapter": chapter,
                "article": article,
                "title": title,
            })
            return

        # 긴 조항 → 불릿(●, -, *, •) 기준 서브 분할
        sub_chunks = re.split(r"\n(?=[●\-\*•]\s)", text)
        for i, sub in enumerate(sub_chunks):
            sub = sub.strip()
            if not sub:
                continue
            chunks.append({
                "text": sub,
                "chapter": chapter,
                "article": f"{article}" if i == 0 else f"{article} ({i+1})",
                "title": title,
            })
