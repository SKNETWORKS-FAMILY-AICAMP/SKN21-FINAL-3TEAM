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

# QdrantClient도 import
from qdrant_client import QdrantClient

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
    {
        "content": """급여 규정 제21조 (야근 수당)
야근 수당은 통상임금의 1.5배로 지급됩니다.
휴일 근무 시에는 통상임금의 2배를 지급합니다.
야근은 사전 승인이 필요하며, 사후 정산은 불가합니다.
월 40시간을 초과하는 야근은 건강 관리 차원에서 제한됩니다.""",
        "title": "급여 규정 - 야근 수당",
        "source": "급여규정.pdf",
        "category": "급여",
        "scope": "company",
    },
]


# 회의록 데이터 (긴 텍스트 테스트용)
MEETING_DOCUMENTS = [
    {
        "content": """# 2분기 코드리뷰 속도 개선 회의록

일시: 2024년 4월 15일
참석자: 정지훈(CTO), 이지아(시니어 개발자)

[회의 배경]
현재 PR 대기 시간이 평균 48시간으로 너무 길어서 개발 속도에 영향을 주고 있습니다.
이로 인해 긴급한 버그 수정도 지연되고, 개발자들의 불만이 높아지고 있는 상황입니다.

[논의 내용]
정지훈: PR 대기 시간이 평균 48시간입니다. 너무 길어요. 특히 긴급 버그 수정이 지연되는 것이 문제입니다.
이지아: 리뷰어 지정을 자동화하고 24시간 내 첫 피드백 룰을 정하면 어떨까요?
        현재는 누가 리뷰할지 애매해서 서로 미루는 경향이 있습니다.
정지훈: 좋은 아이디어네요. 슬랙 봇으로 알림을 보내면 더 효과적일 것 같습니다.
이지아: 추가로 리뷰 가이드라인 문서도 업데이트해서 리뷰 포인트를 명확히 하면 좋겠습니다.

[결정 사항]
1. 24시간 이내 첫 피드백 완료 원칙 수립
2. 리뷰 지연 발생 시 자동 알림 시스템 도입
3. 리뷰어 자동 지정 로직 개발

[Action Items]
- 정지훈: 리뷰 지연 알림 봇 연동 및 설정 (기한: 금요일, 우선순위: 높음)
- 이지아: 신규 리뷰 가이드라인 문서 업데이트 (기한: 다음 주 월요일, 우선순위: 중간)
- 정지훈: 리뷰어 자동 지정 로직 설계 (기한: 다음 주 수요일, 우선순위: 중간)

[예상 효과]
- PR 대기 시간 48시간 → 24시간으로 단축
- 긴급 버그 수정 지연 문제 해소
- 개발자 만족도 향상""",
        "title": "2분기 코드리뷰 속도 개선 회의록",
        "source": "회의록_2024_04_15.md",
        "category": "회의록",
        "scope": "company",
    },
    {
        "content": """# 레거시 정산 모듈 리팩토링 회의록

일시: 2024년 4월 20일
참석자: 박성호(백엔드 리드), 최유리(백엔드 개발자)

[회의 배경]
현재 정산 모듈이 너무 복잡하게 구현되어 있어 신규 매체 추가나 로직 변경이 매우 어려운 상황입니다.
코드 가독성도 낮고, 테스트 코드도 부족하여 버그 발생 위험이 높습니다.

[논의 내용]
박성호: 정산 로직이 너무 복잡해서 신규 매체 추가가 힘듭니다.
        하나의 거대한 함수에 모든 로직이 들어있어서 코드 이해가 어렵습니다.
최유리: 인터페이스로 분리해서 전략 패턴을 도입하는 게 좋겠어요.
        각 매체별로 클래스를 만들고, 공통 인터페이스를 구현하는 방식이면 확장성이 좋을 것 같습니다.
박성호: 맞습니다. 그리고 각 전략마다 단위 테스트도 작성하면 안정성이 높아질 것 같습니다.
최유리: 리팩토링 중에 기존 기능이 깨지지 않도록 기존 로직도 테스트 코드로 먼저 커버하는 게 좋겠습니다.

[결정 사항]
1. 정산 모듈 추상화 및 단계별 리팩토링 진행
2. 전략 패턴을 활용한 매체별 클래스 분리
3. 리팩토링 전 기존 로직 테스트 코드 작성 완료
4. 주 1회 진행 상황 공유 미팅

[Action Items]
- 박성호: 정산 도메인 클래스 설계안 공유 (기한: 이번 주 금요일, 우선순위: 높음)
- 최유리: 기존 로직 단위 테스트 코드 작성 (기한: 다음 주 월요일, 우선순위: 높음)
- 박성호: 전략 패턴 POC 구현 (기한: 다음 주 목요일, 우선순위: 중간)

[예상 효과]
- 신규 매체 추가 시간 단축 (3일 → 1일)
- 코드 가독성 향상
- 테스트 커버리지 증가로 버그 감소
- 유지보수 비용 감소""",
        "title": "레거시 정산 모듈 리팩토링 회의록",
        "source": "회의록_2024_04_20.md",
        "category": "회의록",
        "scope": "company",
    },
    {
        "content": """# 풀스택 개발자 긴급 채용 회의록

일시: 2024년 4월 25일
참석자: 장우진(HR 팀장), 강유진(HR 담당), 이지현(개발팀 리드)

[회의 배경]
Q2 프로젝트 일정이 촉박한 상황에서 개발 인력이 부족하여 풀스택 개발자 긴급 채용이 필요합니다.
현재 팀원들의 업무 강도가 높아 추가 인력 없이는 일정 준수가 어려운 상황입니다.

[논의 내용]
장우진: 연봉 책정이 너무 낮으면 좋은 인재 확보가 어렵습니다. 시장 평균보다 10% 높게 책정하는 게 좋겠습니다.
강유진: 시장 상황을 봐서는 지금이 적기입니다. 경쟁사들도 채용을 많이 하고 있어서 빨리 진행해야 합니다.
이지현: 업무 강도 고려하면 2명 채용이 맞을 것 같습니다. 1명으로는 부족할 것 같습니다.
장우진: 원격 근무 가능 여부도 명시하면 좋겠어요. 요즘 원격 근무 가능한 회사를 선호하는 지원자가 많습니다.
강유진: 채용 공고에 기술 스택과 프로젝트 내용을 구체적으로 명시하면 적합한 지원자를 받을 수 있을 것 같습니다.

[결정 사항]
1. 풀스택 개발자 2명 채용 진행
2. 급여 협상 범위: 시장 평균 대비 110% 수준
3. 주 2일 원격 근무 가능으로 공고
4. 기술 스택 명시: React, Node.js, PostgreSQL, AWS

[Action Items]
- 장우진: 채용 공고 작성 및 게시 (기한: 3일 이내, 우선순위: 높음)
- 강유진: 채용 플랫폼 등록 및 헤드헌터 컨택 (기한: 3일 이내, 우선순위: 높음)
- 이지현: 기술 면접 질문지 준비 (기한: 1주일 이내, 우선순위: 중간)
- 장우진: 온보딩 프로세스 점검 (기한: 2주 이내, 우선순위: 낮음)

[예상 일정]
- 채용 공고 게시: 4월 28일
- 서류 마감: 5월 12일
- 1차 면접: 5월 15-19일
- 최종 합격: 5월 26일
- 입사: 6월 3일

[예산]
- 연봉: 각 7,000만원 (총 1억 4천만원)
- 채용 비용: 500만원
- 온보딩 비용: 200만원""",
        "title": "풀스택 개발자 긴급 채용 회의록",
        "source": "회의록_2024_04_25.md",
        "category": "회의록",
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

    # 전체 문서 합치기
    all_documents = EXAMPLE_DOCUMENTS + MEETING_DOCUMENTS

    print(f"\nQdrant URL: {qdrant_url}")
    print(f"규정 문서 개수: {len(EXAMPLE_DOCUMENTS)}")
    print(f"회의록 문서 개수: {len(MEETING_DOCUMENTS)}")
    print(f"전체 문서 개수: {len(all_documents)}")

    # 1. Qdrant VectorStore 초기화
    print("\n[Step 1] Qdrant VectorStore 초기화...")
    vector_store = QdrantVectorStore(
        url=qdrant_url,
        api_key=qdrant_api_key,
        collection_name="documents",
    )

    # 기존 컬렉션이 있으면 삭제 (초기화)
    try:
        vector_store.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        collections = vector_store.client.get_collections().collections
        if any(c.name == "documents" for c in collections):
            print("  기존 컬렉션 삭제 중...")
            vector_store.delete_collection()
    except Exception as e:
        print(f"  컬렉션 삭제 중 오류 (무시): {e}")

    # 새로 초기화
    vector_store.initialize(vector_size=768)

    # 2. 임베딩 모델 로드
    print("\n[Step 2] 임베딩 모델 로드 (jhgan/ko-sbert-nli)...")
    embedding_model = EmbeddingModel()
    embedding_model.load_model()

    # 3. 문서 임베딩 생성
    print("\n[Step 3] 문서 임베딩 생성...")
    documents = [doc["content"] for doc in all_documents]
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
        for doc in all_documents
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

    # 테스트 1: 규정 검색
    test_query_1 = "연차 휴가는 몇 일 받을 수 있나요?"
    print(f"\n  [테스트 1] 질의: '{test_query_1}'")
    query_embedding = embedding_model.encode([test_query_1])[0]
    results = vector_store.search(query_embedding, top_k=3)
    print(f"  검색 결과 (Top 3):")
    for i, result in enumerate(results, 1):
        print(f"    {i}. [{result['title']}] (유사도: {result['score']:.4f})")
        print(f"       출처: {result['source']}")
        print(f"       내용: {result['content'][:100]}...")
        print()

    # 테스트 2: 회의록 검색
    test_query_2 = "코드리뷰 속도 개선 회의에서 어떤 내용이 논의되었나요?"
    print(f"\n  [테스트 2] 질의: '{test_query_2}'")
    query_embedding = embedding_model.encode([test_query_2])[0]
    results = vector_store.search(query_embedding, top_k=3)
    print(f"  검색 결과 (Top 3):")
    for i, result in enumerate(results, 1):
        print(f"    {i}. [{result['title']}] (유사도: {result['score']:.4f})")
        print(f"       출처: {result['source']}")
        print(f"       내용: {result['content'][:150]}...")
        print()

    print("="*60)
    print("✅ 완료! Qdrant에 예시 문서가 저장되었습니다.")
    print("="*60)


if __name__ == "__main__":
    main()
