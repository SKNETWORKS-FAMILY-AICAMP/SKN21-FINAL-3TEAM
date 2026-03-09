"""
AI Hub 데이터 -> v2_generate 학습 데이터 변환 스크립트 (필드 풀 랜덤 조합 방식)

소스: AI Hub "요약문 및 레포트 생성 데이터" (SN 582)
타겟: data/training/v2_generate/aihub_generate.jsonl (700개)

배분:
  - meeting_minutes: 100개 (회의록 카테고리)
  - report: 300개 (보고서 + 간행물)
  - proposal: 300개 (보도자료)

필드 풀 방식:
  각 문서유형별 필드를 필수/메타/내용 3계층으로 분류.
  매 샘플마다: 필수 전부 + 내용 풀 2~4개 + 메타 풀 1~3개 = 총 6~10개 필드.
  synthesize_generate.py와 동일한 FIELD_POOLS 사용.

변환 전략 (반자동):
  1. AI Hub passage -> user input 으로 사용
  2. 필드 풀에서 랜덤 필드 조합 선택
  3. GPT-4o에게 선택된 필드 명세 + passage 전달 -> JSON 생성
  4. 선택된 필드 기준 자동 검증 후 저장

사용법:
    python ai/finetuning/scripts/convert_aihub_generate.py --dry-run
    python ai/finetuning/scripts/convert_aihub_generate.py
    python ai/finetuning/scripts/convert_aihub_generate.py --template report
    python ai/finetuning/scripts/convert_aihub_generate.py --append
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

# -- sLLM 시스템 프롬프트 --
DYNAMIC_SYSTEM_PROMPT = DOC_GENERATE_SLLM_PROMPT

# ============================================================
# 필드 풀 (synthesize_generate.py와 동일)
# ============================================================

FIELD_POOLS = {
    "meeting_minutes": {
        "doc_type_name": "회의록",
        "input_label": "회의 내용",
        "core": [
            ("title", "회의 주제를 반영한 구체적인 제목"),
            ("date", "회의 날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)"),
            ("attendees", "참석자 이름 배열 (없으면 빈 배열)"),
        ],
        "meta": [
            ("time", "회의 시간 (예: '14:00~15:30')"),
            ("location", "회의 장소 (없으면 빈 문자열)"),
            ("meeting_type", "회의 유형 ('정기', '비정기', '긴급' 중 하나)"),
            ("author", "작성자 이름 (없으면 빈 문자열)"),
            ("moderator", "진행자/사회자 이름 (없으면 빈 문자열)"),
            ("department", "주관 부서명 (없으면 빈 문자열)"),
            ("duration", "회의 소요 시간 (예: '1시간 30분')"),
        ],
        "content": [
            ("summary", "회의에서 논의된 주요 내용을 3~5문장으로 요약"),
            ("content", "회의 내용을 상세하게 기술"),
            ("agenda", "회의 안건 목록 (배열)"),
            ("meeting_purpose", "회의 목적 (1~2문장)"),
            ("decisions", "결정된 사항 목록 (배열, 없으면 빈 배열)"),
            ("action_items", '후속 조치 목록 배열. 각 항목은 {"content": "내용", "assignee": "담당자", "due_date": "기한"} 형태'),
            ("risks", '리스크 목록 배열. 각 항목은 {"description": "설명", "level": "상/중/하", "mitigation": "대응방안"} 형태'),
            ("next_meeting", "다음 회의 일정 (없으면 빈 문자열)"),
            ("notes", "비고 사항 (없으면 빈 문자열)"),
        ],
    },
    "report": {
        "doc_type_name": "업무보고서",
        "input_label": "업무 내용",
        "core": [
            ("title", "업무 내용을 반영한 구체적인 보고서 제목"),
            ("date", "작성 날짜 (YYYY-MM-DD 형식)"),
            ("author", "작성자 이름 (없으면 빈 문자열)"),
        ],
        "meta": [
            ("department", "부서명 (없으면 빈 문자열)"),
            ("position", "직급 (없으면 빈 문자열)"),
            ("report_to", "보고 대상 (없으면 빈 문자열)"),
            ("report_type", "'일일', '주간', '월간', '수시' 중 하나"),
            ("period", "보고 기간 (예: '2026년 2월 1주차')"),
            ("audience", "보고 대상/독자 (없으면 빈 문자열)"),
        ],
        "content": [
            ("overview", "업무 내용을 요약한 보고 개요 (3~5문장)"),
            ("main_content", "업무 세부 내용을 항목별로 구체적으로 작성"),
            ("tasks", '진행 업무 목록 배열. 각 항목은 {"item": "업무명", "assignee": "담당자", "progress": "진행률", "start_date": "시작일", "end_date": "종료일"} 형태'),
            ("achievements", "주요 성과 목록 (배열)"),
            ("issues", "이슈 및 건의사항 (없으면 빈 문자열)"),
            ("kpi_results", "KPI 달성 현황 (없으면 빈 문자열)"),
            ("conclusion", "결론 및 종합 의견"),
            ("recommendations", "권장 사항 목록 (배열)"),
            ("next_plan", "향후 계획 (구체적으로 작성)"),
        ],
    },
    "proposal": {
        "doc_type_name": "제안서",
        "input_label": "제안 내용",
        "core": [
            ("title", "제안 내용을 반영한 구체적인 제안서 제목"),
            ("submit_date", "제출 날짜 (YYYY-MM-DD, 없으면 오늘 날짜)"),
            ("purpose", "제안 목적 및 필요성 (3~5문장)"),
        ],
        "meta": [
            ("submit_to", "제출처 (없으면 빈 문자열)"),
            ("company", "제안사 이름 (없으면 빈 문자열)"),
            ("manager", "담당자 이름 (없으면 빈 문자열)"),
            ("contact", "연락처 (없으면 빈 문자열)"),
            ("proposer", "제안자/제안사명 (없으면 빈 문자열)"),
            ("period", "제안 기간 (예: '2026년 3월 ~ 6월')"),
        ],
        "content": [
            ("background", "제안 배경 (2~3문장)"),
            ("current_situation", "현황 분석 (3~5문장)"),
            ("content", "제안 내용을 항목별로 구체적으로 작성"),
            ("scope", "사업 범위 (2~3문장)"),
            ("schedule", '추진 일정 배열. 각 항목은 {"phase": "단계", "task": "업무", "period": "기간"} 형태'),
            ("budget", '예산 배열. 각 항목은 {"item": "항목", "amount": "금액"} 형태'),
            ("budget_total", "합계 금액 (없으면 빈 문자열)"),
            ("expected_effect", "기대 효과 (3~5문장)"),
            ("resources", "필요 자원 (인력, 장비 등)"),
            ("risks", '리스크 및 대응 방안 배열. 각 항목은 {"risk": "리스크", "mitigation": "대응방안"} 형태'),
            ("deliverables", "산출물 목록 (배열)"),
        ],
    },
}


def select_random_fields(template: str, rng: random.Random) -> list[tuple[str, str]]:
    """필드 풀에서 랜덤 조합 선택. 필수 + 내용 2~4개 + 메타 1~3개."""
    pool = FIELD_POOLS[template]
    core = list(pool["core"])
    meta = list(pool["meta"])
    content = list(pool["content"])

    n_content = rng.randint(2, min(4, len(content)))
    selected_content = rng.sample(content, n_content)

    n_meta = rng.randint(1, min(3, len(meta)))
    selected_meta = rng.sample(meta, n_meta)

    return core + selected_meta + selected_content


def build_dynamic_user_prompt(template: str, passage: str, fields: list[tuple[str, str]]) -> str:
    """선택된 필드로 동적 user prompt 생성."""
    pool = FIELD_POOLS[template]
    doc_type = pool["doc_type_name"]
    input_label = pool["input_label"]

    field_lines = [f"- {name}: {desc}" for name, desc in fields]
    field_spec_str = "\n".join(field_lines)

    return (
        f"다음 내용을 바탕으로 문서를 JSON 형식으로 작성해주세요.\n\n"
        f"[문서 유형] {doc_type}\n\n"
        f"[필드 명세]\n{field_spec_str}\n\n"
        f"[{input_label}]\n{passage}"
    )


def validate_json_output(json_str: str, selected_fields: list[tuple[str, str]]) -> tuple[bool, dict | None, list[str]]:
    """생성된 JSON 검증 (선택된 필드 기준)"""
    errors = []

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return False, None, [f"JSON 파싱 실패: {e}"]

    if not isinstance(data, dict):
        return False, None, ["최상위가 dict가 아님"]

    korean_keys = [k for k in data.keys() if re.search(r"[\uac00-\ud7a3]", k)]
    if korean_keys:
        errors.append(f"한국어 키 발견: {korean_keys}")

    selected_names = [name for name, _ in selected_fields]
    missing = [f for f in selected_names if f not in data]
    if missing:
        errors.append(f"필드 누락: {missing}")

    extra = [k for k in data.keys() if k not in selected_names]
    if extra:
        errors.append(f"과잉 필드: {extra}")

    return len(errors) == 0, data, errors


# -- 카테고리 매핑 --

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

# -- 템플릿별 카테고리 -> 목표 수 --
TEMPLATE_TARGETS = {
    "meeting_minutes": {"회의록": 100},
    "report": {"보고서": 150, "간행물": 150},
    "proposal": {"보도자료": 300},
}

MIN_PASSAGE_LEN = 500
MAX_PASSAGE_LEN = 3000


def load_aihub_data(label_dir: Path, categories: list[str], limit_per_cat: int = 0) -> list[dict]:
    """AI Hub JSON 파일을 카테고리별로 로드."""
    all_docs = []

    if not label_dir.exists():
        print(f"[오류] 데이터 디렉토리 없음: {label_dir}")
        print(f"       AI Hub에서 데이터를 다운로드하세요:")
        print(f"       https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=582")
        sys.exit(1)

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
        cat_rng = random.Random(42)
        for sub_folder in sorted(cat_folder.iterdir()):
            if not sub_folder.is_dir():
                continue

            json_files = list(sub_folder.glob("*.json"))
            cat_rng.shuffle(json_files)

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

    print(f"\n  [{template}] 필터링 후 현황 ({min_len}~{max_len}자):")
    total_target = 0
    for cat, target in targets.items():
        count = len(by_category.get(cat, []))
        status = "OK" if count >= target else "부족"
        print(f"    {cat}: {count:,}건 사용 가능 (목표: {target}, {status})")
        total_target += target

    rng = random.Random(seed)
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
            selected.extend(rng.sample(pool, target))

    rng.shuffle(selected)
    print(f"  총 선별: {len(selected)}건 (목표: {total_target})")
    return selected


def call_gpt4o(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4o",
    max_retries: int = 3,
) -> str | None:
    """GPT-4o API 호출"""
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


def convert_template(
    selected: list[dict],
    template: str,
    output_path: Path,
    model: str = "gpt-4o",
    append: bool = False,
    seed: int = 42,
):
    """특정 템플릿에 대한 변환 수행 (필드 풀 랜덤 조합 + GPT-4o)"""
    sys_prompt = DYNAMIC_SYSTEM_PROMPT
    rng = random.Random(seed)

    mode = "a" if append else "w"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0

    with open(output_path, mode, encoding="utf-8") as f:
        for i, doc in enumerate(selected):
            passage = doc["passage"]

            # 매 샘플마다 필드 풀에서 랜덤 조합 선택
            selected_fields = select_random_fields(template, rng)
            field_names = [name for name, _ in selected_fields]
            user_prompt = build_dynamic_user_prompt(template, passage, selected_fields)

            print(f"    [{i+1}/{len(selected)}] ({len(selected_fields)}필드) GPT-4o...", end=" ", flush=True)

            # GPT-4o 호출
            json_output = call_gpt4o(sys_prompt, user_prompt, model=model)
            if not json_output:
                print("실패 (API)")
                failed += 1
                continue

            # 검증 (선택된 필드 기준)
            is_valid, parsed, errors = validate_json_output(json_output, selected_fields)

            # 과잉 필드 제거 후 재검증
            if not is_valid and parsed and errors:
                extra_errors = [e for e in errors if "과잉 필드" in e]
                if extra_errors and parsed:
                    for k in list(parsed.keys()):
                        if k not in field_names:
                            del parsed[k]
                    json_output = json.dumps(parsed, ensure_ascii=False)
                    is_valid, parsed, errors = validate_json_output(json_output, selected_fields)

            if not is_valid:
                print(f"실패 (검증: {errors})")
                failed += 1
                continue

            # 학습 데이터 저장
            sample = {
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": json_output},
                ]
            }

            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            success += 1
            print(f"OK ({len(parsed)}키)")

            # Rate limiting
            if (i + 1) % 10 == 0:
                time.sleep(1)
                print(f"    --- {i+1}건 완료 (성공: {success}, 실패: {failed}) ---")

    print(f"\n  [{template}] 결과: 성공 {success}, 실패 {failed}")
    return success


def main():
    parser = argparse.ArgumentParser(description="AI Hub -> v2_generate 변환 (필드 풀 방식)")
    parser.add_argument("--input", type=str, default=str(TRAIN_LABEL_DIR))
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR / "aihub_generate.jsonl"))
    parser.add_argument("--template", type=str, choices=["meeting_minutes", "report", "proposal", "all"], default="all")
    parser.add_argument("--total", type=int, default=700, help="총 변환 목표 건수")
    parser.add_argument("--model", type=str, default="gpt-4o")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip", type=int, default=0, help="각 템플릿별 앞쪽 N건 스킵")
    parser.add_argument("--min-len", type=int, default=MIN_PASSAGE_LEN)
    parser.add_argument("--max-len", type=int, default=MAX_PASSAGE_LEN)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not os.getenv("OPENAI_API_KEY"):
        print("[오류] OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    print("=" * 70)
    print("  AI Hub -> v2_generate 변환 (필드 풀 랜덤 조합 방식)")
    print("=" * 70)
    print(f"  입력: {args.input}")
    print(f"  출력: {args.output}")
    print(f"  모델: {args.model}")
    print(f"  목표: {args.total}건 (meeting_minutes 100 + report 300 + proposal 300)")
    print(f"  DRY RUN: {'ON' if args.dry_run else 'OFF'}")

    # 비율에 따른 할당
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

    needed_categories = set()
    for tmpl in templates_to_run:
        needed_categories.update(template_targets_scaled[tmpl].keys())

    # 1. 데이터 로드
    print(f"\n[1/3] 데이터 로드 (카테고리: {', '.join(needed_categories)})")
    data_dir = Path(args.input)
    docs = load_aihub_data(data_dir, list(needed_categories), limit_per_cat=2000)

    if not docs:
        print("[오류] 로드된 데이터가 없습니다.")
        sys.exit(1)

    # 2. 데이터 선별
    print(f"\n[2/3] 데이터 선별")
    template_selected = {}
    used_passages = set()

    for tmpl in templates_to_run:
        targets = template_targets_scaled[tmpl]
        available_docs = [d for d in docs if hash(d["passage"]) not in used_passages]
        selected = filter_and_select(available_docs, tmpl, targets, args.min_len, args.max_len, args.seed)
        for doc in selected:
            used_passages.add(hash(doc["passage"]))
        template_selected[tmpl] = selected

    if args.dry_run:
        print(f"\n[DRY RUN] 필드 조합 미리보기:")
        rng = random.Random(args.seed)
        for tmpl, selected in template_selected.items():
            print(f"\n  [{tmpl}] {len(selected)}건 선별됨")
            if selected:
                print(f"    샘플 원문 ({len(selected[0]['passage'])}자): {selected[0]['passage'][:100]}...")
            print(f"    샘플 필드 조합 3개:")
            for j in range(3):
                fields = select_random_fields(tmpl, rng)
                names = [f[0] for f in fields]
                print(f"      {j+1}. ({len(names)}필드) {names}")

        total = sum(len(s) for s in template_selected.values())
        print(f"\n  총 선별: {total}건")
        print(f"  예상 API 비용: ~${total * 0.04:.1f} (GPT-4o 기준)")
        return

    # 3. 변환
    print(f"\n[3/3] 변환 시작 (GPT-4o API 호출)")
    output_path = Path(args.output)
    total_success = 0

    for i, tmpl in enumerate(templates_to_run):
        selected = template_selected[tmpl]
        if not selected:
            continue
        if args.skip > 0 and i == 0:
            selected = selected[args.skip:]
            print(f"\n  === {tmpl} ({len(selected)}건, skip {args.skip}) ===")
        else:
            print(f"\n  === {tmpl} ({len(selected)}건) ===")
        is_append = args.append or (i > 0)
        success = convert_template(
            selected, tmpl, output_path,
            model=args.model, append=is_append, seed=args.seed + i,
        )
        total_success += success

    # 4. 결과 요약
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        print(f"\n  [결과 요약]")
        print(f"  총 데이터: {len(lines)}건")

        template_dist = {"meeting_minutes": 0, "report": 0, "proposal": 0}
        json_valid = 0
        field_count_dist = {}
        for line in lines:
            sample = json.loads(line)
            user_content = sample["messages"][1]["content"]
            assistant_content = sample["messages"][2]["content"]

            if "회의록" in user_content:
                template_dist["meeting_minutes"] += 1
            elif "제안서" in user_content:
                template_dist["proposal"] += 1
            else:
                template_dist["report"] += 1

            try:
                parsed = json.loads(assistant_content)
                json_valid += 1
                n_keys = len(parsed)
                field_count_dist[n_keys] = field_count_dist.get(n_keys, 0) + 1
            except json.JSONDecodeError:
                pass

        pct = json_valid / len(lines) * 100 if lines else 0
        print(f"  템플릿 분포: {template_dist}")
        print(f"  JSON 유효율: {json_valid}/{len(lines)} ({pct:.1f}%)")
        print(f"  필드 수 분포: {dict(sorted(field_count_dist.items()))}")

    print(f"\n  완료!")


if __name__ == "__main__":
    main()
