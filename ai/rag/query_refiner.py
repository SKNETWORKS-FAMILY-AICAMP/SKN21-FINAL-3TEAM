"""
Query Refinement — 검색 전 쿼리 변환

사용자 쿼리를 RAG 검색에 최적화된 형태로 변환한다.

방법:
  1. 형태소 분석 후 핵심 키워드 추출 (BM25 검색 품질 향상)
  2. 동의어 확장 (사내 규정 도메인 특화)
  3. 불용어 제거
  4. 구어체→문어체 변환 (Vector 검색 품질 향상)

비용: 0 (kiwipiepy 로컬 처리, LLM 호출 없음)
"""
import logging
import re

logger = logging.getLogger(__name__)

# kiwipiepy 인스턴스 — hybrid_search.py의 것을 재사용하여 이중 로딩 방지
_kiwi = None
try:
    from ai.rag.hybrid_search import _kiwi as _shared_kiwi
    _kiwi = _shared_kiwi
    if _kiwi is not None:
        logger.info("kiwipiepy 인스턴스를 hybrid_search에서 재사용")
except ImportError:
    pass

if _kiwi is None:
    try:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
        logger.info("kiwipiepy 새 인스턴스 생성 (query_refiner)")
    except Exception:
        logger.warning("kiwipiepy를 사용할 수 없습니다. query_refiner 기능이 제한됩니다.")


# ── 불용어 (검색에 불필요한 조사/어미/접속사) ──
_STOPWORDS = {
    "이", "가", "을", "를", "의", "에", "에서", "은", "는", "도", "로", "으로",
    "와", "과", "하다", "있다", "없다", "되다", "이다", "것", "수", "등",
    "때", "좀", "그", "저", "이런", "저런", "어떤", "다른",
    "합니다", "입니다", "됩니다", "있습니다", "없습니다",
    "하고", "하면", "해서", "하여", "대해", "대한",
    "질문", "알려", "알고", "싶다", "궁금", "문의",
    "가능", "할", "할까", "할까요", "인가요", "인지", "건가요",
}

# ── 동의어 사전 (사내 규정 도메인 특화) ──
_SYNONYM_MAP: dict[str, list[str]] = {
    "연차": ["연차", "연차휴가", "유급휴가", "휴가"],
    "반차": ["반차", "반일휴가", "오전반차", "오후반차"],
    "병가": ["병가", "질병휴가", "병가휴직"],
    "육아휴직": ["육아휴직", "출산휴가", "육아"],
    "퇴근": ["퇴근", "근태", "근무시간", "퇴사시간"],
    "출근": ["출근", "근태", "근무시간", "출근시간"],
    "재택": ["재택", "재택근무", "원격근무", "리모트"],
    "야근": ["야근", "연장근무", "초과근무", "시간외근무"],
    "보안": ["보안", "정보보호", "보안규정", "정보보안"],
    "USB": ["USB", "외부저장장치", "이동식저장매체", "보조기억매체"],
    "출장": ["출장", "출장비", "출장경비", "여비"],
    "경비": ["경비", "비용", "경비처리", "비용처리"],
    "급여": ["급여", "임금", "봉급", "월급", "보수"],
    "승진": ["승진", "진급", "승급"],
    "징계": ["징계", "제재", "처분", "징계처분"],
    "퇴직": ["퇴직", "퇴사", "퇴직금", "퇴직급여"],
    "수습": ["수습", "수습기간", "시용기간", "시용"],
    "계약": ["계약", "근로계약", "고용계약"],
    "개인정보": ["개인정보", "개인정보보호", "정보보호"],
    "클라우드": ["클라우드", "클라우드서비스", "SaaS", "외부서비스"],
}

# ── 구어체 → 문어체 변환 사전 (Vector 검색 품질 향상) ──
# 사용자 구어체를 규정 문서에 가까운 표현으로 바꿔 임베딩 유사도를 높인다.
_COLLOQUIAL_TO_FORMAL: list[tuple[str, str]] = [
    # 어미 변환 (긴 패턴부터 매칭)
    (r"쓸\s*수\s*있(어요|나요|을까요?|는지)?", "사용 가능 여부"),
    (r"받을\s*수\s*있(어요|나요|을까요?|는지)?", "수령 가능 여부"),
    (r"할\s*수\s*있(어요|나요|을까요?|는지)?", "가능 여부"),
    (r"해도\s*되(나요|는지|는 건지|는 건가요|죠)?", "허용 여부"),
    (r"안\s*되(나요|는지|는 건지|는 건가요|죠)?", "금지 여부"),
    (r"해야\s*(하나요|되나요|하는지|하는 건지)", "의무 사항"),
    (r"몇\s*일(이나|까지)?\s*(쓸|사용할|받을)?\s*수?\s*있(어요|나요)?", "일수 기준"),
    (r"얼마(나|까지)?\s*(받|쓸|사용할)?\s*수?\s*있(어요|나요)?", "한도 기준"),
    (r"어떻게\s*(해요|하나요|하면 되나요|해야 하나요|하는지)", "절차 및 방법"),
    (r"언제(까지)?\s*(해요|하나요|해야 하나요|내야 하나요)", "기한 기준"),
    (r"누가\s*(해요|하나요|승인하나요|결재하나요)", "담당자 및 승인권자"),
    # 단어 수준 변환
    (r"알려\s*주세요", "안내"),
    (r"궁금해요", "문의"),
    (r"뭐예요\??", "정의"),
    (r"뭔가요\??", "정의"),
]

