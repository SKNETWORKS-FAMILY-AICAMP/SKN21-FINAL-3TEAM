"""
Qdrant에 예시 문서 벡터화 및 저장
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

# 직접 import하여 순환 의존성 회피
import sys
import importlib.util

# qdrant_store 직접 로드
qdrant_spec = importlib.util.spec_from_file_location(
    "qdrant_store",
    project_root / "ai" / "rag" / "qdrant_store.py"
)
qdrant_module = importlib.util.module_from_spec(qdrant_spec)
qdrant_spec.loader.exec_module(qdrant_module)
QdrantVectorStore = qdrant_module.QdrantVectorStore

# embeddings 직접 로드
embeddings_spec = importlib.util.spec_from_file_location(
    "embeddings",
    project_root / "ai" / "rag" / "embeddings.py"
)
embeddings_module = importlib.util.module_from_spec(embeddings_spec)
embeddings_spec.loader.exec_module(embeddings_module)
EmbeddingModel = embeddings_module.EmbeddingModel


# 예시 문서 데이터
EXAMPLE_DOCUMENTS = [
    {
        "content": """인사 규정 제3조 (연차 휴가)
정규직 근로자는 입사일로부터 1년 경과 시 연차 휴가 15일이 부여됩니다.
3년 이상 근속 시 매 2년마다 1일씩 가산되어 최대 25일까지 부여됩니다.
연차 휴가는 1년 이내에 사용하지 않을 경우 소멸되며, 미사용 연차에 대한 수당이 지급됩니다.""",
        "title": "인사 규정 - 연차 휴가",
        "source": "인사규정.pdf",
        "category": "인사",
        "scope": "company",
    },
    {
        "content": """보안 규정 제5조 (개인정보 보호)
임직원은 업무상 취득한 고객의 개인정보를 외부에 유출하거나 무단으로 사용해서는 안 됩니다.
개인정보는 암호화하여 저장하고, 접근 권한이 있는 자만 열람할 수 있습니다.
개인정보 유출 시 즉시 정보보호 담당자에게 보고해야 하며, 위반 시 징계 처분될 수 있습니다.""",
        "title": "보안 규정 - 개인정보 보호",
        "source": "보안규정.pdf",
        "category": "보안",
        "scope": "company",
    },
    {
        "content": """근무 규정 제7조 (재택근무)
주 2일 이내의 재택근무가 허용되며, 사전에 팀장의 승인을 받아야 합니다.
재택근무 시에도 정규 근무 시간(09:00~18:00)을 준수해야 하며, 업무 일지를 작성해야 합니다.
재택근무 중에도 화상 회의 및 협업 툴을 통해 업무 연락이 가능해야 합니다.""",
        "title": "근무 규정 - 재택근무",
        "source": "근무규정.pdf",
        "category": "근무",
        "scope": "company",
    },
    {
        "content": """복리후생 규정 제10조 (건강검진)
회사는 전 직원에게 연 1회 종합 건강검진을 제공합니다.
40세 이상 직원에게는 추가 검진 항목이 제공되며, 배우자도 건강검진 혜택을 받을 수 있습니다.
건강검진 비용은 회사가 전액 부담하며, 검진 당일은 유급 휴가로 처리됩니다.""",
        "title": "복리후생 규정 - 건강검진",
        "source": "복리후생규정.pdf",
        "category": "복리후생",
        "scope": "company",
    },
    {
        "content": """출장 규정 제12조 (출장비 지급)
국내 출장 시 교통비, 숙박비, 식비가 실비로 지급됩니다.
해외 출장 시에는 출장 전 사전 승인을 받아야 하며, 항공권 및 숙박은 회사에서 예약합니다.
출장 종료 후 7일 이내에 출장 보고서와 영수증을 제출해야 합니다.""",
        "title": "출장 규정 - 출장비 지급",
        "source": "출장규정.pdf",
        "category": "출장",
        "scope": "company",
    },
    {
        "content": """휴가 규정 제15조 (경조사 휴가)
