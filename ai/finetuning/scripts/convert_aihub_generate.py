"""
AI Hub 데이터 → v2_generate 학습 데이터 변환 스크립트 (반자동 파이프라인)

소스: AI Hub "요약문 및 레포트 생성 데이터" (SN 582)
타겟: data/training/v2_generate/aihub_generate.jsonl (460개)

AI Hub 데이터 구조 (파일 1건 = JSON 1건):
  {
    "Meta(Acqusition)": {"doc_type": "minute", ...},
    "Meta(Refine)": {"passage": "원문 텍스트"},
    "Annotation": {"summary1": "...", "summary2": "...", "summary3": "..."}
  }

배분:
  - meeting_minutes: 40개 (회의록 카테고리 → GPT-4o로 JSON 생성)
  - report: 210개 (보고서 + 간행물 → GPT-4o로 JSON 생성)
  - proposal: 210개 (보도자료 + 간행물 중 사업/정책 → GPT-4o로 JSON 생성)

변환 전략 (반자동):
  1. AI Hub passage → user input 으로 사용
  2. GPT-4o에게 프로덕션 system prompt + user prompt 그대로 전달
  3. GPT-4o가 JSON output 생성
  4. 필수 키 자동 검증 후 저장

사용법:
    # dry-run (API 호출 없이 데이터 선별만 확인)
    python ai/finetuning/scripts/convert_aihub_generate.py --dry-run

    # 기본 실행 (GPT-4o API 필요)
    python ai/finetuning/scripts/convert_aihub_generate.py

    # 템플릿별 실행
    python ai/finetuning/scripts/convert_aihub_generate.py --template report
    python ai/finetuning/scripts/convert_aihub_generate.py --template proposal

    # 건수 조정 + API 모델 변경
    python ai/finetuning/scripts/convert_aihub_generate.py --total 100 --model gpt-4o-mini

    # 이어서 실행 (기존 파일에 append)
    python ai/finetuning/scripts/convert_aihub_generate.py --template report --append
"""

import argparse
import json
import io
import os
import random
import re
import sys
import time
from pathlib import Path

# Windows 콘솔 한글 출력
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# AI Hub 데이터 경로 (실제 구조에 맞춤)
RAW_BASE = BASE_DIR / "data" / "raw" / "aihub" / "022.요약문 및 레포트 생성 데이터" / "01.데이터"
TRAIN_LABEL_DIR = RAW_BASE / "1.Training" / "라벨링데이터" / "TL1"
OUTPUT_DIR = BASE_DIR / "data" / "training" / "v2_generate"

# ── 프로덕션 시스템 프롬프트 (document_agent.py와 100% 일치) ──

