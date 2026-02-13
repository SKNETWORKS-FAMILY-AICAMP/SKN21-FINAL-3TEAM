"""
RAG 파이프라인 통합 테스트

테스트 항목:
  1. add_documents → retrieve 기본 동작
  2. scope 필터링 (personal 문서가 다른 사용자에게 안 보이는지)
  3. user_id=None이면 company 문서만 반환
  4. 빈 컬렉션에서 검색 시 빈 리스트 반환
  5. 배치 add_documents 동작
  6. 한국어 형태소 분석 토크나이저 확인
"""
import shutil
import tempfile

import pytest

from ai.rag.hybrid_search import tokenize
from ai.rag.pipeline import RAGPipeline, reset_pipeline

# ── 테스트용 규정 문서 ──

COMPANY_DOCS = [
    "직원은 연간 15일의 유급 연차휴가를 사용할 수 있다. 입사 1년 미만인 경우 매월 1일의 유급휴가가 발생한다.",
    "야근 수당은 통상임금의 1.5배로 지급하며, 휴일근무 시 2배를 지급한다. 야근은 사전 승인이 필요하다.",
    "퇴직금은 근속 1년당 30일분의 평균임금으로 산정한다. 퇴직 시 14일 이내에 지급해야 한다.",
    "재택근무는 주 2회까지 허용되며, 사전에 팀장의 승인을 받아야 한다. 재택근무 시 업무 시작과 종료를 보고해야 한다.",
    "출장비는 교통비, 숙박비, 식비를 실비로 지급하며, 일비는 1일 2만원을 정액 지급한다.",
]

COMPANY_METAS = [
    {"source": "취업규칙 제15조", "scope": "company"},
    {"source": "취업규칙 제22조", "scope": "company"},
    {"source": "취업규칙 제30조", "scope": "company"},
    {"source": "재택근무 규정 제3조", "scope": "company"},
    {"source": "출장비 규정 제5조", "scope": "company"},
]

PERSONAL_DOCS = [
    "김철수의 2024년 연차 사용 내역: 총 10일 사용, 잔여 5일. 여름휴가 3일 포함.",
    "이영희의 재택근무 승인 기록: 2024년 1분기 총 20회 재택근무 실시.",
]

PERSONAL_METAS = [
    {"source": "개인기록_김철수", "scope": "personal", "user_id": "1"},
    {"source": "개인기록_이영희", "scope": "personal", "user_id": "2"},
]


@pytest.fixture
def temp_dir():
    """테스트마다 새로운 임시 ChromaDB 디렉토리"""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def pipeline(temp_dir):
    """초기화된 RAGPipeline (테스트마다 독립)"""
    reset_pipeline()
    p = RAGPipeline(persist_dir=temp_dir)
    p.initialize()
    return p


@pytest.fixture
def pipeline_with_docs(pipeline):
    """회사 + 개인 문서가 모두 추가된 파이프라인"""
    pipeline.add_documents(COMPANY_DOCS, COMPANY_METAS)
    pipeline.add_documents(PERSONAL_DOCS, PERSONAL_METAS)
    return pipeline


# ── 1. 기본 동작 ──


class TestBasicRetrieval:
    def test_add_and_retrieve(self, pipeline_with_docs):
        """문서를 추가하고 관련 질문으로 검색하면 결과가 반환된다."""
        results = pipeline_with_docs.retrieve("연차휴가는 며칠인가요?", user_id=1)

        assert len(results) > 0
        assert all("content" in r for r in results)
        assert all("source" in r for r in results)
        assert all("score" in r for r in results)

    def test_retrieve_relevance(self, pipeline_with_docs):
        """연차 관련 질문 시 연차 문서가 최상위에 온다."""
        results = pipeline_with_docs.retrieve("연차휴가 일수가 궁금합니다", user_id=1)

        assert len(results) > 0
        top_content = results[0]["content"]
        assert "연차" in top_content or "휴가" in top_content

    def test_retrieve_top_k(self, pipeline_with_docs):
        """top_k 파라미터대로 결과 수가 제한된다."""
        results = pipeline_with_docs.retrieve("규정", user_id=1, top_k=3)
        assert len(results) <= 3

    def test_retrieve_result_format(self, pipeline_with_docs):
        """반환 형식이 {"content", "source", "score"}인지 확인"""
        results = pipeline_with_docs.retrieve("야근 수당", user_id=1)

        for r in results:
            assert isinstance(r["content"], str)
            assert isinstance(r["source"], str)
            assert isinstance(r["score"], float)


# ── 2. scope 필터링 ──


