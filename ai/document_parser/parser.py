"""
문서 파싱 라우터 (팀원 C 담당)

파일 형식별 자동 분기:
  - 디지털 PDF → Docling
  - 스캔 PDF / 이미지 → PaddleOCR
  - DOCX → python-docx
  - TXT → 직접 읽기
"""

import logging
from pathlib import Path

from ai.document_parser.docling_parser import DoclingParser
from ai.document_parser.docx_parser import DocxParser
from ai.document_parser.ocr_parser import OCRParser

logger = logging.getLogger(__name__)

# 이미지 확장자 (OCR 대상)
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}


class DocumentParser:
    """파일 형식별 자동 파싱"""

    def __init__(self):
        self._docling = DoclingParser()
        self._docx = DocxParser()
        self._ocr = OCRParser()

    def parse(self, file_path: str) -> str:
        """
        파일을 파싱하여 구조화된 마크다운 텍스트 반환

        지원 형식: .pdf, .docx, .txt, .png, .jpg, .jpeg, .bmp, .tiff

        Returns:
            마크다운 형식의 구조화된 텍스트
        """
        ext = Path(file_path).suffix.lower()
        logger.info("문서 파싱 시작: %s (형식: %s)", file_path, ext)

        if ext == ".pdf":
            return self._parse_pdf(file_path)
        elif ext == ".docx":
            return self._parse_docx(file_path)
        elif ext == ".txt":
            return self._parse_txt(file_path)
        elif ext in _IMAGE_EXTENSIONS:
            return self._parse_image(file_path)
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {ext}")

    def _parse_pdf(self, file_path: str) -> str:
        """PDF 파싱 — Docling 시도, 텍스트가 부족하면 OCR fallback"""
        text = self._docling.parse(file_path)

        # Docling 결과가 너무 짧으면 스캔 문서일 가능성 → OCR fallback
        if len(text.strip()) < 50:
            logger.info("Docling 결과가 짧음 (%d자) → OCR fallback", len(text.strip()))
            text = self._ocr.extract_text_from_pdf(file_path)

        return text

    def _parse_docx(self, file_path: str) -> str:
        """DOCX 파싱"""
        return self._docx.parse(file_path)

    def _parse_txt(self, file_path: str) -> str:
        """TXT 직접 읽기"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _parse_image(self, file_path: str) -> str:
        """이미지 파일 OCR"""
        return self._ocr.extract_text(file_path)

    def parse_and_chunk(self, file_path: str) -> list[dict]:
        """
        파싱 + 조항 단위 청킹 (RAG 적재용)

        PDF → Docling 마크다운 → 조항 분할
        DOCX/TXT → 단락 단위 분할

        Returns:
            list[dict]: [{"text": ..., "source": ..., "chapter": ..., "article": ...}, ...]
        """
        ext = Path(file_path).suffix.lower()
        source = Path(file_path).stem

        if ext == ".pdf":
            markdown = self._parse_pdf(file_path)
            chunks = self._docling.split_by_sections(markdown)
            for chunk in chunks:
                chunk["source"] = source
            return chunks

        # DOCX/TXT: 빈 줄 기준 단락 분할
        text = self.parse(file_path)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks = []
        for i, para in enumerate(paragraphs):
            chunks.append({
                "text": para,
                "source": source,
                "chapter": "",
                "article": "",
                "title": f"단락 {i+1}",
            })

        logger.info("청킹 완료: %s → %d개 청크", file_path, len(chunks))
        return chunks