SYSTEM_PROMPTS = {
    "meeting_minutes": (
        "당신은 회의록 작성 전문가입니다.\n"
        "아래 [작성 지침]을 참고하여 입력된 회의 내용을 바탕으로 실제 회의록을 생성하세요.\n\n"
        "[작성 지침]\n"
        "- title: 회의 주제를 반영한 구체적인 제목\n"
        "- date: 회의 날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)\n"
        "- attendees: 참석자 이름 배열 (없으면 빈 배열)\n"
        "- summary: 회의에서 논의된 주요 내용을 파트별로 3~5문장으로 요약 "
        "(한 줄 요약 금지, 반드시 실제 내용으로 작성)\n"
        "- decisions: 결정된 사항 목록 (배열, 없으면 빈 배열)\n"
        "- action_items: 후속 조치 목록. 각 항목은 {content, assignee, due_date} 형태\n"
        "- risks: 리스크 목록. 각 항목은 {description, level(상/중/하), regulation} 형태\n\n"
        "반드시 JSON만 출력하세요. 설명 텍스트나 지침 문장을 값으로 출력하지 마세요."
    ),
    "report": (
        "당신은 업무보고서 작성 전문가입니다.\n"
        "아래 [작성 지침]을 참고하여 사용자의 업무 내용을 바탕으로 실제 보고서 내용을 생성하세요.\n\n"
        "[작성 지침]\n"
        "- title: 업무 내용을 반영한 구체적인 보고서 제목\n"
        "- author: 작성자 이름 (없으면 빈 문자열)\n"
        "- date: 오늘 날짜 (YYYY-MM-DD 형식)\n"
        "- department: 부서명 (없으면 빈 문자열)\n"
        "- position: 직급 (없으면 빈 문자열)\n"
        "- report_to: 보고 대상 (없으면 빈 문자열)\n"
        "- report_type: '일일', '주간', '월간', '수시' 중 하나\n"
        "- overview: 업무 내용을 요약한 보고 개요 (3~5문장, 반드시 실제 내용으로 작성)\n"
        "- main_content: 업무 세부 내용을 항목별로 구체적으로 작성\n"
        "- tasks: 진행 중인 업무 목록. 반드시 JSON 배열 형태이며 각 항목은 다음 키를 포함해야 함:\n"
        '  { "item": "업무항목명", "assignee": "담당자", "progress": "진행률(예:70%)", '
        '"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD" }\n'
        "  (담당자/날짜 정보가 없으면 빈 문자열로 채울 것)\n"
        "- issues: 이슈 및 건의사항 (없으면 빈 문자열)\n"
        "- next_plan: 향후 계획 (구체적으로 작성)\n\n"
        "반드시 JSON만 출력하세요. 설명 텍스트나 지침 문장을 값으로 출력하지 마세요."
    ),
    "proposal": (
        "당신은 제안서 작성 전문가입니다.\n"
        "아래 [작성 지침]을 참고하여 사용자의 제안 내용을 바탕으로 실제 제안서 내용을 생성하세요.\n\n"
        "[작성 지침]\n"
        "- title: 제안 내용을 반영한 구체적인 제안서 제목\n"
        "- submit_date: 제출 날짜 (YYYY-MM-DD, 없으면 오늘 날짜)\n"
        "- submit_to: 제출처 (없으면 빈 문자열)\n"
        "- company: 제안사 이름 (없으면 빈 문자열)\n"
        "- manager: 담당자 이름 (없으면 빈 문자열)\n"
        "- contact: 연락처 (없으면 빈 문자열)\n"
        "- proposal_name: 제안명 (title과 유사하게)\n"
        "- background: 제안 배경을 2~3문장으로 실제 내용으로 작성\n"
        "- proposal_date: 제안 날짜 (YYYY-MM-DD)\n"
        "- period: 제안 기간 (예: 2026년 3월 ~ 6월)\n"
        "- proposer: 제안사명\n"
        "- manager_contact: 담당자 / 연락처\n"
        "- purpose: 제안 목적 및 필요성을 3~5문장으로 실제 내용으로 작성\n"
        "- analysis: 현황 분석을 3~5문장으로 실제 내용으로 작성\n"
        "- content: 제안 내용을 항목별로 구체적으로 작성\n"
        "- schedule: 추진 일정 배열. 각 항목은 {item, phase1, phase2, phase3, phase4} 형태\n"
        "- budget: 예산 배열. 각 항목은 {item, quantity, unit_price, amount} 형태\n"
        "- budget_total: 합계 금액\n"
        "- expected_effect: 기대 효과를 3~5문장으로 실제 내용으로 작성\n\n"
        "반드시 JSON만 출력하세요. 설명 텍스트나 지침 문장을 값으로 출력하지 마세요."
    ),
}

USER_PROMPT_TEMPLATES = {
    "meeting_minutes": (
        "다음 회의 내용을 바탕으로 회의록 JSON을 작성해주세요.\n\n"
        "[회의 내용]\n{passage}\n\n"
        "출력 JSON 키: title, date, attendees, summary, decisions, action_items, risks"
    ),
    "report": (
        "다음 업무 내용을 바탕으로 업무보고서 JSON을 작성해주세요.\n\n"
        "[업무 내용]\n{passage}\n\n"
        "출력 JSON 키: title, author, date, department, position, report_to, report_type, "
        "overview, main_content, tasks, issues, next_plan"
    ),
    "proposal": (
        "다음 제안 내용을 바탕으로 제안서 JSON을 작성해주세요.\n\n"
        "[제안 내용]\n{passage}\n\n"
        "출력 JSON 키: title, submit_date, submit_to, company, manager, contact, proposal_name, "
        "background, proposal_date, period, proposer, manager_contact, purpose, analysis, "
        "content, schedule, budget, budget_total, expected_effect"
    ),
}

# 필수 필드 (검증용)
REQUIRED_FIELDS = {
    "meeting_minutes": ["title", "date", "attendees", "summary", "decisions", "action_items"],
    "report": ["title", "author", "date", "department", "report_type", "overview", "main_content", "tasks"],
    "proposal": [
        "title", "submit_date", "submit_to", "company", "manager",
        "proposal_name", "background", "purpose", "content", "schedule", "budget",
    ],
}

# ── 카테고리 매핑 (폴더명 → 한글) ──

