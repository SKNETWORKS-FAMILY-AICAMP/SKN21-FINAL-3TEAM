"""
회의록 예시 데이터를 Qdrant에 저장하는 시드 스크립트

실행 방법 (프로젝트 루트에서):
    python -m ai.tests.seed_meeting_minutes

주의: QDRANT_URL, QDRANT_API_KEY 환경변수(.env)가 설정되어 있어야 합니다.
"""
import sys
import os

# 프로젝트 루트를 sys.path에 추가 (직접 실행 시)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from ai.rag.qdrant_pipeline import get_qdrant_pipeline

# ────────────────────────────────────────────────────────────────
# 회의록 예시 데이터 (각 항목 = Qdrant에 저장될 하나의 청크)
# ────────────────────────────────────────────────────────────────

MEETING_DOCUMENTS = [

    # ── 회의록 1: AI 개발팀 주간 회의 (2026-02-17) ──────────────
    """[AI 개발팀 주간 회의록]
날짜: 2026년 2월 17일 (월) 14:00 ~ 15:30
참석자: 신지용(PM), 진승언(AI리드), 윤경은(AI서브), 안혜빈(Backend), 문지영(Frontend)
장소: 회의실 B / 화상회의 병행

■ 안건 1. 주간 진행 현황 공유
- 진승언: 문서 생성 에이전트 개발 70% 완료. 회의록·보고서·제안서 3종 DOCX 자동 생성 구현.
  Solar-1-mini 모델에서 복잡한 JSON 구조 반환 시 오류 발생 → 후처리 로직 보강 완료.
- 윤경은: RAG 파이프라인 Qdrant 연동 50% 완료. BM25+벡터 하이브리드 검색 RRF 합산 구현.
- 안혜빈: Google Calendar 연동 모듈 30% 완료. OAuth 2.0 토큰 갱신 로직 구현 중.
- 문지영: 문서 생성 페이지 UI 60% 완료. 채팅 스트리밍 SSE 연결 안정화.

■ 안건 2. 이슈 및 리스크 논의
- Solar LLM 응답 속도 평균 4~6초 → 스트리밍 방식으로 UX 개선 필요 (담당: 진승언, 기한: 2/28)
- AWS 인프라 비용이 예상 대비 10~15% 초과 가능 → 스팟 인스턴스 활용 방안 검토 (담당: 신지용)

■ 결정사항
1. 문서 에이전트 스트리밍 응답 방식으로 전환 (2/28까지)
2. 소형 LLM(solar-1-mini) → solar-pro 모델 업그레이드 검토 (3/7 결정)
3. 다음 회의: 2026년 2월 24일 (월) 14:00

■ Action Items
- 진승언: 문서 에이전트 스트리밍 구현 (기한: 2026-02-28)
- 신지용: AWS 스팟 인스턴스 비용 분석 보고서 작성 (기한: 2026-02-21)
- 안혜빈: Google Calendar API 권한 범위 확인 및 공유 (기한: 2026-02-19)
- 윤경은: Qdrant 초기 데이터 구축 완료 (기한: 2026-02-24)""",

    # ── 회의록 2: AI 개발팀 주간 회의 (2026-02-24) ──────────────
    """[AI 개발팀 주간 회의록]
날짜: 2026년 2월 24일 (월) 14:00 ~ 15:00
참석자: 신지용(PM), 진승언(AI리드), 윤경은(AI서브), 안혜빈(Backend), 문지영(Frontend)
장소: 회의실 A

■ 안건 1. 주간 진행 현황 공유
- 진승언: 문서 에이전트 스트리밍 구현 완료. DOCX 다운로드 기능 정상 동작 확인.
  제안서 생성 시 진행현황 테이블 키 불일치 버그 수정 완료.
- 윤경은: Qdrant 벡터 DB 회사 규정 문서 100건 이상 업로드 완료.
  doc_qa 기능 연동 테스트 시작.
- 안혜빈: Google Calendar 일정 조회·등록 API 구현 완료. 토큰 자동 갱신 정상 동작.
- 문지영: 문서 생성 페이지 완성. 일정 관리 페이지 UI 착수.

■ 안건 2. Solar 모델 업그레이드 검토 결과
- solar-1-mini → solar-pro 전환 시 API 비용 약 3배 증가
- 현재 후처리 로직 보강으로 solar-1-mini 품질 개선됨 → 당분간 유지 결정
- 파인튜닝 후 sLLM 전환 시 재검토 예정

■ 결정사항
1. Solar 모델: solar-1-mini 유지 (파인튜닝 후 재검토)
2. 다음 스프린트 목표: doc_qa + 일정 에이전트 통합 테스트
3. 3월 파일럿 테스트 대상 부서: 경영전략팀 협의 예정 (신지용 담당)
4. 다음 회의: 2026년 3월 3일 (월) 14:00

■ Action Items
- 진승언: doc_qa 프론트엔드 출처 표시 카드 구현 (기한: 2026-03-03)
- 윤경은: doc_qa 검색 정확도 평가 지표 작성 (기한: 2026-03-03)
- 신지용: 경영전략팀 파일럿 테스트 협의 (기한: 2026-02-28)
- 문지영: 일정 관리 페이지 기본 UI 완성 (기한: 2026-03-03)""",

    # ── 회의록 3: 멘토 미팅 (2026-02-20) ────────────────────────
    """[멘토 미팅 회의록]
날짜: 2026년 2월 20일 (목) 10:00 ~ 11:00
참석자: 신지용(PM), 진승언(AI리드), 윤경은(AI서브) / 멘토: 김태훈 멘토
형식: 화상회의 (Google Meet)

■ 멘토 피드백 요약

1. RAG 파이프라인 구조
- 멘토: "BM25+벡터 하이브리드 검색 + RRF 합산 구조는 적절하다. Reranker(Cross-Encoder)는
  응답 속도 병목이 있으니 비활성화 결정은 합리적이다."
- 멘토: "Qdrant scope 필터링으로 회사/개인 문서를 분리하는 방식은 보안상 좋은 접근이다."

2. 문서 생성 에이전트
- 멘토: "Solar-mini 모델의 JSON 오류는 모델 크기 한계다. 후처리 정규화 방향은 맞다.
  프롬프트를 sys_prompt(설명)와 user_prompt(데이터)로 분리하는 것도 좋은 방법."
- 멘토: "DOCX 생성 시 python-docx는 적절한 선택. 나중에 PDF 변환도 고려해볼 것."

3. 아키텍처 전반
- 멘토: "LangGraph 멀티에이전트 구조에서 오케스트레이터가 너무 많은 로직을 담당하지 않도록
  각 서브에이전트에 책임을 명확히 분리할 것."
- 멘토: "4단계 파인튜닝 전 데이터 수집 시 입력/출력 쌍을 명확히 정의해야 한다."

■ 결정사항
1. Reranker 비활성화 유지 (RRF로 충분한 품질 확보)
2. 프롬프트 분리 전략(sys/user) 전 에이전트에 적용
3. 향후 PDF 변환 기능 백로그에 추가

■ 다음 멘토 미팅: 2026년 3월 20일""",

    # ── 회의록 4: 경영전략팀 파일럿 협의 (2026-02-28) ───────────
    """[파일럿 테스트 협의 회의록]
날짜: 2026년 2월 28일 (금) 15:00 ~ 16:00
참석자: 신지용(PM), 경영전략팀 박민준 팀장, 이수진 과장
장소: 회의실 C

■ 협의 내용

1. 파일럿 테스트 범위
- 경영전략팀 소속 10명 대상 4주간 시범 운영 (3월 1일 ~ 3월 28일)
- 테스트 기능: AI 문서 자동 생성 (보고서·회의록), 사내 규정 Q&A 챗봇

2. 경영전략팀 요구사항
- 보고서 생성 시 팀 양식(로고, 폰트)을 유지할 수 있으면 좋겠다.
- 회의록에서 Action Item을 Google 캘린더에 자동 등록되면 유용할 것.
- 모바일 환경 지원 여부 확인 요청.

3. 보안 및 데이터 처리
- 경영전략팀 문서는 팀 내에서만 접근 가능해야 함 → scope 필터링으로 대응 가능 확인.
- 민감한 전략 문서는 AI 학습 데이터로 사용하지 않을 것을 확약.

■ 결정사항
1. 파일럿 테스트 일정: 2026년 3월 1일 시작 확정
2. 팀 양식 커스터마이징: 3단계 백로그에 추가 (현재 기본 양식으로 진행)
3. Action Item → Google Calendar 자동 연동: 3월 내 구현 목표 (안혜빈 담당)
4. 모바일 대응: Tailwind 반응형으로 기본 지원, 최적화는 추후

■ Action Items
- 신지용: 파일럿 테스트 가이드 문서 작성 및 배포 (기한: 2026-03-01)
- 안혜빈: Action Item → Google Calendar 자동 연동 구현 (기한: 2026-03-21)
- 진승언: 경영전략팀 계정 생성 및 테스트 환경 구성 (기한: 2026-03-01)""",
]

