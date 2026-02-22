# QA Baseline Experiment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Midm-2.0-Base-Instruct(4-bit)와 A.X-3.1-Light(4-bit) 두 모델의 QA 능력을 정량(ROUGE-L, Token F1) + 정성(답변 예시 저장) 방식으로 비교 평가한다.

**Architecture:** QA 샘플 JSON 40건(일반 20 + 업무 20)을 만들고, 단일 실험 스크립트가 두 모델을 순차 로드(bitsandbytes 4-bit) → 추론 → 지표 계산 → 결과 저장 순으로 동작한다.

**Tech Stack:** Python, transformers, bitsandbytes, rouge-score, torch (Colab L4 기준)

---

### Task 1: QA 샘플 데이터 생성

**Files:**
- Create: `ai/data/qa_samples.json`

**Step 1: 파일 생성**

아래 JSON을 `ai/data/qa_samples.json`에 저장한다. 일반(general) 20건 + 업무(business) 20건, 총 40건.

```json
[
  {
    "id": "gen_001",
    "domain": "general",
    "context": "대한민국의 수도는 서울특별시이다. 서울은 한반도 중서부에 위치하며, 한강이 도심을 가로질러 흐른다. 인구는 약 950만 명으로 대한민국에서 가장 인구가 많은 도시이다. 조선 왕조 시대에 수도로 지정된 이후 600년 이상 정치·경제·문화의 중심지 역할을 해왔다.",
    "question": "서울의 인구는 약 몇 명인가?",
    "answer": "약 950만 명"
  },
  {
    "id": "gen_002",
    "domain": "general",
    "context": "광합성은 식물이 햇빛 에너지를 이용해 이산화탄소와 물로부터 포도당을 합성하는 과정이다. 이 과정에서 산소가 부산물로 방출된다. 광합성은 엽록체 내의 엽록소에서 일어나며, 지구 생태계의 에너지 순환에서 핵심적인 역할을 한다.",
    "question": "광합성 과정에서 부산물로 방출되는 물질은 무엇인가?",
    "answer": "산소"
  },
  {
    "id": "gen_003",
    "domain": "general",
    "context": "세종대왕은 조선 제4대 왕으로, 재위 기간은 1418년부터 1450년까지이다. 그는 훈민정음을 창제하여 백성들이 쉽게 읽고 쓸 수 있도록 했으며, 천문학·음악·농업 등 다양한 분야에서 업적을 남겼다. 장영실을 등용하여 과학 기술 발전에도 크게 기여했다.",
    "question": "세종대왕이 창제한 문자 체계의 이름은?",
    "answer": "훈민정음"
  },
  {
    "id": "gen_004",
    "domain": "general",
    "context": "블랙홀은 중력이 매우 강해 빛조차 탈출하지 못하는 천체이다. 블랙홀의 경계를 사건 지평선이라고 하며, 이 경계를 넘은 물질은 되돌아올 수 없다. 블랙홀은 거대한 별이 수명을 다하고 붕괴할 때 생성되거나, 은하 중심에 초대질량 블랙홀 형태로 존재한다.",
    "question": "블랙홀에서 빛이 탈출하지 못하는 경계를 무엇이라 하는가?",
    "answer": "사건 지평선"
  },
  {
    "id": "gen_005",
    "domain": "general",
    "context": "대한민국의 법정 최저임금은 매년 고용노동부 산하 최저임금위원회에서 결정한다. 2024년 기준 시간당 최저임금은 9,860원이며, 주 40시간 기준 월 환산액은 약 206만 원이다. 최저임금 위반 시 사업주는 3년 이하의 징역 또는 2천만 원 이하의 벌금에 처해질 수 있다.",
    "question": "2024년 기준 대한민국 시간당 최저임금은 얼마인가?",
    "answer": "9,860원"
  },
  {
    "id": "gen_006",
    "domain": "general",
    "context": "인터넷 프로토콜(IP)은 네트워크에서 데이터를 패킷 단위로 전송하는 규칙의 집합이다. IP 주소는 네트워크 상의 각 장치를 식별하는 고유한 번호이다. 현재 널리 사용되는 IPv4는 32비트 주소 체계를 사용하며, 주소 고갈 문제로 인해 128비트 체계의 IPv6로 전환이 진행 중이다.",
    "question": "IPv4와 IPv6의 주소 비트 수는 각각 얼마인가?",
    "answer": "IPv4는 32비트, IPv6는 128비트"
  },
  {
    "id": "gen_007",
    "domain": "general",
    "context": "기후 위기 대응을 위해 2015년 파리협정이 체결되었다. 이 협정은 지구 평균 기온 상승을 산업화 이전 대비 1.5°C 이내로 제한하는 것을 목표로 한다. 196개국이 서명했으며, 각국은 국가별 온실가스 감축 목표(NDC)를 제출하고 이행 결과를 보고해야 한다.",
    "question": "파리협정이 체결된 연도는?",
    "answer": "2015년"
  },
  {
    "id": "gen_008",
    "domain": "general",
    "context": "혈액형은 적혈구 표면의 항원 종류에 따라 분류된다. ABO식 혈액형은 A형, B형, AB형, O형으로 구분되며, Rh식은 Rh+ 또는 Rh-로 나뉜다. AB형은 A항원과 B항원을 모두 가지고 있으며, O형은 두 항원 모두 없다. 수혈 시 혈액형 불일치는 심각한 합병증을 유발할 수 있다.",
    "question": "ABO식 혈액형 중 A항원과 B항원을 모두 가진 혈액형은?",
    "answer": "AB형"
  },
  {
    "id": "gen_009",
    "domain": "general",
    "context": "조선왕조실록은 조선 태조부터 철종까지 25대 472년간의 역사를 담은 기록물이다. 1973년 국보 제151호로 지정되었으며, 1997년에는 유네스코 세계기록유산으로 등재되었다. 총 2,077책, 약 6,400만 자로 이루어진 방대한 분량이 특징이다.",
    "question": "조선왕조실록이 유네스코 세계기록유산으로 등재된 연도는?",
    "answer": "1997년"
  },
  {
    "id": "gen_010",
    "domain": "general",
    "context": "태양계는 태양을 중심으로 8개의 행성이 공전하는 천체 시스템이다. 태양에서 가장 가까운 행성은 수성이고, 가장 먼 행성은 해왕성이다. 목성은 태양계에서 가장 큰 행성으로 지구 질량의 약 318배에 달한다. 2006년 국제천문연맹(IAU)은 명왕성을 행성에서 왜소행성으로 재분류했다.",
    "question": "태양계에서 태양과 가장 가까운 행성은?",
    "answer": "수성"
  },
  {
    "id": "gen_011",
    "domain": "general",
    "context": "DNA(디옥시리보핵산)는 생물체의 유전 정보를 담고 있는 분자로, 이중 나선 구조를 가진다. DNA는 아데닌(A), 구아닌(G), 사이토신(C), 티민(T) 네 가지 염기로 구성된다. A는 항상 T와, G는 항상 C와 수소 결합으로 쌍을 이룬다. 이 구조는 1953년 왓슨과 크릭이 규명했다.",
    "question": "DNA 이중 나선 구조를 규명한 과학자들은 누구인가?",
    "answer": "왓슨과 크릭"
  },
  {
    "id": "gen_012",
    "domain": "general",
    "context": "한국의 전통 발효 식품인 김치는 배추, 무 등 채소에 고춧가루, 마늘, 생강 등의 양념을 버무려 발효시킨 음식이다. 김치에는 유산균이 풍부하여 장 건강에 도움을 준다. 2013년 유네스코 인류무형문화유산으로 등재되었으며, 김장 문화도 함께 등재되었다.",
    "question": "김치가 유네스코 인류무형문화유산으로 등재된 연도는?",
    "answer": "2013년"
  },
  {
    "id": "gen_013",
    "domain": "general",
    "context": "경제학에서 GDP(국내총생산)는 일정 기간 동안 한 나라 안에서 생산된 모든 최종 재화와 서비스의 시장 가치 합계이다. GNP(국민총생산)는 자국 국민이 국내외에서 생산한 것의 합계이다. 한국은 2023년 기준 GDP 약 1조 7천억 달러로 세계 13위 경제 규모를 기록했다.",
    "question": "GDP와 GNP의 차이는 무엇인가?",
    "answer": "GDP는 일정 기간 국내에서 생산된 최종 재화·서비스의 합계이고, GNP는 자국 국민이 국내외에서 생산한 것의 합계이다."
  },
  {
    "id": "gen_014",
    "domain": "general",
    "context": "인공지능(AI)은 인간의 지능적 행동을 모방하는 컴퓨터 시스템이다. 머신러닝은 데이터를 통해 스스로 학습하는 AI의 하위 분야이며, 딥러닝은 다층 신경망을 이용한 머신러닝의 한 종류이다. 2022년 ChatGPT의 등장으로 생성형 AI가 대중화되었다.",
    "question": "딥러닝과 머신러닝의 관계를 간단히 설명하라.",
    "answer": "딥러닝은 다층 신경망을 이용한 머신러닝의 한 종류이다."
  },
  {
    "id": "gen_015",
    "domain": "general",
    "context": "한국의 의료보험 제도는 1977년 직장의료보험으로 시작하여 1989년 전 국민 의료보험이 실현되었다. 현재는 국민건강보험공단이 운영하는 단일 보험자 체계로, 직장가입자와 지역가입자로 구분된다. 보험료는 소득과 재산에 따라 차등 부과된다.",
    "question": "대한민국 전 국민 의료보험이 실현된 연도는?",
    "answer": "1989년"
  },
  {
    "id": "gen_016",
    "domain": "general",
    "context": "양자컴퓨터는 양자역학의 원리를 이용해 정보를 처리하는 컴퓨터이다. 기존 컴퓨터가 비트(0 또는 1) 단위로 정보를 처리하는 반면, 양자컴퓨터는 큐비트를 사용하여 0과 1을 동시에 나타낼 수 있다. 이를 중첩(superposition)이라 한다. Google은 2019년 양자 우월성을 달성했다고 발표했다.",
    "question": "양자컴퓨터에서 정보 처리의 기본 단위는?",
    "answer": "큐비트"
  },
  {
    "id": "gen_017",
    "domain": "general",
    "context": "한글날은 세종대왕이 훈민정음을 반포한 것을 기념하는 날로, 매년 10월 9일이다. 1949년 처음 공휴일로 지정되었다가 1990년 공휴일에서 제외되었으나, 2013년에 다시 공휴일로 복원되었다. 한글날은 한글의 우수성을 기리고 한글 사랑을 실천하는 날로 여러 기념 행사가 열린다.",
    "question": "한글날은 매년 몇 월 며칠인가?",
    "answer": "10월 9일"
  },
  {
    "id": "gen_018",
    "domain": "general",
    "context": "재생에너지는 태양광, 풍력, 수력, 지열, 바이오매스 등 자연에서 무한히 공급되는 에너지원을 활용하는 에너지이다. 화석연료와 달리 온실가스 배출이 거의 없어 탄소중립 달성에 핵심적인 역할을 한다. 국제재생에너지기구(IRENA)에 따르면 2023년 전 세계 재생에너지 발전 용량은 3,400GW를 넘었다.",
    "question": "재생에너지의 예를 세 가지 이상 제시하라.",
    "answer": "태양광, 풍력, 수력, 지열, 바이오매스 등"
  },
  {
    "id": "gen_019",
    "domain": "general",
    "context": "대한민국 헌법 제1조는 '대한민국은 민주공화국이다'와 '대한민국의 주권은 국민에게 있고, 모든 권력은 국민으로부터 나온다'로 구성되어 있다. 현행 헌법은 1987년 6월 민주화운동의 결과로 개정된 제9차 개헌으로, 대통령 직선제가 부활되었다.",
    "question": "현행 대한민국 헌법이 개정된 연도와 배경은?",
    "answer": "1987년, 6월 민주화운동의 결과로 개정되었으며 대통령 직선제가 부활되었다."
  },
  {
    "id": "gen_020",
    "domain": "general",
    "context": "커피는 전 세계에서 가장 많이 소비되는 음료 중 하나로, 에티오피아가 원산지로 알려져 있다. 커피의 주요 성분인 카페인은 중추신경계를 자극하여 각성 효과를 유발한다. 아라비카와 로부스타가 대표적인 커피 품종이며, 아라비카는 전 세계 생산량의 약 60~70%를 차지한다.",
    "question": "커피 품종 중 전 세계 생산량의 약 60~70%를 차지하는 것은?",
    "answer": "아라비카"
  },
  {
    "id": "biz_001",
    "domain": "business",
    "context": "2025년 4월 3일 오후 2시, 신제품 출시 전략 회의가 진행되었다. 참석자는 김민준 팀장, 이서연 마케팅 대리, 박지훈 개발 주임이었다. 회의에서는 신제품 '스마트 워크플로우 v2.0'의 출시일을 2025년 5월 20일로 확정하였다. 마케팅 예산은 총 3,000만 원으로 책정되었으며, SNS 광고에 1,500만 원, 오프라인 행사에 1,000만 원, 기타 500만 원을 배정하기로 했다.",
    "question": "신제품 출시일은 언제로 확정되었는가?",
    "answer": "2025년 5월 20일"
  },
  {
    "id": "biz_002",
    "domain": "business",
    "context": "2025년 4월 3일 오후 2시, 신제품 출시 전략 회의가 진행되었다. 참석자는 김민준 팀장, 이서연 마케팅 대리, 박지훈 개발 주임이었다. 회의에서는 신제품 '스마트 워크플로우 v2.0'의 출시일을 2025년 5월 20일로 확정하였다. 마케팅 예산은 총 3,000만 원으로 책정되었으며, SNS 광고에 1,500만 원, 오프라인 행사에 1,000만 원, 기타 500만 원을 배정하기로 했다.",
    "question": "SNS 광고에 배정된 예산은 얼마인가?",
    "answer": "1,500만 원"
  },
  {
    "id": "biz_003",
    "domain": "business",
    "context": "프로젝트 주간 보고서 (2025년 4월 2주차). 프로젝트명: ERP 시스템 고도화. 진행률: 67%. 이번 주 완료 사항: 사용자 인증 모듈 개발 완료, DB 마이그레이션 1차 완료. 이슈: QA 환경 서버 장애로 테스트 일정 3일 지연. 다음 주 목표: 결재 워크플로우 모듈 개발 착수, QA 서버 복구 후 테스트 재개.",
    "question": "이번 주 발생한 이슈는 무엇인가?",
    "answer": "QA 환경 서버 장애로 테스트 일정 3일 지연"
  },
  {
    "id": "biz_004",
    "domain": "business",
    "context": "프로젝트 주간 보고서 (2025년 4월 2주차). 프로젝트명: ERP 시스템 고도화. 진행률: 67%. 이번 주 완료 사항: 사용자 인증 모듈 개발 완료, DB 마이그레이션 1차 완료. 이슈: QA 환경 서버 장애로 테스트 일정 3일 지연. 다음 주 목표: 결재 워크플로우 모듈 개발 착수, QA 서버 복구 후 테스트 재개.",
    "question": "현재 프로젝트 진행률은 몇 퍼센트인가?",
    "answer": "67%"
  },
  {
    "id": "biz_005",
    "domain": "business",
    "context": "수신: 전 직원\n발신: 인사팀\n제목: 2025년 상반기 성과 평가 일정 안내\n\n안녕하세요. 인사팀입니다. 2025년 상반기 성과 평가 일정을 아래와 같이 안내드립니다. 자기 평가 기간: 4월 14일(월) ~ 4월 18일(금). 팀장 평가 기간: 4월 21일(월) ~ 4월 25일(금). 최종 결과 통보: 5월 9일(금). 성과 평가 시스템 접속은 사내 인트라넷 → HR포털에서 가능합니다.",
    "question": "자기 평가 기간은 언제부터 언제까지인가?",
    "answer": "4월 14일(월)부터 4월 18일(금)까지"
  },
  {
    "id": "biz_006",
    "domain": "business",
    "context": "수신: 전 직원\n발신: 인사팀\n제목: 2025년 상반기 성과 평가 일정 안내\n\n안녕하세요. 인사팀입니다. 2025년 상반기 성과 평가 일정을 아래와 같이 안내드립니다. 자기 평가 기간: 4월 14일(월) ~ 4월 18일(금). 팀장 평가 기간: 4월 21일(월) ~ 4월 25일(금). 최종 결과 통보: 5월 9일(금). 성과 평가 시스템 접속은 사내 인트라넷 → HR포털에서 가능합니다.",
    "question": "성과 평가 시스템에 어떻게 접속하는가?",
    "answer": "사내 인트라넷 → HR포털을 통해 접속한다."
  },
  {
    "id": "biz_007",
    "domain": "business",
    "context": "고객사 미팅 회의록 (2025년 3월 28일). 고객사: (주)테크솔루션. 담당자: 최현우 이사. 당사: 영업팀 정수빈 과장. 논의 내용: 1) 현재 도입 중인 CRM 솔루션의 데이터 마이그레이션 일정 조율. 2) 추가 라이선스 5개 구매 요청. 3) 기술지원 SLA를 현행 24시간에서 8시간으로 단축 요청. 후속 조치: 라이선스 견적서 발송(3/31), SLA 변경 검토 후 회신(4/4).",
    "question": "고객사가 요청한 기술지원 SLA 응답 시간은?",
    "answer": "8시간"
  },
  {
    "id": "biz_008",
    "domain": "business",
    "context": "고객사 미팅 회의록 (2025년 3월 28일). 고객사: (주)테크솔루션. 담당자: 최현우 이사. 당사: 영업팀 정수빈 과장. 논의 내용: 1) 현재 도입 중인 CRM 솔루션의 데이터 마이그레이션 일정 조율. 2) 추가 라이선스 5개 구매 요청. 3) 기술지원 SLA를 현행 24시간에서 8시간으로 단축 요청. 후속 조치: 라이선스 견적서 발송(3/31), SLA 변경 검토 후 회신(4/4).",
    "question": "라이선스 견적서는 언제 발송하기로 했는가?",
    "answer": "3월 31일"
  },
  {
    "id": "biz_009",
    "domain": "business",
    "context": "사내 공지: IT 보안 정책 강화 안내 (시행일: 2025년 5월 1일). 주요 변경 사항: 1) 비밀번호 변경 주기: 90일 → 60일로 단축. 2) VPN 미접속 시 사내 시스템 접근 불가. 3) 개인 USB 사용 전면 금지, 승인된 클라우드 스토리지만 허용. 4) 퇴근 후 업무 PC 전원 반드시 종료. 위반 시 보안 감사 대상이 될 수 있습니다.",
    "question": "변경된 비밀번호 변경 주기는?",
    "answer": "60일"
  },
  {
    "id": "biz_010",
    "domain": "business",
    "context": "사내 공지: IT 보안 정책 강화 안내 (시행일: 2025년 5월 1일). 주요 변경 사항: 1) 비밀번호 변경 주기: 90일 → 60일로 단축. 2) VPN 미접속 시 사내 시스템 접근 불가. 3) 개인 USB 사용 전면 금지, 승인된 클라우드 스토리지만 허용. 4) 퇴근 후 업무 PC 전원 반드시 종료. 위반 시 보안 감사 대상이 될 수 있습니다.",
    "question": "개인 USB 대신 허용되는 대안은?",
    "answer": "승인된 클라우드 스토리지"
  },
  {
    "id": "biz_011",
    "domain": "business",
    "context": "2025년 2분기 영업 실적 보고. 총 매출: 42억 3,500만 원 (전분기 대비 +8.2%). 신규 계약: 17건. 계약 해지: 3건. 순증 고객 수: 14명. 최대 계약 건: 스마트시티 솔루션 공급 계약 (계약금액 8억 원). 목표 달성률: 94.1% (목표: 45억 원). 미달 원인: 공공 부문 예산 집행 지연으로 2건 계약 4분기로 이월.",
    "question": "2분기 목표 달성률은 몇 퍼센트인가?",
    "answer": "94.1%"
  },
  {
    "id": "biz_012",
    "domain": "business",
    "context": "2025년 2분기 영업 실적 보고. 총 매출: 42억 3,500만 원 (전분기 대비 +8.2%). 신규 계약: 17건. 계약 해지: 3건. 순증 고객 수: 14명. 최대 계약 건: 스마트시티 솔루션 공급 계약 (계약금액 8억 원). 목표 달성률: 94.1% (목표: 45억 원). 미달 원인: 공공 부문 예산 집행 지연으로 2건 계약 4분기로 이월.",
    "question": "목표 달성에 미달한 원인은 무엇인가?",
    "answer": "공공 부문 예산 집행 지연으로 2건 계약이 4분기로 이월되었기 때문"
  },
  {
    "id": "biz_013",
    "domain": "business",
    "context": "팀 회의록 (2025년 4월 10일). 안건: 재택근무 정책 조정. 현행: 주 2회 재택. 논의 결과: 팀원 6명 중 5명이 주 3회 재택 확대 희망. 팀장 의견: 업무 성과 지표 달성 조건부 주 3회 허용 가능. 결정사항: 4월부터 주 3회 재택 시범 운영(3개월), 7월 재평가 후 정책 확정. 단, 전사 주요 회의일(매주 화요일)은 반드시 출근.",
    "question": "재택근무 시범 운영 기간은 얼마인가?",
    "answer": "3개월 (4월부터 7월 재평가까지)"
  },
  {
    "id": "biz_014",
    "domain": "business",
    "context": "팀 회의록 (2025년 4월 10일). 안건: 재택근무 정책 조정. 현행: 주 2회 재택. 논의 결과: 팀원 6명 중 5명이 주 3회 재택 확대 희망. 팀장 의견: 업무 성과 지표 달성 조건부 주 3회 허용 가능. 결정사항: 4월부터 주 3회 재택 시범 운영(3개월), 7월 재평가 후 정책 확정. 단, 전사 주요 회의일(매주 화요일)은 반드시 출근.",
    "question": "반드시 출근해야 하는 요일은?",
    "answer": "매주 화요일"
  },
  {
    "id": "biz_015",
    "domain": "business",
    "context": "신입사원 온보딩 안내. 입사일: 2025년 5월 2일(금). 첫 주 일정: 5/2 회사 소개 및 팀 배정, 5/5 보안 교육 및 장비 지급, 5/7 업무 시스템 교육, 5/8 멘토 배정 및 OJT 시작. 준비물: 신분증, 통장 사본, 최종 학력 증명서. 문의: 인사팀 박소연 (내선 1234).",
    "question": "업무 시스템 교육은 언제 진행되는가?",
    "answer": "5월 7일"
  },
  {
    "id": "biz_016",
    "domain": "business",
    "context": "리스크 관리 보고서 (2025년 Q1). 식별된 주요 리스크: 1) 핵심 인력 이탈 위험 (가능성: 중, 영향도: 높음) → 대응: 리텐션 패키지 도입 검토. 2) 공급망 불안정 (가능성: 높음, 영향도: 중) → 대응: 복수 공급업체 계약 완료. 3) 규제 변경 (가능성: 낮음, 영향도: 높음) → 대응: 법무팀 모니터링 강화. 전체 리스크 수준: 보통.",
    "question": "공급망 불안정 리스크에 대한 대응 방안은?",
    "answer": "복수 공급업체 계약 완료"
  },
  {
    "id": "biz_017",
    "domain": "business",
    "context": "예산 집행 현황 (2025년 3월 기준). 총 예산: 12억 원. 집행 완료: 7억 2,000만 원 (60%). 잔여 예산: 4억 8,000만 원. 주요 집행 내역: 인건비 4억 2,000만 원, 마케팅 1억 5,000만 원, 인프라 8,000만 원, 기타 7,000만 원. 4분기 추가 예산 신청 예정 항목: AI 솔루션 도입 (예상 1억 5,000만 원).",
    "question": "3월 기준 예산 집행률은 몇 퍼센트인가?",
    "answer": "60%"
  },
  {
    "id": "biz_018",
    "domain": "business",
    "context": "고객 서비스 팀 월간 리포트 (2025년 3월). 총 접수 문의: 1,842건. 처리 완료: 1,798건. 미처리: 44건. 평균 응답 시간: 2.3시간. 고객 만족도(CSAT): 4.2/5.0. 주요 불만 유형: 배송 지연 38%, 제품 불량 27%, 환불 처리 21%, 기타 14%. 개선 조치: 배송 파트너사 변경 검토 중.",
    "question": "고객 불만 중 가장 높은 비율을 차지하는 유형은?",
    "answer": "배송 지연 (38%)"
  },
  {
    "id": "biz_019",
    "domain": "business",
    "context": "계약서 요약. 계약명: 소프트웨어 유지보수 서비스 계약. 갑: (주)알파테크. 을: (주)베타소프트. 계약 기간: 2025년 4월 1일 ~ 2026년 3월 31일 (1년). 계약 금액: 연 2,400만 원 (월 200만 원). 서비스 범위: 소프트웨어 버그 수정, 보안 패치, 월 1회 정기 점검. 위약금: 계약 해지 시 잔여 계약금의 20%.",
    "question": "계약 해지 시 위약금은 얼마인가?",
    "answer": "잔여 계약금의 20%"
  },
  {
    "id": "biz_020",
    "domain": "business",
    "context": "계약서 요약. 계약명: 소프트웨어 유지보수 서비스 계약. 갑: (주)알파테크. 을: (주)베타소프트. 계약 기간: 2025년 4월 1일 ~ 2026년 3월 31일 (1년). 계약 금액: 연 2,400만 원 (월 200만 원). 서비스 범위: 소프트웨어 버그 수정, 보안 패치, 월 1회 정기 점검. 위약금: 계약 해지 시 잔여 계약금의 20%.",
    "question": "이 계약에서 제공하는 서비스 범위는?",
    "answer": "소프트웨어 버그 수정, 보안 패치, 월 1회 정기 점검"
  }
]
```

