"""
Regulation Parser Module

Parses regulation PDF files into structured Article objects and RAG chunks.
based on logic from ai/tests/test_e2e_judgment.py
"""
import re
import fitz  # PyMuPDF
from typing import List, Dict, Tuple, Any

# Regex patterns for parsing
RE_CHAPTER = re.compile(r"^(제\s*\d+\s*장)\s*(.*)")
RE_ARTICLE = re.compile(r"^(제\s*\d+\s*조(?:의\d+)?)\s*(?:\(([^)]+)\))?\s*(.*)")
RE_APPENDIX = re.compile(r"^(부\s*칙|별\s*표|부록)")
RE_TOC_LINE = re.compile(r"^제\s*\d+\s*[조장절]\s")


def parse_regulation_pdf(pdf_path: str) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parse a regulation PDF file.

    Returns:
        chunks (List[str]): Text chunks for RAG.
        chunk_metas (List[Dict]): Metadata for RAG chunks.
        articles (List[Dict]): Structured article data for DB (title, article_number, content, category).
    """
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()

    chunks, chunk_metas, articles = _chunk_by_articles(full_text)
    return chunks, chunk_metas, articles


def _chunk_by_articles(full_text: str) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split text into articles and chunks.
    """
    lines = full_text.split("\n")
    chunks = []
    chunk_metas = []
    articles_data = []  # For DB: {article_number, title, content, category}

    current_chapter = ""
    current_article_num = ""
    current_article_title = ""
    current_lines = []
    in_toc = False

    def _flush():
        nonlocal current_lines
        if not current_lines:
            return

        text = "\n".join(current_lines).strip()
        
        # Skip very short or TOC lines
        if len(text) < 30:
            # Check if it's a valid short article (e.g. "제1조(목적) 이 규정은...")
            if not (RE_ARTICLE.match(text) or RE_APPENDIX.match(text)):
                current_lines = []
                return

        # Double check for TOC blocks
        non_empty = [l for l in current_lines if l.strip()]
        if non_empty:
            toc_ratio = sum(1 for l in non_empty if RE_TOC_LINE.match(l.strip())) / len(non_empty)
            if toc_ratio > 0.5 and len(non_empty) > 3:
                current_lines = []
                return

        # Prepare metadata
        # Use existing variables or fallback to generic names
        source = current_article_num or current_chapter or "Regulation"
        title = current_article_title or current_chapter or "사내규정"
        category = current_chapter.split(" ")[1] if " " in current_chapter else "General"
        
        # 1. Add to Articles Data (DB)
        # Only add valid articles (must have article number or be appendix)
        if current_article_num or RE_APPENDIX.match(text):
             articles_data.append({
                "article_number": current_article_num if current_article_num else "Appendix",
                "title": title,
                "content": text,
                "category": category,
                "version": "1.0" 
            })

        # 2. Add to Chunks (RAG) - Split long text
        if len(text) > 400:
            sub_chunks = _split_by_bullets(text)
            for idx, sub in enumerate(sub_chunks):
                if len(sub.strip()) < 10: continue
                
                sub_source = f"{source} ({idx+1}/{len(sub_chunks)})" if len(sub_chunks) > 1 else source
                chunks.append(sub.strip())
                chunk_metas.append({
                    "source": sub_source,
                    "scope": "company",
                    "title": title,
                    "chapter": current_chapter,
                    "article": current_article_num,
                    "category": category
                })
        else:
            chunks.append(text)
            chunk_metas.append({
                "source": source,
                "scope": "company",
                "title": title,
                "chapter": current_chapter,
                "article": current_article_num,
                "category": category
            })

        current_lines = []

    def _split_by_bullets(text: str) -> List[str]:
        parts = re.split(r"(?=●)", text)
        if len(parts) <= 1:
            parts = re.split(r"(?<=다\.)\s*\n|(?<=한다\.)\s*\n|(?<=된다\.)\s*\n", text)
        
        result = []
        current = ""
        for part in parts:
            part = part.strip()
            if not part: continue
            if len(current) + len(part) > 400 and current:
                result.append(current)
                current = part
            else:
                current = current + "\n" + part if current else part
        
        if current.strip():
            result.append(current)
        return result if result else [text]

    # Main parsing loop
    for line in lines:
        stripped = line.strip()
        if not stripped: continue

        # Cover page / TOC detection
        if "듀듀 테크놀로지" in stripped or "Duedue Technology" in stripped:
            in_toc = True
            continue
        if in_toc and ("목 차" in stripped or "목차" in stripped):
            continue

        # Appendix
        if RE_APPENDIX.match(stripped):
            _flush()
            current_article_num = stripped[:20].strip()
            current_article_title = stripped[:20].strip()
            current_lines = [stripped]
            continue

        # Chapter Header
        m_ch = RE_CHAPTER.match(stripped)
        if m_ch:
            _flush()
            current_chapter = f"{m_ch.group(1)} {m_ch.group(2)}".strip()
            in_toc = False
            current_lines = [stripped]
            current_article_num = ""
            current_article_title = ""
            continue

        # Article Header
        m_art = RE_ARTICLE.match(stripped)
        if m_art:
            _flush()
            current_article_num = m_art.group(1).strip()
            current_article_title = m_art.group(2).strip() if m_art.group(2) else ""
            in_toc = False
            current_lines = [stripped]
            continue

        current_lines.append(stripped)

    _flush()
    return chunks, chunk_metas, articles_data
