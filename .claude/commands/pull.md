# Git Pull (develop + 내 브랜치)

develop의 최신 변경사항을 가져오고, 내 브랜치에도 반영한다.

## 실행 절차

1. `git config user.name`으로 사용자 확인
2. `git status`로 커밋 안 된 변경사항 확인
   - 커밋 안 된 변경사항이 있으면 사용자에게 먼저 커밋하거나 stash할지 물어보기
3. 현재 브랜치 이름 확인 (`git branch --show-current`)
4. **develop 최신화**:
   - `git checkout develop`
   - `git pull origin develop`
5. **내 브랜치로 복귀 + develop 머지**:
   - `git checkout <현재브랜치>`
   - `git pull origin <현재브랜치>` (리모트 변경사항 가져오기)
   - `git merge develop` (develop 내용을 내 브랜치에 반영)
   - 충돌 발생 시 사용자에게 알리고 해결 방법 안내
6. 완료 후 결과 요약 출력 (새로 받은 커밋 수, 변경된 파일 등)

## 주의사항
- 충돌 발생 시 자동 해결하지 말고 사용자에게 보고
- `--force` 절대 사용 금지
- stash 사용 시 작업 끝나면 `git stash pop` 안내