**Step 2: 데이터 확인**

```bash
python -c "
import json
with open('ai/data/qa_samples.json', encoding='utf-8') as f:
    data = json.load(f)
general = [d for d in data if d['domain'] == 'general']
business = [d for d in data if d['domain'] == 'business']
print(f'총 {len(data)}건: general={len(general)}, business={len(business)}')
"
```

Expected:
```
총 40건: general=20, business=20
```

**Step 3: Commit**

```bash
git add ai/data/qa_samples.json
git commit -m "feat: QA baseline 샘플 데이터 40건 생성 (일반 20 + 업무 20)"
```

---

### Task 2: 실험 스크립트 작성

**Files:**
- Create: `ai/experiments/run_qa_baseline.py`

**Step 1: 파일 생성**

`ai/experiments/run_qa_baseline.py`를 아래 코드로 생성한다.

```python
"""
QA Baseline 실험: Midm-2.0-Base-Instruct vs A.X-3.1-Light

두 한국어 sLLM의 QA 능력을 정량(ROUGE-L, Token F1) + 정성(답변 저장) 방식으로 비교한다.

사용법:
    # 두 모델 모두 실행
    python ai/experiments/run_qa_baseline.py

    # 특정 모델만 실행
    python ai/experiments/run_qa_baseline.py --model midm
    python ai/experiments/run_qa_baseline.py --model ax

    # Colab 환경 예시
    !python ai/experiments/run_qa_baseline.py --model midm

환경:
    pip install transformers bitsandbytes accelerate rouge-score torch
    GPU: Colab L4 (24GB VRAM) 권장
"""

import argparse
import json
import re
import time
from pathlib import Path
from collections import Counter

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from rouge_score import rouge_scorer

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = BASE_DIR / "ai" / "data" / "qa_samples.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── 모델 설정 ──
MODEL_CONFIGS = {
    "midm": {
        "model_id": "K-intelligence/Midm-2.0-Base-Instruct",
        "short_name": "Midm-2.0-Base",
        "max_new_tokens": 128,
    },
    "ax": {
        "model_id": "skt/A.X-3.1-Light",
        "short_name": "A.X-3.1-Light",
        "max_new_tokens": 128,
    },
}

# ── 정성 평가용 저장 개수 ──
QUALITATIVE_SAMPLE_IDS = [
    "gen_001", "gen_005", "gen_010", "gen_014", "gen_019",
    "biz_001", "biz_003", "biz_007", "biz_011", "biz_017",
]


# ── 데이터 로드 ──

def load_qa_samples():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── 지표 계산 ──

def normalize_answer(text: str) -> str:
    """답변 텍스트 정규화 (공백, 특수문자 처리)"""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s가-힣]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def token_f1(pred: str, gold: str) -> float:
    """SQuAD 방식 토큰 F1 (한국어 어절 단위)"""
    pred_tokens = normalize_answer(pred).split()
    gold_tokens = normalize_answer(gold).split()
    if not pred_tokens or not gold_tokens:
        return 0.0
    pred_counter = Counter(pred_tokens)
    gold_counter = Counter(gold_tokens)
    common = sum((pred_counter & gold_counter).values())
    if common == 0:
        return 0.0
    precision = common / len(pred_tokens)
    recall = common / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def rouge_l(pred: str, gold: str, scorer) -> float:
    """ROUGE-L F1"""
    result = scorer.score(gold, pred)
    return result["rougeL"].fmeasure


# ── 모델 로드 ──

def load_model_4bit(model_id: str):
    """bitsandbytes 4-bit 양자화로 모델 로드"""
    print(f"\n  모델 로드 중: {model_id}")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    print(f"  로드 완료. Device map: {model.hf_device_map}")
    return tokenizer, model


# ── 추론 ──

def build_prompt(tokenizer, context: str, question: str) -> str:
    """chat template 적용 QA 프롬프트 생성"""
    user_msg = f"다음 글을 읽고 질문에 간결하게 답하세요.\n\n[글]\n{context}\n\n[질문]\n{question}"
    messages = [{"role": "user", "content": user_msg}]
    try:
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    except Exception:
        # chat template 미지원 시 fallback
        prompt = f"[지문]\n{context}\n\n[질문]\n{question}\n\n[답변]\n"
    return prompt


def generate_answer(tokenizer, model, context: str, question: str, max_new_tokens: int) -> str:
    """단일 QA 추론"""
    prompt = build_prompt(tokenizer, context, question)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    input_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = outputs[0][input_len:]
    answer = tokenizer.decode(generated, skip_special_tokens=True).strip()
    # 첫 줄만 취함 (모델이 추가 설명을 붙이는 경우 방지)
    answer = answer.split("\n")[0].strip()
    return answer


# ── 메인 평가 루프 ──

def evaluate_model(model_key: str, samples: list) -> dict:
    cfg = MODEL_CONFIGS[model_key]
    tokenizer, model = load_model_4bit(cfg["model_id"])
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)

    predictions = []
    total_time = 0.0

    print(f"\n  [{cfg['short_name']}] 추론 시작 ({len(samples)}건)")
    for i, sample in enumerate(samples, 1):
        t0 = time.time()
        pred = generate_answer(
            tokenizer, model,
            sample["context"], sample["question"],
            cfg["max_new_tokens"],
        )
        elapsed = time.time() - t0
        total_time += elapsed

        tf1 = token_f1(pred, sample["answer"])
        rl = rouge_l(pred, sample["answer"], scorer)

        predictions.append({
            "id": sample["id"],
            "domain": sample["domain"],
            "question": sample["question"],
            "gold_answer": sample["answer"],
            "pred_answer": pred,
            "token_f1": round(tf1, 4),
            "rouge_l": round(rl, 4),
            "infer_sec": round(elapsed, 2),
        })

        print(f"    [{i:02d}/{len(samples)}] {sample['id']} | TF1={tf1:.3f} ROUGE-L={rl:.3f} | '{pred[:40]}...'")

    # 메모리 해제
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return {
        "model_key": model_key,
        "model_id": cfg["model_id"],
        "short_name": cfg["short_name"],
        "predictions": predictions,
        "total_infer_sec": round(total_time, 2),
        "avg_infer_sec": round(total_time / len(samples), 2),
    }


# ── 지표 집계 ──

def compute_summary(result: dict) -> dict:
    preds = result["predictions"]

    def avg_metrics(items):
        if not items:
            return {"token_f1": 0.0, "rouge_l": 0.0, "count": 0}
        return {
            "token_f1": round(sum(p["token_f1"] for p in items) / len(items), 4),
            "rouge_l": round(sum(p["rouge_l"] for p in items) / len(items), 4),
            "count": len(items),
        }

    general = [p for p in preds if p["domain"] == "general"]
    business = [p for p in preds if p["domain"] == "business"]

    return {
        "model": result["short_name"],
        "model_id": result["model_id"],
        "overall": avg_metrics(preds),
        "general": avg_metrics(general),
        "business": avg_metrics(business),
        "avg_infer_sec": result["avg_infer_sec"],
        "total_infer_sec": result["total_infer_sec"],
    }


# ── 결과 출력 ──

def print_comparison(summaries: list):
    print("\n" + "=" * 70)
    print("  QA Baseline 결과 비교")
    print("=" * 70)
    header = f"  {'모델':<20} {'전체 TF1':>10} {'전체 RL':>10} {'일반 TF1':>10} {'업무 TF1':>10} {'속도(s)':>8}"
    print(header)
    print("  " + "-" * 68)
    for s in summaries:
        print(
            f"  {s['model']:<20}"
            f" {s['overall']['token_f1']:>10.4f}"
            f" {s['overall']['rouge_l']:>10.4f}"
            f" {s['general']['token_f1']:>10.4f}"
            f" {s['business']['token_f1']:>10.4f}"
            f" {s['avg_infer_sec']:>8.2f}"
        )
    print("=" * 70)


# ── 정성 평가 샘플 추출 ──

def extract_qualitative(all_results: list) -> list:
    qualitative = []
    for result in all_results:
        model_samples = []
        for pred in result["predictions"]:
            if pred["id"] in QUALITATIVE_SAMPLE_IDS:
                model_samples.append(pred)
        qualitative.append({
            "model": result["short_name"],
            "samples": model_samples,
        })
    return qualitative


# ── 저장 ──

def save_results(all_results: list, summaries: list):
    # 정량 결과
    quant_path = RESULTS_DIR / "qa_quantitative.json"
    with open(quant_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)
    print(f"\n  [저장] {quant_path}")

    # 정성 결과 (전체 예측 + 정성 샘플 플래그)
    qual_data = []
    for result in all_results:
        for pred in result["predictions"]:
            entry = {
                "model": result["short_name"],
                "qualitative_sample": pred["id"] in QUALITATIVE_SAMPLE_IDS,
                **pred,
            }
            qual_data.append(entry)

    qual_path = RESULTS_DIR / "qa_qualitative.json"
    with open(qual_path, "w", encoding="utf-8") as f:
        json.dump(qual_data, f, ensure_ascii=False, indent=2)
    print(f"  [저장] {qual_path}")


# ── 엔트리포인트 ──

def main():
    parser = argparse.ArgumentParser(description="QA Baseline 실험")
    parser.add_argument(
        "--model",
        choices=["midm", "ax", "all"],
        default="all",
        help="실행할 모델 (기본: all)",
    )
    args = parser.parse_args()

    target_keys = ["midm", "ax"] if args.model == "all" else [args.model]

    samples = load_qa_samples()
    print(f"데이터 로드: {len(samples)}건")

    all_results = []
    summaries = []

    for key in target_keys:
        print(f"\n{'=' * 70}")
        print(f"  모델: {MODEL_CONFIGS[key]['short_name']}")
        print(f"{'=' * 70}")

        result = evaluate_model(key, samples)
        summary = compute_summary(result)

        all_results.append(result)
        summaries.append(summary)

        print(f"\n  [{summary['model']}] 완료")
        print(f"    전체 Token F1: {summary['overall']['token_f1']:.4f}")
        print(f"    전체 ROUGE-L : {summary['overall']['rouge_l']:.4f}")
        print(f"    일반 Token F1: {summary['general']['token_f1']:.4f}")
        print(f"    업무 Token F1: {summary['business']['token_f1']:.4f}")
        print(f"    평균 추론 시간: {summary['avg_infer_sec']:.2f}s/sample")

    if len(summaries) > 1:
        print_comparison(summaries)

    save_results(all_results, summaries)
    print("\n실험 완료!")


if __name__ == "__main__":
    main()
```