본인 결혼 시 5일, 자녀 결혼 시 1일의 경조사 휴가가 부여됩니다.
직계 가족 사망 시 5일, 배우자 부모 사망 시 3일의 휴가가 부여됩니다.
경조사 휴가는 유급 휴가로 처리되며, 경조금이 별도로 지급됩니다.""",
        "title": "휴가 규정 - 경조사 휴가",
        "source": "휴가규정.pdf",
        "category": "휴가",
        "scope": "company",
    },
    {
        "content": """교육 규정 제18조 (직무 교육)
회사는 직원의 역량 개발을 위해 연간 교육 예산을 책정합니다.
외부 교육 참여 시 교육비 및 교통비가 지원되며, 자격증 취득 시 응시료를 지원합니다.
업무 관련 교육 참여 시간은 근무 시간으로 인정됩니다.""",
        "title": "교육 규정 - 직무 교육",
        "source": "교육규정.pdf",
        "category": "교육",
        "scope": "company",
    },
    {
        "content": """급여 규정 제20조 (성과급)
연간 성과 평가 결과에 따라 성과급이 차등 지급됩니다.
성과급은 S등급 300%, A등급 200%, B등급 100%, C등급 50%가 지급됩니다.
성과 평가는 연 2회 실시되며, 평가 결과는 개별 면담을 통해 공유됩니다.""",
        "title": "급여 규정 - 성과급",
        "source": "급여규정.pdf",
        "category": "급여",
        "scope": "company",
    },
]


def main():
    """예시 문서를 Qdrant에 저장"""
    print("="*60)
    print("Qdrant에 예시 문서 벡터화 및 저장")
    print("="*60)

    # 환경변수 확인
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url or not qdrant_api_key:
        print("ERROR: QDRANT_URL 또는 QDRANT_API_KEY가 .env에 설정되지 않았습니다.")
        return

    print(f"\nQdrant URL: {qdrant_url}")
    print(f"문서 개수: {len(EXAMPLE_DOCUMENTS)}")

    # 1. Qdrant VectorStore 초기화
    print("\n[Step 1] Qdrant VectorStore 초기화...")
    vector_store = QdrantVectorStore(
        url=qdrant_url,
        api_key=qdrant_api_key,
        collection_name="documents",
    )
    vector_store.initialize(vector_size=768)

    # 2. 임베딩 모델 로드
    print("\n[Step 2] 임베딩 모델 로드 (jhgan/ko-sbert-nli)...")
    embedding_model = EmbeddingModel()
    embedding_model.load_model()

    # 3. 문서 임베딩 생성
    print("\n[Step 3] 문서 임베딩 생성...")
    documents = [doc["content"] for doc in EXAMPLE_DOCUMENTS]
    embeddings = embedding_model.encode(documents)
    print(f"  임베딩 생성 완료: {len(embeddings)}개 벡터 (차원: {len(embeddings[0])})")

    # 4. 메타데이터 준비
    metadatas = [
        {
            "title": doc["title"],
            "source": doc["source"],
            "category": doc["category"],
            "scope": doc["scope"],
        }
        for doc in EXAMPLE_DOCUMENTS
    ]

    # 5. Qdrant에 저장
    print("\n[Step 4] Qdrant에 문서 저장...")
    vector_store.add_documents(
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    # 6. 저장 확인
    print("\n[Step 5] 저장 확인...")
    count = vector_store.count()
    print(f"  총 문서 개수: {count}")

    # 7. 테스트 검색
    print("\n[Step 6] 테스트 검색...")
    test_query = "연차 휴가는 몇 일 받을 수 있나요?"
    print(f"  질의: '{test_query}'")

    query_embedding = embedding_model.encode([test_query])[0]
    results = vector_store.search(query_embedding, top_k=3)

    print(f"\n  검색 결과 (Top 3):")
    for i, result in enumerate(results, 1):
        print(f"    {i}. [{result['title']}] (유사도: {result['score']:.4f})")
        print(f"       출처: {result['source']}")
        print(f"       내용: {result['content'][:100]}...")
        print()

    print("="*60)
    print("✅ 완료! Qdrant에 예시 문서가 저장되었습니다.")
    print("="*60)


if __name__ == "__main__":
    main()
