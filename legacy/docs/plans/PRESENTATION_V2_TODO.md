# Presentation v2 — 남은 작업 (2026-03-27)

## 구현 완료
- [x] nav dots / TOC / JS / 섹션 번호 업데이트
- [x] 화면 구성(pages) 섹션 삭제
- [x] 성능 평가(performance) 섹션 삭제

## 지금 구현 중
- [ ] 11: Base 모델 한계 섹션 — 실제 출력 예시 기반
- [ ] 12: 판단 Agent 성과 섹션
- [ ] 13: 문서생성 Agent 성과 섹션
- [ ] 14: 문서요약 Agent 성과 섹션

## 부족한 데이터 (나중에 준비 필요)
- [ ] **실제 LoRA 출력 예시 텍스트**: `outputs/` 폴더에서 LoRA 모델의 실제 JSON 출력을 확인해서 성과 페이지에 반영 필요
- [ ] **데모 영상 (5분)**: 발표 후반에 넣을 데모 영상 촬영 필요
  - 추천 시나리오: 판단 → 문서생성 → 일정등록
- [ ] **presentation.html v1과 v2 비교 후 빠진 내용 없는지 최종 확인**

## 데이터 소스 (확인됨)
- 판단 Base 출력: `outputs/v1_judgment/eval_results.json`
- 문서생성 Base 출력: `outputs/v3_generate/eval_results/qualitative_base.json`
- 문서요약 Base 출력: `outputs/v3_summary/kanana-1.5-8b-instruct-2505/qualitative_samples.json`