FOLDER_TO_CATEGORY = {
    "01.news_r": "뉴스",
    "02.briefing": "보도자료",
    "03.his_cul": "역사기록물",
    "04.paper": "보고서",
    "05.minute": "회의록",
    "06.edit": "사설",
    "07.public": "간행물",
    "08.speech": "연설문",
    "09.literature": "문학",
    "10.narration": "나레이션",
}

# ── 템플릿별 카테고리 → 목표 수 ──
# meeting_minutes: 40 (회의록 = 국회 속기록, GPT-4o 변환)
# report: 210 (보고서 105 + 간행물 105)
# proposal: 210 (보도자료 105 + 간행물(사업/정책) 105)

TEMPLATE_TARGETS = {
    "meeting_minutes": {"회의록": 40},
    "report": {"보고서": 105, "간행물": 105},
    "proposal": {"보도자료": 105, "간행물": 105},
}

# 원문 길이 필터 (v2_generate: 더 긴 원문 필요)
MIN_PASSAGE_LEN = 500
MAX_PASSAGE_LEN = 3000


def load_aihub_data(label_dir: Path, categories: list[str], limit_per_cat: int = 0) -> list[dict]:
    """AI Hub 중첩 JSON 파일을 카테고리별 필요 수만큼만 로드.

    전체 14만 건을 로드하면 너무 느리므로, 필요한 카테고리만 limit_per_cat만큼 로드.
    """
    all_docs = []

    if not label_dir.exists():
        print(f"[오류] 데이터 디렉토리 없음: {label_dir}")
        print(f"       AI Hub에서 데이터를 다운로드하세요:")
        print(f"       https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=582")
        sys.exit(1)

    # 필요한 카테고리의 폴더명 찾기
    cat_to_folder = {v: k for k, v in FOLDER_TO_CATEGORY.items()}
    needed_folders = {}
    for cat in categories:
        folder = cat_to_folder.get(cat)
        if folder:
            needed_folders[folder] = cat

    for cat_folder in sorted(label_dir.iterdir()):
        if not cat_folder.is_dir():
            continue
        if cat_folder.name not in needed_folders:
            continue

        category = needed_folders[cat_folder.name]
        limit = limit_per_cat if limit_per_cat > 0 else 500

        cat_docs = []
        for sub_folder in sorted(cat_folder.iterdir()):
            if not sub_folder.is_dir():
                continue

            json_files = list(sub_folder.glob("*.json"))
            random.shuffle(json_files)

            for fp in json_files:
                if len(cat_docs) >= limit:
                    break
                try:
                    with open(fp, encoding="utf-8") as f:
                        raw = json.load(f)

                    meta_refine = raw.get("Meta(Refine)", {})
                    passage = meta_refine.get("passage", "")
                    if not passage or not isinstance(passage, str):
                        continue

                    doc = {
                        "passage": passage,
                        "category": category,
                    }
                    cat_docs.append(doc)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

            if len(cat_docs) >= limit:
                break

        all_docs.extend(cat_docs)
        print(f"  {cat_folder.name} ({category}): {len(cat_docs):,}건 로드")

    print(f"  총 로드: {len(all_docs):,}건")
    return all_docs


def filter_and_select(
    docs: list[dict],
    template: str,
    targets: dict[str, int],
    min_len: int = MIN_PASSAGE_LEN,
    max_len: int = MAX_PASSAGE_LEN,
    seed: int = 42,
) -> list[dict]:
    """카테고리별로 원문 길이 필터링 후 목표 수만큼 선별"""
    by_category = {}
    for doc in docs:
        cat = doc["category"]
        if cat not in targets:
            continue
        passage = doc["passage"]
        if not (min_len <= len(passage) <= max_len):
            continue
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(doc)

    # 현황 출력
    print(f"\n  [{template}] 필터링 후 현황 ({min_len}~{max_len}자):")
    total_target = 0
    for cat, target in targets.items():
        count = len(by_category.get(cat, []))
        status = "OK" if count >= target else "부족"
        print(f"    {cat}: {count:,}건 사용 가능 (목표: {target}, {status})")
        total_target += target

    # 카테고리별 목표 수만큼 랜덤 선별
    random.seed(seed)
    selected = []
    for cat, target in targets.items():
        pool = by_category.get(cat, [])
        if not pool:
            print(f"    [경고] {cat}: 데이터 없음")
            continue
        if len(pool) < target:
            print(f"    [경고] {cat}: {len(pool)}건만 사용 (목표 {target})")
            selected.extend(pool)
        else:
            selected.extend(random.sample(pool, target))

    random.shuffle(selected)
    print(f"  총 선별: {len(selected)}건 (목표: {total_target})")
    return selected


