"""
PaddleOCR 파서 (팀원 C 담당)

스캔된 문서나 이미지 기반 문서의 한국어 텍스트 추출.
PDF의 경우 페이지별 이미지로 변환 후 OCR 수행.
"""

import logging

logger = logging.getLogger(__name__)


class OCRParser:
    """PaddleOCR 기반 텍스트 추출"""

    def __init__(self, lang: str = "korean"):
        self.lang = lang
        self._ocr = None

    @property
    def ocr(self):
        """PaddleOCR 인스턴스 (lazy 초기화)"""
        if self._ocr is None:
            self._initialize()
        return self._ocr

    def _initialize(self):
        """PaddleOCR 초기화"""
        from paddleocr import PaddleOCR

        logger.info("PaddleOCR 초기화 중 (lang=%s)...", self.lang)
        self._ocr = PaddleOCR(use_angle_cls=True, lang=self.lang, show_log=False)
        logger.info("PaddleOCR 초기화 완료")

    def extract_text(self, file_path: str) -> str:
        """
        이미지/스캔 PDF에서 텍스트 추출

        지원 형식: .png, .jpg, .jpeg, .bmp, .tiff, .pdf (스캔본)

        Returns:
            추출된 텍스트 (줄바꿈 구분)
        """
        result = self.ocr.ocr(file_path, cls=True)

        if not result:
            logger.warning("OCR 결과 없음: %s", file_path)
            return ""

        lines = []
        for page in result:
            if page is None:
                continue
            for line_info in page:
                # line_info: [bbox, (text, confidence)]
                text = line_info[1][0]
                confidence = line_info[1][1]
                if confidence >= 0.5:
                    lines.append(text)

        extracted = "\n".join(lines)
        logger.info("OCR 완료: %s (%d줄, %d자)", file_path, len(lines), len(extracted))
        return extracted

    def extract_text_from_pdf(self, file_path: str) -> str:
        """
        스캔 PDF -> 페이지별 OCR -> 텍스트 합산

        PyMuPDF로 페이지를 이미지로 변환 후 OCR 수행.

        Returns:
            전체 페이지 OCR 텍스트
        """
        import fitz  # PyMuPDF
        import tempfile
        import os
        from pathlib import Path

        doc = fitz.open(file_path)
        page_count = doc.page_count
        all_text = []

        logger.info("스캔 PDF OCR 시작: %s (%d페이지)", file_path, page_count)

        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(page_count):
                page = doc[i]
                # 페이지를 이미지로 렌더링 (300 DPI)
                pix = page.get_pixmap(dpi=300)
                img_path = os.path.join(tmpdir, f"page_{i+1}.png")
                pix.save(img_path)

                # OCR 수행
                page_text = self.extract_text(img_path)
                if page_text:
                    all_text.append(f"--- 페이지 {i+1} ---\n{page_text}")

        doc.close()

        result = "\n\n".join(all_text)
        logger.info("스캔 PDF OCR 완료: %d페이지, %d자", page_count, len(result))
        return result