**Step 2: 문법 검사 (의존성 없이)**

```bash
python -m py_compile ai/experiments/run_qa_baseline.py && echo "OK"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add ai/experiments/run_qa_baseline.py
git commit -m "feat: QA baseline 실험 스크립트 작성 (Midm vs A.X-3.1-Light)"
```

---

### Task 3: Colab 실행 및 결과 확인

**Step 1: Colab 노트북 준비**

Colab에서 아래 셀을 순서대로 실행한다.

```python
# 셀 1: 저장소 클론 및 의존성 설치
!git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM.git
%cd SKN21-FINAL-3TEAM

!pip install -q transformers bitsandbytes accelerate rouge-score
```

```python
# 셀 2: PYTHONPATH 설정
import sys, os
sys.path.insert(0, os.getcwd())
```

```python
# 셀 3: Midm 먼저 실행
!python ai/experiments/run_qa_baseline.py --model midm
```

```python
# 셀 4: A.X 실행
!python ai/experiments/run_qa_baseline.py --model ax
```

**Step 2: 결과 확인**

```python
# 셀 5: 정량 결과 출력
import json

with open("ai/experiments/results/qa_quantitative.json", encoding="utf-8") as f:
    quant = json.load(f)

for s in quant:
    print(f"\n모델: {s['model']}")
    print(f"  전체 Token F1: {s['overall']['token_f1']:.4f}")
    print(f"  전체 ROUGE-L : {s['overall']['rouge_l']:.4f}")
    print(f"  일반 Token F1: {s['general']['token_f1']:.4f}")
    print(f"  업무 Token F1: {s['business']['token_f1']:.4f}")
```

```python
# 셀 6: 정성 샘플 출력 (정성 평가용 10건)
with open("ai/experiments/results/qa_qualitative.json", encoding="utf-8") as f:
    qual = json.load(f)

qual_samples = [q for q in qual if q["qualitative_sample"]]
for entry in qual_samples:
    print(f"\n[{entry['model']}] {entry['id']}")
    print(f"  Q: {entry['question']}")
    print(f"  Gold: {entry['gold_answer']}")
    print(f"  Pred: {entry['pred_answer']}")
    print(f"  TF1={entry['token_f1']:.3f} RL={entry['rouge_l']:.3f}")
```

**Step 3: 결과 파일 로컬로 내려받기**

Colab에서:
```python
from google.colab import files
files.download("ai/experiments/results/qa_quantitative.json")
files.download("ai/experiments/results/qa_qualitative.json")
```

**Step 4: 결과 커밋 (로컬에서)**

결과 파일을 `ai/experiments/results/`에 복사 후:
```bash
git add ai/experiments/results/qa_quantitative.json ai/experiments/results/qa_qualitative.json
git commit -m "feat: QA baseline 실험 결과 저장 (Midm vs A.X-3.1-Light)"
```
