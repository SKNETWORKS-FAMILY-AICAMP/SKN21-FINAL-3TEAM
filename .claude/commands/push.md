# Git Push (내 브랜치 + develop)

현재 브랜치의 변경사항을 origin에 push하고, develop에도 머지 후 push한다.

## 실행 절차

1. `git config user.name`으로 사용자 확인
2. `git status`로 커밋 안 된 변경사항 확인
   - 커밋 안 된 변경사항이 있으면 사용자에게 먼저 커밋할지 물어보기
3. 현재 브랜치 이름 확인 (`git branch --show-current`)
4. **내 브랜치 push**: `git push origin <현재브랜치>`
5. **develop 머지 + push**:
   - `git checkout develop`
   - `git pull origin develop` (최신 상태 맞추기)
   - `git merge <현재브랜치>` (충돌 시 사용자에게 알리고 중단)
   - `git push origin develop`
   - `git checkout <현재브랜치>` (원래 브랜치로 복귀)
6. 완료 후 결과 요약 출력

## 주의사항
- `--force` 절대 사용 금지
- 충돌 발생 시 자동 해결하지 말고 사용자에게 보고
- main에는 절대 push하지 않음