MEETING_METADATAS = [
    {
        "source": "meeting_minutes",
        "title": "AI 개발팀 주간 회의록 (2026-02-17)",
        "scope": "company",
        "document_type": "meeting_minutes",
        "date": "2026-02-17",
    },
    {
        "source": "meeting_minutes",
        "title": "AI 개발팀 주간 회의록 (2026-02-24)",
        "scope": "company",
        "document_type": "meeting_minutes",
        "date": "2026-02-24",
    },
    {
        "source": "meeting_minutes",
        "title": "멘토 미팅 회의록 (2026-02-20)",
        "scope": "company",
        "document_type": "meeting_minutes",
        "date": "2026-02-20",
    },
    {
        "source": "meeting_minutes",
        "title": "파일럿 테스트 협의 회의록 (2026-02-28)",
        "scope": "company",
        "document_type": "meeting_minutes",
        "date": "2026-02-28",
    },
]


def main():
    print("=" * 60)
    print("회의록 예시 데이터 Qdrant 저장 시작")
    print("=" * 60)

    print("\n[1/2] QdrantRAGPipeline 초기화 중...")
    pipeline = get_qdrant_pipeline()
    print("      초기화 완료!")

    print(f"\n[2/2] 회의록 {len(MEETING_DOCUMENTS)}건 저장 중...")
    pipeline.add_documents(
        documents=MEETING_DOCUMENTS,
        metadatas=MEETING_METADATAS,
    )

    print("\n" + "=" * 60)
    print(f"완료! 총 {len(MEETING_DOCUMENTS)}건의 회의록이 Qdrant에 저장되었습니다.")
    print("\n테스트 질문 예시:")
    print("  - '2월 17일 회의에서 결정된 사항이 뭐야?'")
    print("  - '회의록에 Action Item이 뭐가 있어?'")
    print("  - '파일럿 테스트 대상 부서가 어디야?'")
    print("  - '멘토가 RAG에 대해 뭐라고 했어?'")
    print("=" * 60)


if __name__ == "__main__":
    main()
