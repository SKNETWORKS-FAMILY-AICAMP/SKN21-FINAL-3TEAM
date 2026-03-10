"""
문서 분석 파인튜닝 학습 데이터 Export

DB에 저장된 GPT 분석 결과(summary, category, tags)를
LoRA 학습용 JSONL 형식으로 추출한다.

출력 형식 (chat format):
  {"messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "문서 제목: ...\n문서 내용:\n..."},
    {"role": "assistant", "content": "{\"summary\": ..., \"category\": ..., \"tags\": [...]}"}
  ]}

사용법:
  cd /home/ubuntu/SKN21-FINAL-3TEAM
  export $(grep -v '^#' .env | xargs)
  source .venv/bin/activate
  python3 scripts/export_analysis_training_data.py

  # 데이터 증강 포함 (카테고리별 프롬프트 변형으로 3배 증강)
  python3 scripts/export_analysis_training_data.py --augment
"""

import asyncio
import argparse
import json
import os
import random
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))


SYSTEM_PROMPT = "당신은 문서 분석 전문가입니다. 주어진 문서를 분석하여 요약, 분류, 태그를 JSON으로 반환합니다.\n\n반드시 유효한 JSON만 출력하세요. 설명이나 마크다운 없이 JSON 객체만 반환합니다."

USER_PROMPT_TEMPLATE = """다음 문서를 분석해주세요.

문서 제목: {title}
문서 내용:
{content}

다음 JSON 형식으로 응답해주세요:
{{
  "summary": "2-3문장으로 문서의 핵심 내용을 요약",
  "category": "다음 중 하나 선택: 계약서, 회의록, 제안서, 정책문서, 인사문서, 보고서, 기타",
  "tags": ["관련 키워드 태그 3-5개, 예: 마케팅, 계약, 2025"]
}}"""

# 증강용 프롬프트 변형
AUGMENTED_PROMPTS = [
    "아래 문서를 분석하고 요약, 분류, 태그를 JSON으로 반환하세요.\n\n제목: {title}\n내용:\n{content}\n\nJSON 형식: {{\"summary\": \"...\", \"category\": \"계약서/회의록/제안서/정책문서/인사문서/보고서/기타\", \"tags\": [...]}}",
    "문서를 읽고 분석 결과를 JSON으로 출력하세요.\n\n[문서 제목] {title}\n[문서 본문]\n{content}\n\n출력 형식:\n{{\"summary\": \"핵심 내용 2-3문장\", \"category\": \"카테고리\", \"tags\": [\"키워드\"]}}",
]


async def get_documents():
    """DB에서 GPT 분석 완료된 문서 조회"""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL 환경변수가 설정되지 않았습니다.")
        return []

    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        from app.models.document import Document
        query = select(Document).where(
            Document.status == "completed",
            Document.content.isnot(None),
            Document.category.isnot(None),
        ).order_by(Document.created_at)
        result = await session.execute(query)
        docs = result.scalars().all()

    await engine.dispose()
    return docs


def make_training_example(title, content, summary, category, tags, prompt_template=None):
    """학습 데이터 1건 생성"""
    truncated = content[:3000]

    if prompt_template:
        user_content = prompt_template.format(title=title, content=truncated)
    else:
        user_content = USER_PROMPT_TEMPLATE.format(title=title, content=truncated)

    assistant_content = json.dumps({
        "summary": summary,
        "category": category,
        "tags": tags,
    }, ensure_ascii=False)

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ]
    }


async def main():
    parser = argparse.ArgumentParser(description="문서 분석 학습 데이터 Export")
    parser.add_argument("--augment", action="store_true", help="데이터 증강 (프롬프트 변형 3배)")
    parser.add_argument("--output", default=None, help="출력 파일 경로")
    args = parser.parse_args()

    print("DB에서 문서 로드 중...")
    docs = await get_documents()

    if not docs:
        print("분석 완료된 문서가 없습니다.")
        return

    print(f"총 {len(docs)}개 문서 로드 완료")

    # 카테고리 분포 확인
    cat_count = {}
    for doc in docs:
        cat = doc.category or "기타"
        cat_count[cat] = cat_count.get(cat, 0) + 1
    print(f"\n카테고리 분포:")
    for cat, cnt in sorted(cat_count.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {cnt}개")

    # 학습 데이터 생성
    training_data = []
    for doc in docs:
        content = doc.content or ""
        title = doc.title or ""
        summary = doc.summary or ""
        category = doc.category or "기타"
        tags = doc.tags or []

        if not content.strip():
            continue

        # 원본 프롬프트
        example = make_training_example(title, content, summary, category, tags)
        training_data.append(example)

        # 증강: 프롬프트 변형
        if args.augment:
            for aug_prompt in AUGMENTED_PROMPTS:
                aug_example = make_training_example(
                    title, content, summary, category, tags,
                    prompt_template=aug_prompt
                )
                training_data.append(aug_example)

    # 셔플
    random.shuffle(training_data)

    # train/val 분리 (90/10)
    split_idx = max(1, int(len(training_data) * 0.9))
    train_data = training_data[:split_idx]
    val_data = training_data[split_idx:]

    # 저장
    output_dir = os.path.join(PROJECT_ROOT, "ai", "finetuning", "data")
    os.makedirs(output_dir, exist_ok=True)

    train_path = os.path.join(output_dir, "doc_analysis_train.jsonl")
    val_path = os.path.join(output_dir, "doc_analysis_val.jsonl")

    with open(train_path, "w", encoding="utf-8") as f:
        for item in train_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(val_path, "w", encoding="utf-8") as f:
        for item in val_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\n학습 데이터 생성 완료:")
    print(f"  Train: {train_path} ({len(train_data)}건)")
    print(f"  Val:   {val_path} ({len(val_data)}건)")
    print(f"  총:    {len(training_data)}건" + (" (증강 포함)" if args.augment else ""))

    # 샘플 출력
    print(f"\n--- 샘플 (1건) ---")
    sample = training_data[0]
    print(f"System: {sample['messages'][0]['content'][:80]}...")
    print(f"User: {sample['messages'][1]['content'][:100]}...")
    print(f"Assistant: {sample['messages'][2]['content']}")


if __name__ == "__main__":
    asyncio.run(main())