# 핵심 품사 태그 (kiwipiepy 기준: NNG 일반명사, NNP 고유명사, VV 동사, VA 형용사, SL 외국어)
_KEY_POS_TAGS = {"NNG", "NNP", "VV", "VA", "SL", "SH", "SN"}


def _extract_keywords(text: str) -> list[str]:
    """형태소 분석으로 핵심 키워드 추출 (명사/동사/형용사/외국어만)"""
    if _kiwi is None:
        # fallback: 공백 분리 후 불용어 제거
        tokens = text.split()
        return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]

    keywords = []
    for token in _kiwi.tokenize(text):
        # 핵심 품사만 추출
        if token.tag in _KEY_POS_TAGS:
            word = token.form
            # 불용어 체크
            if word not in _STOPWORDS and len(word) > 0:
                keywords.append(word)

    return keywords


def _expand_synonyms(keywords: list[str]) -> list[str]:
    """동의어 확장 — 키워드에 대한 동의어를 추가"""
    expanded = list(keywords)  # 원본 유지

    for kw in keywords:
        kw_lower = kw.lower()
        for base, synonyms in _SYNONYM_MAP.items():
            # 키워드가 동의어 사전의 base 또는 synonyms에 포함되면 확장
            if kw_lower == base.lower() or kw_lower in [s.lower() for s in synonyms]:
                for syn in synonyms:
                    if syn not in expanded:
                        expanded.append(syn)
                break  # 하나의 동의어 그룹에만 매칭

    return expanded


# ── 규정 조항 참조 패턴 (다양한 번호 체계 지원) ──
_ARTICLE_PATTERNS = [
    r"제\s*\d+\s*조(?:\s*제\s*\d+\s*항)?",  # 제8조, 제8조 제2항
    r"제\s*\d+\s*[장편절관]",                  # 제3장, 제2편, 제1절
    r"별표\s*\d+",                             # 별표 1
    r"부칙\s*\d*",                             # 부칙, 부칙 2
    r"\d+\.\d+(?:\.\d+)?\s*조?",              # 3.2조, 3.2.1
]
_ARTICLE_RE = re.compile("|".join(f"({p})" for p in _ARTICLE_PATTERNS))


def _extract_article_refs(text: str) -> list[str]:
    """텍스트에서 규정 조항 참조를 추출한다.

    지원 형식: 제N조, 제N조 제N항, 제N장, 별표 N, 부칙 N, 3.2조 등
    """
    refs = []
    for m in _ARTICLE_RE.finditer(text):
        ref = m.group().replace(" ", "")
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def refine_query(raw_query: str) -> str:
    """사용자 쿼리를 검색에 최적화된 형태로 변환한다.

    변환 단계:
      1. 형태소 분석 → 핵심 키워드 추출 (불용어 제거)
      2. 동의어 확장 (사내 규정 도메인)
      3. 규정 조항 참조 보존 (제N조 등)
      4. 키워드 조합으로 최적화된 쿼리 생성

    Args:
        raw_query: 사용자 원본 쿼리

    Returns:
        검색에 최적화된 쿼리 문자열
    """
    if not raw_query or not raw_query.strip():
        return raw_query

    # 1. 규정 조항 참조 보존
    article_refs = _extract_article_refs(raw_query)

    # 2. 핵심 키워드 추출
    keywords = _extract_keywords(raw_query)

    if not keywords:
        return raw_query  # 키워드가 없으면 원본 반환

    # 3. 동의어 확장
    expanded = _expand_synonyms(keywords)

    # 4. 규정 조항 참조 추가
    for ref in article_refs:
        if ref not in expanded:
            expanded.append(ref)

    # 5. 중복 제거 + 조합
    seen = set()
    unique = []
    for kw in expanded:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            unique.append(kw)

    refined = " ".join(unique)

    logger.info(
        f"[QueryRefiner] '{raw_query}' → '{refined}' "
        f"(키워드 {len(keywords)}개 → 확장 {len(unique)}개)"
    )
    return refined


def refine_query_for_bm25(raw_query: str) -> str:
    """BM25 전용 쿼리 변환 — 키워드만 추출 (동의어 확장 포함)

    Vector 검색은 원본 쿼리(의미 보존)를, BM25는 키워드 쿼리를 사용하면
    하이브리드 검색 품질이 향상된다.
    """
    return refine_query(raw_query)


def _convert_colloquial_to_formal(text: str) -> str:
    """구어체를 규정 문서에 가까운 문어체로 변환한다.

    규칙 기반이므로 LLM 호출 없이 즉시 처리. 매칭되는 패턴이 없으면 원본 반환.
    """
    converted = text
    for pattern, replacement in _COLLOQUIAL_TO_FORMAL:
        converted = re.sub(pattern, replacement, converted)

    if converted != text:
        logger.info(f"[QueryRefiner:Vector] 구어체→문어체: '{text}' → '{converted}'")

    return converted


def refine_query_for_vector(raw_query: str) -> str:
    """Vector 검색용 쿼리 — 구어체→문어체 변환 후 반환.

    핵심 키워드는 유지하면서 구어 표현만 규정 문서체로 바꿔
    임베딩 유사도를 높인다. 문장 구조는 보존.
    """
    if not raw_query or not raw_query.strip():
        return raw_query
    return _convert_colloquial_to_formal(raw_query)