def call_gpt4o(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4o",
    max_retries: int = 3,
) -> str | None:
    """GPT-4o API 호출하여 JSON 생성"""
    try:
        from openai import OpenAI
    except ImportError:
        print("[오류] openai 패키지가 필요합니다: pip install openai")
        sys.exit(1)

    client = OpenAI()

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"    [API 에러 (시도 {attempt+1}/{max_retries})] {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return None


def validate_json_output(json_str: str, template: str) -> tuple[bool, dict | None, list[str]]:
    """생성된 JSON 출력을 검증"""
    errors = []

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return False, None, [f"JSON 파싱 실패: {e}"]

    if not isinstance(data, dict):
        return False, None, ["최상위가 dict가 아님"]

    # 한국어 키 체크
    korean_keys = [k for k in data.keys() if re.search(r"[\uac00-\ud7a3]", k)]
    if korean_keys:
        errors.append(f"한국어 키 발견: {korean_keys}")

    # 필수 필드 체크
    required = REQUIRED_FIELDS.get(template, [])
    missing = [f for f in required if f not in data]
    if missing:
        errors.append(f"필수 필드 누락: {missing}")

    is_valid = len(errors) == 0
    return is_valid, data, errors


def convert_template(
    selected: list[dict],
    template: str,
    output_path: Path,
    model: str = "gpt-4o",
    append: bool = False,
):
    """특정 템플릿에 대한 변환을 수행 (GPT-4o 호출)"""
    sys_prompt = SYSTEM_PROMPTS[template]
    user_template = USER_PROMPT_TEMPLATES[template]

    mode = "a" if append else "w"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0

    with open(output_path, mode, encoding="utf-8") as f:
        for i, doc in enumerate(selected):
            passage = doc["passage"]
            user_prompt = user_template.format(passage=passage)

            print(f"    [{i+1}/{len(selected)}] GPT-4o 호출 중...", end=" ", flush=True)

            # GPT-4o 호출
            json_output = call_gpt4o(sys_prompt, user_prompt, model=model)
            if not json_output:
                print("실패 (API)")
                failed += 1
                continue

            # 검증
            is_valid, parsed, errors = validate_json_output(json_output, template)
            if not is_valid:
                print(f"실패 (검증: {errors})")
                failed += 1
                continue

            # 학습 데이터 형식으로 저장
            sample = {
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": json_output},
                ]
            }

            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            success += 1
            print(f"OK (키: {len(parsed)}개)")

            # Rate limiting
            if (i + 1) % 10 == 0:
                time.sleep(1)
                print(f"    --- {i+1}건 완료 (성공: {success}, 실패: {failed}) ---")

    print(f"\n  [{template}] 결과: 성공 {success}, 실패 {failed}")
    return success


