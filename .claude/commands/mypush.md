# Git Push (내 브랜치만)

현재 브랜치의 변경사항을 origin에 push한다. develop은 건드리지 않는다.

## 실행 절차

1. `git status`로 커밋 안 된 변경사항 확인
   - 커밋 안 된 변경사항이 있으면 사용자에게 먼저 커밋할지 물어보기
2. 현재 브랜치 이름 확인 (`git branch --show-current`)
3. `git push origin <현재브랜치>`
4. 완료 후 결과 요약 출력

## 주의사항
- `--force` 절대 사용 금지
- main, develop에는 push하지 않음
