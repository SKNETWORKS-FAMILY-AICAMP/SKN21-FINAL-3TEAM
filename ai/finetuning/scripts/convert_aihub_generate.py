"""
AI Hub 데이터 → v2_generate 학습 데이터 변환 스크립트 (반자동 파이프라인)

소스: AI Hub "요약문 및 레포트 생성 데이터" (SN 582)
타겟: data/training/v2_generate/aihub_generate.jsonl (690개)

AI Hub 데이터 구조 (파일 1건 = JSON 1건):
  {
    "Meta(Acqusition)": {"doc_type": "minute", ...},
    "Meta(Refine)": {"passage": "원문 텍스트"},
    "Annotation": {"summary1": "...", "summary2": "...", "summary3": "..."}
  }

배분:
  - meeting_minutes: 60개 (회의록 카테고리 → GPT-4o로 JSON 생성)
  - report: 315개 (보고서 + 간행물 → GPT-4o로 JSON 생성)
  - proposal: 315개 (보도자료 → GPT-4o로 JSON 생성)

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
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env", override=True)

from ai.llm.prompts import DOC_GENERATE_SLLM_PROMPT

# AI Hub 데이터 경로 (실제 구조에 맞춤)
RAW_BASE = BASE_DIR / "data" / "raw" / "ai_hub" / "022.요약문 및 레포트 생성 데이터" / "01.데이터"
TRAIN_LABEL_DIR = RAW_BASE / "1.Training" / "라벨링데이터" / "TL1"
OUTPUT_DIR = BASE_DIR / "data" / "training" / "v2_generate"

# ── sLLM 시스템 프롬프트 (ai/llm/prompts.py에서 import — synthesize_generate.py와 동일) ──
DYNAMIC_SYSTEM_PROMPT = DOC_GENERATE_SLLM_PROMPT

# ── 템플릿별 필드 명세 (synthesize_generate.py FIELD_SPECS와 100% 동일) ──

FIELD_SPECS = {
    "meeting_minutes": {
        "doc_type_name": "회의록",
        "input_label": "회의 내용",
        "fields": [
            ("title", "회의 주제를 반영한 구체적인 제목"),
            ("date", "회의 날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)"),
            ("attendees", "참석자 이름 배열 (없으면 빈 배열)"),
            ("summary", "회의에서 논의된 주요 내용을 파트별로 3~5문장으로 요약"),
            ("decisions", "결정된 사항 목록 (배열, 없으면 빈 배열)"),
            ("action_items", '후속 조치 목록 배열. 각 항목은 {"content", "assignee", "due_date"} 형태'),
            ("risks", '리스크 목록 배열. 각 항목은 {"description", "level"(상/중/하), "regulation"} 형태'),
        ],
    },
    "report": {
        "doc_type_name": "업무보고서",
        "input_label": "업무 내용",
        "fields": [
            ("title", "업무 내용을 반영한 구체적인 보고서 제목"),
            ("author", "작성자 이름 (없으면 빈 문자열)"),
            ("date", "작성 날짜 (YYYY-MM-DD 형식)"),
            ("department", "부서명 (없으면 빈 문자열)"),
            ("position", "직급 (없으면 빈 문자열)"),
            ("report_to", "보고 대상 (없으면 빈 문자열)"),
            ("report_type", "'일일', '주간', '월간', '수시' 중 하나"),
            ("overview", "업무 내용을 요약한 보고 개요 (3~5문장)"),
            ("main_content", "업무 세부 내용을 항목별로 구체적으로 작성"),
            ("tasks", '진행 업무 목록 배열. 각 항목은 {"item", "assignee", "progress", "start_date", "end_date"} 형태'),
            ("issues", "이슈 및 건의사항 (없으면 빈 문자열)"),
            ("next_plan", "향후 계획 (구체적으로 작성)"),
        ],
    },
    "proposal": {
        "doc_type_name": "제안서",
        "input_label": "제안 내용",
        "fields": [
            ("title", "제안 내용을 반영한 구체적인 제안서 제목"),
            ("submit_date", "제출 날짜 (YYYY-MM-DD, 없으면 오늘 날짜)"),
            ("submit_to", "제출처 (없으면 빈 문자열)"),
            ("company", "제안사 이름 (없으면 빈 문자열)"),
            ("manager", "담당자 이름 (없으면 빈 문자열)"),
            ("contact", "연락처 (없으면 빈 문자열)"),
            ("proposal_name", "제안명 (title과 유사하게)"),
            ("background", "제안 배경 (2~3문장)"),
            ("proposal_date", "제안 날짜 (YYYY-MM-DD)"),
            ("period", "제안 기간 (예: 2026년 3월 ~ 6월)"),
            ("proposer", "제안사명"),
            ("manager_contact", "담당자 / 연락처"),
            ("purpose", "제안 목적 및 필요성 (3~5문장)"),
            ("analysis", "현황 분석 (3~5문장)"),
            ("content", "제안 내용을 항목별로 구체적으로 작성"),
            ("schedule", '추진 일정 배열. 각 항목은 {"item", "phase1", "phase2", "phase3", "phase4"} 형태'),
            ("budget", '예산 배열. 각 항목은 {"item", "quantity", "unit_price", "amount"} 형태'),
            ("budget_total", "합계 금액"),
            ("expected_effect", "기대 효과 (3~5문장)"),
        ],
    },
}


def build_dynamic_user_prompt(template: str, passage: str) -> str:
    """동적 필드 명세 방식의 user prompt 생성 (synthesize_generate.py와 동일)"""
    spec = FIELD_SPECS[template]
    doc_type = spec["doc_type_name"]
    input_label = spec["input_label"]

    field_lines = []
    for field_name, field_desc in spec["fields"]:
        field_lines.append(f"- {field_name}: {field_desc}")
    field_spec_str = "\n".join(field_lines)

    return (
        f"다음 내용을 바탕으로 문서를 JSON 형식으로 작성해주세요.\n\n"
        f"[문서 유형] {doc_type}\n\n"
        f"[필드 명세]\n{field_spec_str}\n\n"
        f"[{input_label}]\n{passage}"
    )

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
# meeting_minutes: 60 (회의록 = 국회 속기록, GPT-4o 변환)
# report: 315 (보고서 158 + 간행물 157)
# proposal: 315 (보도자료)

TEMPLATE_TARGETS = {
    "meeting_minutes": {"회의록": 60},
    "report": {"보고서": 158, "간행물": 157},
    "proposal": {"보도자료": 315},
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
        seen_passages = set()
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

                    # 같은 passage가 20per/2~3sent 폴더에 중복 존재 → 로딩 시 제거
                    p_hash = hash(passage)
                    if p_hash in seen_passages:
                        continue
                    seen_passages.add(p_hash)

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
    sys_prompt = DYNAMIC_SYSTEM_PROMPT

    mode = "a" if append else "w"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0

    with open(output_path, mode, encoding="utf-8") as f:
        for i, doc in enumerate(selected):
            passage = doc["passage"]
            user_prompt = build_dynamic_user_prompt(template, passage)

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
    parser.add_argument("--total", type=int, default=690, help="총 변환 목표 건수")
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
    print(f"  목표: {args.total}건 (meeting_minutes 60 + report 315 + proposal 315)")
    print(f"  DRY RUN: {'ON' if args.dry_run else 'OFF'}")

    # 비율에 따른 할당 (TEMPLATE_TARGETS 기반)
    base_total = sum(sum(cats.values()) for cats in TEMPLATE_TARGETS.values())
    ratio = args.total / base_total
    template_targets_scaled = {}
    for tmpl, cats in TEMPLATE_TARGETS.items():
        template_targets_scaled[tmpl] = {
            cat: max(1, int(count * ratio)) for cat, count in cats.items()
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
    docs = load_aihub_data(data_dir, list(needed_categories), limit_per_cat=2000)

    if not docs:
        print("[오류] 로드된 데이터가 없습니다.")
        sys.exit(1)

    # 2. 템플릿별 데이터 선별 (간행물 중복 방지)
    print(f"\n[2/3] 데이터 선별")
    template_selected = {}
    used_passages = set()  # 중복 방지용

    for tmpl in templates_to_run:
        targets = template_targets_scaled[tmpl]

        # 이미 사용된 passage를 풀에서 제거한 docs 생성
        available_docs = [d for d in docs if hash(d["passage"]) not in used_passages]

        selected = filter_and_select(available_docs, tmpl, targets, args.min_len, args.max_len, args.seed)

        # 선택된 passage를 used_passages에 등록
        for doc in selected:
            used_passages.add(hash(doc["passage"]))

        template_selected[tmpl] = selected

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
