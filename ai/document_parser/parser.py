"""
문서 파싱 라우터 (팀원 C 담당)

파일 형식별 자동 분기:
  - 디지털 PDF → Docling
  - 스캔 PDF / 이미지 → PaddleOCR → Docling
  - DOCX → python-docx
  - TXT → 직접 읽기
"""
from pathlib import Path


class DocumentParser:
    """파일 형식별 자동 파싱"""

    def parse(self, file_path: str) -> str:
        """
        파일을 파싱하여 구조화된 마크다운 텍스트 반환

        Returns:
            마크다운 형식의 구조화된 텍스트
        """
        ext = Path(file_path).suffix.lower()

        if ext == ".pdf":
            return self._parse_pdf(file_path)
        elif ext == ".docx":
            return self._parse_docx(file_path)
        elif ext == ".txt":
            return self._parse_txt(file_path)
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {ext}")

    def _parse_pdf(self, file_path: str) -> str:
        """PDF 파싱 (Docling + PaddleOCR)"""
        # TODO: 팀원 C 구현
        raise NotImplementedError

    def _parse_docx(self, file_path: str) -> str:
        """DOCX 파싱 (python-docx)"""
        # TODO: 팀원 C 구현
        raise NotImplementedError

    def _parse_txt(self, file_path: str) -> str:
        """TXT 직접 읽기"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
