"""
Docling PDF 파싱 테스트 스크립트
- 대상: ai/data/test.pdf (앞 10페이지만 파싱)
- 출력: ai/data/test_parsed.txt

실행 방법:
    cd SKN21-FINAL-3TEAM
    python ai/document_parser/test_docling_parse.py

사전 조건:
    - docling이 설치되어 있어야 함
    - ai/data/test.pdf 파일이 있어야 함
"""

import sys
import time
from pathlib import Path

# ai/ 폴더 기준 경로 (ai/document_parser/ → ai/)
ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "data" / "test.pdf"
OUTPUT_PATH = ROOT / "data" / "test_parsed.txt"

MAX_PAGES = 10


def main():
    # --- 파일 존재 확인 ---
    if not PDF_PATH.exists():
        print(f"[ERROR] PDF 파일이 없습니다: {PDF_PATH}")
        print("  ai/data/test.pdf 를 먼저 넣어주세요.")
        sys.exit(1)

    print(f"[INFO] 파싱 대상: {PDF_PATH}")
    print(f"[INFO] 최대 페이지: {MAX_PAGES}페이지")
    print("[INFO] Docling 로딩 중...")

    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    except ImportError as e:
        print(f"[ERROR] docling 임포트 실패: {e}")
        print("  pip install docling 을 실행하세요.")
        sys.exit(1)

    # --- 파이프라인 옵션 ---
    # do_ocr=True  : 스캔본 / 폰트 인코딩 깨진 PDF도 처리
    # do_table_structure=True : 표 구조 인식
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend,
            )
        }
    )

    start = time.time()
    print("[INFO] 변환 시작 (OCR 포함, 시간이 걸릴 수 있습니다)...")

    # page_range=(1, N): 앞에서 N페이지만 파싱
    # max_num_pages=N: "N페이지 초과 문서는 거부" (전혀 다른 의미 — 사용 금지)
    result = converter.convert(PDF_PATH, page_range=(1, MAX_PAGES))

    elapsed = time.time() - start
    print(f"[INFO] 변환 완료 ({elapsed:.1f}s)")

    # --- 텍스트 추출 ---
    # export_to_markdown(): 헤더, 테이블 구조 포함 (규정 문서에 유리)
    # export_to_text(): 순수 텍스트만
    markdown_text = result.document.export_to_markdown()

    # --- 저장 ---
    OUTPUT_PATH.write_text(markdown_text, encoding="utf-8")
    print(f"[INFO] 저장 완료: {OUTPUT_PATH}")
    print(f"[INFO] 총 글자 수: {len(markdown_text):,}자")

    # --- 미리보기 (앞 500자) ---
    print("\n" + "=" * 60)
    print("[ 미리보기 - 앞 500자 ]")
    print("=" * 60)
    print(markdown_text[:500])
    print("=" * 60)


if __name__ == "__main__":
    main()