def main():
    parser = argparse.ArgumentParser(description="AI Hub → v2_generate 변환 (반자동)")
    parser.add_argument("--input", type=str, default=str(TRAIN_LABEL_DIR), help="AI Hub TL1 디렉토리")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR / "aihub_generate.jsonl"), help="출력 파일")
    parser.add_argument("--template", type=str, choices=["meeting_minutes", "report", "proposal", "all"], default="all")
    parser.add_argument("--total", type=int, default=460, help="총 변환 목표 건수")
    parser.add_argument("--model", type=str, default="gpt-4o", help="사용할 OpenAI 모델")
    parser.add_argument("--append", action="store_true", help="기존 파일에 추가")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    parser.add_argument("--skip", type=int, default=0, help="각 템플릿별 앞쪽 N건 스킵 (이어하기용)")
    parser.add_argument("--min-len", type=int, default=MIN_PASSAGE_LEN, help="최소 원문 길이")
    parser.add_argument("--max-len", type=int, default=MAX_PASSAGE_LEN, help="최대 원문 길이")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 데이터 선별만 수행")
    args = parser.parse_args()

    # API 키 확인
    if not args.dry_run and not os.getenv("OPENAI_API_KEY"):
        print("[오류] OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    print("=" * 70)
    print("  AI Hub → v2_generate 변환 (반자동 파이프라인)")
    print("=" * 70)
    print(f"  입력: {args.input}")
    print(f"  출력: {args.output}")
    print(f"  모델: {args.model}")
    print(f"  목표: {args.total}건 (meeting_minutes 40 + report 210 + proposal 210)")
    print(f"  DRY RUN: {'ON' if args.dry_run else 'OFF'}")

    # 비율에 따른 할당
    ratio = args.total / 460
    template_targets_scaled = {
        "meeting_minutes": {"회의록": max(1, int(40 * ratio))},
        "report": {"보고서": max(1, int(105 * ratio)), "간행물": max(1, int(105 * ratio))},
        "proposal": {"보도자료": max(1, int(105 * ratio)), "간행물": max(1, int(105 * ratio))},
    }

    templates_to_run = (
        [args.template] if args.template != "all"
        else ["meeting_minutes", "report", "proposal"]
    )

    # 필요한 카테고리 목록 수집
    needed_categories = set()
    for tmpl in templates_to_run:
        needed_categories.update(template_targets_scaled[tmpl].keys())

    # 1. 데이터 로드 (필요한 카테고리만)
    print(f"\n[1/3] 데이터 로드 (카테고리: {', '.join(needed_categories)})")
    data_dir = Path(args.input)
    docs = load_aihub_data(data_dir, list(needed_categories), limit_per_cat=500)

    if not docs:
        print("[오류] 로드된 데이터가 없습니다.")
        sys.exit(1)

    # 2. 템플릿별 데이터 선별 (간행물 중복 방지)
    print(f"\n[2/3] 데이터 선별")
    template_selected = {}
    used_passages = set()  # 중복 방지용

    for tmpl in templates_to_run:
        targets = template_targets_scaled[tmpl]
        # 템플릿마다 다른 시드로 선별 (중복 방지)
        tmpl_seed = args.seed + hash(tmpl) % 1000
        selected = filter_and_select(docs, tmpl, targets, args.min_len, args.max_len, tmpl_seed)

        # 이전 템플릿에서 사용한 passage와 중복 제거
        deduped = []
        for doc in selected:
            passage_hash = hash(doc["passage"][:200])
            if passage_hash not in used_passages:
                deduped.append(doc)
                used_passages.add(passage_hash)
        if len(deduped) < len(selected):
            print(f"    [{tmpl}] 중복 제거: {len(selected)} -> {len(deduped)}건")
        template_selected[tmpl] = deduped

    if args.dry_run:
        print(f"\n[DRY RUN] API 호출 없이 데이터 선별 현황만 확인합니다.")
        for tmpl, selected in template_selected.items():
            print(f"  {tmpl}: {len(selected)}건 선별됨")
            if selected:
                sample = selected[0]
                print(f"    샘플 원문 ({len(sample['passage'])}자): {sample['passage'][:100]}...")
        total = sum(len(s) for s in template_selected.values())
        print(f"\n  총 선별: {total}건")
        print(f"  예상 API 비용: ~${total * 0.04:.1f} (GPT-4o 기준)")
        return

    # 3. 변환 시작 (GPT-4o 호출)
    print(f"\n[3/3] 변환 시작 (GPT-4o API 호출)")
    output_path = Path(args.output)
    total_success = 0

    for i, tmpl in enumerate(templates_to_run):
        selected = template_selected[tmpl]
        if not selected:
            continue
        # --skip 적용: 이어하기 시 이미 완료된 건 스킵
        if args.skip > 0 and i == 0:
            selected = selected[args.skip:]
            print(f"\n  === {tmpl} ({len(selected)}건, skip {args.skip}) ===")
        else:
            print(f"\n  === {tmpl} ({len(selected)}건) ===")
        is_append = args.append or (i > 0)
        success = convert_template(selected, tmpl, output_path, model=args.model, append=is_append)
        total_success += success

    # 4. 결과 요약
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        print(f"\n  [결과 요약]")
        print(f"  총 데이터: {len(lines)}건")

        template_dist = {"meeting_minutes": 0, "report": 0, "proposal": 0}
        json_valid = 0
        for line in lines:
            sample = json.loads(line)
            sys_content = sample["messages"][0]["content"]
            assistant_content = sample["messages"][2]["content"]

            if "회의록" in sys_content:
                template_dist["meeting_minutes"] += 1
            elif "제안서" in sys_content:
                template_dist["proposal"] += 1
            else:
                template_dist["report"] += 1

            try:
                json.loads(assistant_content)
                json_valid += 1
            except json.JSONDecodeError:
                pass

        pct = json_valid / len(lines) * 100 if lines else 0
        print(f"  템플릿 분포: {template_dist}")
        print(f"  JSON 유효율: {json_valid}/{len(lines)} ({pct:.1f}%)")

    print(f"\n  완료!")


if __name__ == "__main__":
    main()
