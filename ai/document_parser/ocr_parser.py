"""
PaddleOCR 파서 (팀원 C 담당)

스캔된 문서나 이미지 기반 문서의 한국어 텍스트 추출
"""


class OCRParser:
    """PaddleOCR 기반 텍스트 추출"""

    def __init__(self):
        self.ocr = None

    def initialize(self):
        """PaddleOCR 초기화"""
        # TODO: 팀원 C 구현
        # from paddleocr import PaddleOCR
        # self.ocr = PaddleOCR(lang='korean')
        raise NotImplementedError

    def extract_text(self, file_path: str) -> str:
        """이미지/스캔 PDF에서 텍스트 추출"""
        # TODO: 팀원 C 구현
        raise NotImplementedError
