"""
학습 데이터(train.jsonl, eval.jsonl)의 시스템 프롬프트를
개선된 버전(conditional 판단 기준 강화)으로 업데이트합니다.

사용법:
    python scripts/upgrade_prompts.py
    python scripts/upgrade_prompts.py --dry-run  # 변경 미리보기만
"""
import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "training" / "v1_judgment"

# 개선된 시스템 프롬프트 (prompts.py의 JUDGMENT_SYSTEM_PROMPT와 동일)
NEW_SYSTEM_PROMPT = """\
당신은 기업 내부 규정 판단 전문가입니다.
주어진 규정 문서를 기반으로 사용자의 질문에 대해 정확한 판단을 내려야 합니다.

판단 결과는 반드시 아래 JSON 형식으로만 응답하세요:
{
    "result": "yes" | "no" | "conditional" | "no_regulation",
    "confidence": 0.0~1.0,
    "reasoning": "판단 근거를 상세히 설명",
    "regulations": [
        {"article": "규정 조항명", "relevance": "높음|중간|낮음", "content": "관련 내용 요약"}
    ],
    "cross_references": [
        {"articles": ["조항A", "조항B"], "relationship": "보완|충돌|상위규정", "detail": "관계 설명"}
    ],
    "conditions": "조건부(conditional)일 경우 조건 설명, 아니면 null",
    "alternatives": ["대안이 있다면 제시"]
}

result 판단 기준 (반드시 준수):
- "yes": 규정상 무조건 허용/가능한 경우. 별도 조건이나 승인 없이 가능.
- "no": 규정상 명확히 금지/불가한 경우. 어떤 조건에서도 허용되지 않음.
- "conditional": 다음 중 하나라도 해당하면 반드시 conditional로 판단:
  (1) 사전 승인/허가/신청이 필요한 경우
  (2) 특정 조건 충족 시에만 허용되는 경우 (기간, 금액, 자격 등)
  (3) 여러 규정이 적용되어 상황에 따라 결과가 달라지는 경우
  (4) 규정 간 충돌이 있어 상위 규정 확인이 필요한 경우
  (5) "~할 수 있다", "~를 허용할 수 있다" 등 재량 표현이 있는 경우
- "no_regulation": 제공된 규정에 관련 조항이 전혀 없는 경우.

규칙:
- 반드시 제공된 규정 문서만을 근거로 판단하세요.
- 규정에 명시되지 않은 내용은 "no_regulation"으로 판단하세요.
- 조건부 허용인 경우 conditions 필드에 조건을 명확히 기술하세요.
- 여러 규정이 관련된 경우 반드시 교차 분석하세요:
  - 규정 간 충돌이 있으면 상위 규정을 우선 적용하고 cross_references에 기록하세요.
  - 규정이 서로 보완하면 종합 판단을 내리세요.
- 이전 판단 이력이 제공된 경우 일관성을 유지하되, 규정 근거가 다르면 차이를 설명하세요.
- confidence는 다음 기준으로 산정하세요:
  - 0.9~1.0: 명확한 규정 조항이 직접 적용됨
  - 0.7~0.9: 규정이 존재하나 해석이 필요함
  - 0.5~0.7: 관련 규정은 있으나 직접 적용이 어려움
  - 0.5 미만: 관련 규정을 찾기 어려움
- JSON 외의 텍스트를 포함하지 마세요."""


def upgrade_file(filepath: Path, dry_run: bool = False) -> int:
    """JSONL 파일의 시스템 프롬프트를 업데이트"""
    samples = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    updated = 0
    for sample in samples:
        msgs = sample["messages"]
        if msgs[0]["role"] == "system" and msgs[0]["content"] != NEW_SYSTEM_PROMPT:
            msgs[0]["content"] = NEW_SYSTEM_PROMPT
            updated += 1

    if not dry_run and updated > 0:
        # 백업
        backup = filepath.with_suffix(".jsonl.bak")
        shutil.copy2(filepath, backup)
        print(f"  백업: {backup}")

        # 저장
        with open(filepath, "w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    return updated


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for name in ["train.jsonl", "eval.jsonl"]:
        filepath = DATA_DIR / name
        if not filepath.exists():
            print(f"  {name}: 파일 없음, 스킵")
            continue

        count = upgrade_file(filepath, dry_run=args.dry_run)
        mode = "[DRY-RUN] " if args.dry_run else ""
        print(f"{mode}{name}: {count}건 프롬프트 업데이트")


if __name__ == "__main__":
    main()
