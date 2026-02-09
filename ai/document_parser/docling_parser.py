"""
Docling PDF 파서 (팀원 C 담당)

기능: PDF의 테이블, 헤더, 본문 구조를 인식하여 마크다운으로 변환
규정 문서처럼 조항 구조가 있는 문서에 최적
"""


class DoclingParser:
    """Docling 기반 PDF 구조화 파싱"""

    def parse(self, file_path: str) -> str:
        """
        PDF → 마크다운 변환 (테이블, 헤더 구조 유지)
        """
        # TODO: 팀원 C 구현
        # from docling.document_converter import DocumentConverter
        # converter = DocumentConverter()
        # result = converter.convert(file_path)
        # return result.document.export_to_markdown()
        raise NotImplementedError

    def split_by_sections(self, markdown_text: str) -> list:
        """마크다운을 조항 단위로 분할 (청킹용)"""
        # TODO: 팀원 C 구현
        raise NotImplementedError