class TestScopeFiltering:
    def test_user1_sees_own_personal(self, pipeline_with_docs):
        """user_id=1은 자신의 personal 문서(김철수)를 검색할 수 있다."""
        results = pipeline_with_docs.retrieve("김철수 연차 사용 내역", user_id=1, top_k=10)

        contents = " ".join(r["content"] for r in results)
        assert "김철수" in contents

    def test_user1_cannot_see_user2_personal(self, pipeline_with_docs):
        """user_id=1은 user_id=2의 personal 문서(이영희)를 볼 수 없다."""
        results = pipeline_with_docs.retrieve("이영희 재택근무", user_id=1, top_k=10)

        contents = " ".join(r["content"] for r in results)
        assert "이영희" not in contents

    def test_user2_sees_own_personal(self, pipeline_with_docs):
        """user_id=2는 자신의 personal 문서(이영희)를 검색할 수 있다."""
        results = pipeline_with_docs.retrieve("이영희 재택근무 기록", user_id=2, top_k=10)

        contents = " ".join(r["content"] for r in results)
        assert "이영희" in contents

    def test_both_users_see_company_docs(self, pipeline_with_docs):
        """모든 사용자는 company 문서를 검색할 수 있다."""
        for uid in [1, 2]:
            results = pipeline_with_docs.retrieve("야근 수당 규정", user_id=uid)
            contents = " ".join(r["content"] for r in results)
            assert "야근" in contents


# ── 3. user_id=None → company만 ──


class TestNullUserId:
    def test_no_user_id_returns_company_only(self, pipeline_with_docs):
        """user_id=None이면 company 문서만 반환된다."""
        results = pipeline_with_docs.retrieve("연차휴가", user_id=None, top_k=10)

        for r in results:
            # personal 문서의 내용이 포함되면 안 됨
            assert "김철수" not in r["content"]
            assert "이영희" not in r["content"]

    def test_no_user_id_still_returns_results(self, pipeline_with_docs):
        """user_id=None이어도 company 문서가 검색된다."""
        results = pipeline_with_docs.retrieve("퇴직금 산정 방법", user_id=None)
        assert len(results) > 0


# ── 4. 빈 컬렉션 ──


class TestEmptyCollection:
    def test_retrieve_empty(self, pipeline):
        """빈 컬렉션에서 검색하면 빈 리스트를 반환한다."""
        results = pipeline.retrieve("아무 질문", user_id=1)
        assert results == []

    def test_search_empty(self, pipeline):
        """빈 컬렉션에서 HybridSearcher.search도 빈 리스트를 반환한다."""
        results = pipeline.searcher.search("아무 질문", user_id=1)
        assert results == []


# ── 5. 배치 처리 ──


class TestBatchProcessing:
    def test_batch_add(self, pipeline):
        """batch_size보다 많은 문서를 추가해도 정상 동작한다."""
        # 7개 문서를 batch_size=3으로 추가
        all_docs = COMPANY_DOCS + PERSONAL_DOCS
        all_metas = COMPANY_METAS + PERSONAL_METAS

        pipeline.add_documents(all_docs, all_metas, batch_size=3)

        results = pipeline.retrieve("연차", user_id=1)
        assert len(results) > 0


# ── 6. 토크나이저 ──


class TestTokenizer:
    def test_korean_morphs(self):
        """한국어 형태소 분석이 제대로 동작하는지 확인"""
        tokens = tokenize("연차사용 신청서를 제출합니다")
        # "연차", "사용" 등이 분리되어야 함
        assert len(tokens) > 2
        assert any("연차" in t for t in tokens)

    def test_tokenize_empty(self):
        """빈 문자열도 에러 없이 처리"""
        tokens = tokenize("")
        assert tokens == []


# ── 7. 개별 모듈 ──


class TestVectorStore:
    def test_get_all_documents(self, pipeline):
        """add 후 get_all_documents가 저장된 문서를 반환한다."""
        pipeline.add_documents(COMPANY_DOCS[:2], COMPANY_METAS[:2])

        all_docs = pipeline.vector_store.get_all_documents()
        assert len(all_docs["documents"]) == 2
        assert len(all_docs["metadatas"]) == 2

    def test_delete_collection(self, pipeline):
        """delete_collection 후 재초기화하면 빈 컬렉션이 된다."""
        pipeline.add_documents(COMPANY_DOCS[:2], COMPANY_METAS[:2])
        pipeline.vector_store.delete_collection()
        pipeline.vector_store.initialize()

        all_docs = pipeline.vector_store.get_all_documents()
        assert len(all_docs["documents"]) == 0

    def test_upsert_duplicate_ids(self, pipeline):
        """같은 ID로 문서를 다시 추가해도 에러가 발생하지 않는다."""
        embeddings = pipeline.embedding_model.encode(COMPANY_DOCS[:1])
        pipeline.vector_store.add_documents(
            documents=COMPANY_DOCS[:1],
            metadatas=COMPANY_METAS[:1],
            ids=["fixed-id-001"],
            embeddings=embeddings,
        )
        # 같은 ID로 다시 추가 (upsert이므로 에러 없어야 함)
        pipeline.vector_store.add_documents(
            documents=["업데이트된 문서 내용"],
            metadatas=COMPANY_METAS[:1],
            ids=["fixed-id-001"],
            embeddings=pipeline.embedding_model.encode(["업데이트된 문서 내용"]),
        )
        all_docs = pipeline.vector_store.get_all_documents()
        assert len(all_docs["documents"]) == 1
        assert "업데이트" in all_docs["documents"][0]
