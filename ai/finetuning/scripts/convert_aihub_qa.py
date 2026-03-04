"""
AI Hub 데이터 → v2_qa 학습 데이터 변환 스크립트

소스 2가지:
  1. 행정 문서 대상 기계독해 (SN 569) → MRC → DOC_QA 형식 변환 (300개)
  2. 요약문 및 레포트 생성 데이터 (SN 582) → 원문 기반 QA쌍 생성 (300개)

타겟: data/training/v2_qa/aihub_qa.jsonl (600개)

SN 569 데이터 구조 (대용량 JSON 1건):
  {
    "Dataset": {...},
    "data": [
      {
        "doc_id": "...", "doc_title": "...",
        "paragraphs": [
          {
            "context": "지문 텍스트",
            "qas": [
              {
                "question": "질문",
                "answers": {"text": "답변", "answer_start": 123},
                "qa_type": 1
              }
            ]
          }
        ]
      }
    ]
  }

SN 582 데이터 구조 (개별 JSON):
  {
    "Meta(Acqusition)": {"doc_type": "paper", ...},
    "Meta(Refine)": {"passage": "원문 텍스트"},
    "Annotation": {"summary1": "...", "summary2": "...", "summary3": "..."}
  }

사용법:
    # dry-run (API 호출 없이 MRC 변환만)
    python ai/finetuning/scripts/convert_aihub_qa.py --dry-run

    # MRC 데이터만 변환 (API 불필요)
    python ai/finetuning/scripts/convert_aihub_qa.py --source mrc

    # 레포트 데이터만 변환 (API 필요)
    python ai/finetuning/scripts/convert_aihub_qa.py --source report

    # 전체 실행
    python ai/finetuning/scripts/convert_aihub_qa.py

    # 건수 조정
    python ai/finetuning/scripts/convert_aihub_qa.py --mrc-count 50 --report-count 30
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

# AI Hub 데이터 경로
MRC_BASE = BASE_DIR / "data" / "raw" / "aihub" / "016.행정 문서 대상 기계독해 데이터" / "01.데이터"
MRC_LABEL_DIR = MRC_BASE / "1.Training" / "라벨링데이터"

REPORT_BASE = BASE_DIR / "data" / "raw" / "aihub" / "022.요약문 및 레포트 생성 데이터" / "01.데이터"
REPORT_LABEL_DIR = REPORT_BASE / "1.Training" / "라벨링데이터" / "TL1"

OUTPUT_DIR = BASE_DIR / "data" / "training" / "v2_qa"

# ── 프로덕션 시스템 프롬프트 (ai/llm/prompts.py와 100% 일치) ──

SYSTEM_PROMPT = (
    "당신은 기업 문서 기반 질의응답 전문가입니다.\n"
    "주어진 문서 내용을 근거로 사용자의 질문에 정확하게 답변합니다.\n\n"
    "결과는 반드시 아래 JSON 형식으로만 응답하세요:\n"
    "{\n"
    '    "answer": "질문에 대한 답변",\n'
    '    "citations": [\n'
    '        {"source": "문서명/출처", "content": "인용 내용", "relevance": "높음|중간|낮음"}\n'
    "    ],\n"
    '    "confidence": 0.0~1.0\n'
    "}\n\n"
    "규칙:\n"
    "- 반드시 제공된 문서 내용만을 근거로 답변하세요.\n"
    "- 답변의 근거가 되는 문서 내용을 citations에 포함하세요.\n"
    "- 문서에서 답을 찾을 수 없으면 confidence를 낮게 설정하고 솔직히 답하세요.\n"
    "- 추측이나 외부 지식으로 답변을 보충하지 마세요.\n"
    "- JSON 외의 텍스트를 포함하지 마세요."
)

# QA 생성용 GPT-4o 프롬프트
QA_GENERATION_SYSTEM_PROMPT = (
    "주어진 문서 내용을 바탕으로 자연스러운 질문-답변 쌍을 생성하세요.\n\n"
    "규칙:\n"
    "- 질문은 실제 업무에서 할 법한 자연스러운 한국어로 작성하세요.\n"
    "- 답변은 반드시 문서 내용에 근거해야 합니다.\n"
    "- 답변에 인용할 수 있는 구체적인 문장을 포함하세요.\n\n"
    "JSON 형식으로 출력하세요:\n"
    "{\n"
    '  "question": "질문",\n'
    '  "answer": "답변",\n'
    '  "citation_text": "답변의 근거가 되는 원문 인용",\n'
    '  "source_title": "문서 제목 또는 출처"\n'
    "}"
)

CHUNK_SIZE = 250  # 청크 크기 (자)


# ── 공통 유틸 ──

def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """텍스트를 chunk_size 단위로 분할 (문장 경계 활용)"""
    if not text or len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    sentences = re.split(r"(?<=[.!?。])\s*", text)

    current_chunk = ""
    for sentence in sentences:
        if not sentence.strip():
            continue
        if len(current_chunk) + len(sentence) <= chunk_size:
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            while len(sentence) > chunk_size:
                chunks.append(sentence[:chunk_size].strip())
                sentence = sentence[chunk_size:]
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


# ── 소스 1: SN 569 MRC 데이터 변환 ──

def load_mrc_data(mrc_dir: Path, folders: list[str] = None) -> list[dict]:
    """SN 569 대용량 JSON 파일에서 QA 쌍 추출.

    각 폴더에 하나의 큰 JSON 파일이 있음:
    - TL_span_extraction: 추출형 QA (63,932 docs)
    - TL_span_extraction_how: 절차형 QA (29,074 docs)
    """
    if folders is None:
        folders = ["TL_span_extraction", "TL_span_extraction_how"]

    qa_pairs = []

    for folder_name in folders:
        folder_path = mrc_dir / folder_name
        if not folder_path.exists():
            print(f"  [경고] {folder_name} 없음")
            continue

        json_files = list(folder_path.glob("*.json"))
        if not json_files:
            print(f"  [경고] {folder_name}에 JSON 없음")
            continue

        for fp in json_files:
            print(f"  {folder_name}/{fp.name} 로딩...", end=" ", flush=True)
            try:
                with open(fp, encoding="utf-8") as f:
                    raw = json.load(f)

                data_list = raw.get("data", [])
                count = 0

                for doc in data_list:
                    title = doc.get("doc_title", "")
                    doc_class = doc.get("doc_class", "")

                    for para in doc.get("paragraphs", []):
                        context = para.get("context", "")
                        if not context or len(context) < 100:
                            continue

                        for qa in para.get("qas", []):
                            question = qa.get("question", "")
                            answers = qa.get("answers", {})

                            # answers가 dict (단일) or list
                            if isinstance(answers, dict):
                                answer_text = answers.get("text", "")
                            elif isinstance(answers, list) and answers:
                                answer_text = answers[0].get("text", "")
                            else:
                                continue

                            if not question or not answer_text:
                                continue

                            qa_pairs.append({
                                "context": context,
                                "question": question,
                                "answer": answer_text,
                                "qa_type": qa.get("qa_type", ""),
                                "title": title,
                                "doc_class": doc_class,
                                "source": folder_name,
                            })
                            count += 1

                print(f"{count:,}건 QA 추출")
            except Exception as e:
                print(f"에러: {e}")

    print(f"  총 MRC QA: {len(qa_pairs):,}건")
    return qa_pairs


def filter_mrc_pairs(
    qa_pairs: list[dict],
    max_count: int = 300,
    min_ctx: int = 150,
    max_ctx: int = 800,
    seed: int = 42,
) -> list[dict]:
    """MRC QA 쌍을 필터링 및 선별.

    - context 150~800자
    - answer 5자 이상
    - span_extraction과 span_extraction_how를 6:4 비율로 혼합
    """
    filtered = [
        qa for qa in qa_pairs
        if min_ctx <= len(qa["context"]) <= max_ctx and len(qa["answer"]) >= 5
    ]

    # 소스별 분리
    span = [qa for qa in filtered if qa["source"] == "TL_span_extraction"]
    how = [qa for qa in filtered if qa["source"] == "TL_span_extraction_how"]

    print(f"    필터링: span_extraction {len(span):,}건, span_extraction_how {len(how):,}건")

    random.seed(seed)
    random.shuffle(span)
    random.shuffle(how)

    # 6:4 비율
    span_target = int(max_count * 0.6)
    how_target = max_count - span_target

    selected = span[:span_target] + how[:how_target]

    # 부족하면 다른 쪽에서 보충
    if len(selected) < max_count:
        remaining = max_count - len(selected)
        extra = span[span_target:] + how[how_target:]
        selected.extend(extra[:remaining])

    random.shuffle(selected)
    print(f"    선별: {len(selected)}건 (목표: {max_count})")
    return selected


def convert_mrc_to_training(qa: dict) -> dict:
    """MRC QA 쌍을 v2_qa 학습 데이터 형식으로 변환"""
    context = qa["context"]
    question = qa["question"]
    answer_text = qa["answer"]
    title = qa.get("title", "행정 문서")

    # Context를 청크로 분할
    chunks = split_into_chunks(context)
    if not chunks:
        chunks = [context]

    # Context 배열 형태로 user prompt
    context_array = json.dumps(chunks, ensure_ascii=False)
    user_prompt = f"Context:\n{context_array}\n\nQuestion: {question}"

    # 답변이 포함된 청크를 citation으로
    citation_chunk = chunks[0]
    for chunk in chunks:
        if answer_text in chunk:
            citation_chunk = chunk
            break
        # 부분 매칭
        answer_words = answer_text.split()[:3]
        if any(w in chunk for w in answer_words if len(w) >= 2):
            citation_chunk = chunk
            break

    assistant_response = json.dumps({
        "answer": answer_text,
        "citations": [
            {
                "source": title if title else "행정 문서",
                "content": citation_chunk[:200] if len(citation_chunk) > 200 else citation_chunk,
                "relevance": "높음",
            }
        ],
        "confidence": 0.95,
    }, ensure_ascii=False)

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_response},
        ]
    }


def process_mrc_source(
    mrc_dir: Path,
    target_count: int = 300,
    seed: int = 42,
) -> list[dict]:
    """MRC 데이터 → v2_qa 형식 변환 (API 불필요)"""
    print(f"\n  [소스 1] 행정 문서 기계독해 (SN 569) → DOC_QA 변환")

    if not mrc_dir.exists():
        print(f"    [오류] 디렉토리 없음: {mrc_dir}")
        print(f"    다운로드: https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=569")
        return []

    # QA 쌍 로드
    qa_pairs = load_mrc_data(mrc_dir)
    if not qa_pairs:
        return []

    # 필터링 & 선별
    selected = filter_mrc_pairs(qa_pairs, target_count, seed=seed)

    # 변환
    training_samples = []
    for qa in selected:
        sample = convert_mrc_to_training(qa)
        training_samples.append(sample)

    print(f"    변환 완료: {len(training_samples)}건")
    return training_samples


# ── 소스 2: SN 582 레포트 데이터 → QA 생성 ──

REPORT_CATEGORIES = {
    "04.paper": "보고서",
    "05.minute": "회의록",
    "07.public": "간행물",
    "02.briefing": "보도자료",
    "01.news_r": "뉴스",
}


def load_report_passages(
    label_dir: Path,
    target_count: int = 300,
    min_len: int = 500,
    max_len: int = 1500,
) -> list[dict]:
    """SN 582에서 QA 생성용 passage 로드"""
    docs = []

    for folder_name, category in REPORT_CATEGORIES.items():
        folder_path = label_dir / folder_name
        if not folder_path.exists():
            continue

        limit = target_count  # 각 카테고리에서 충분히 로드
        cat_docs = []

        for sub_folder in sorted(folder_path.iterdir()):
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
                    if not passage or not (min_len <= len(passage) <= max_len):
                        continue
                    cat_docs.append({
                        "passage": passage,
                        "category": category,
                    })
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

            if len(cat_docs) >= limit:
                break

        docs.extend(cat_docs)
        print(f"    {folder_name} ({category}): {len(cat_docs):,}건")

    print(f"    총 로드: {len(docs):,}건")
    return docs


def generate_qa_from_passage(
    passage: str,
    doc_category: str,
    model: str = "gpt-4o",
    max_retries: int = 3,
) -> dict | None:
    """GPT-4o를 사용하여 passage에서 QA 쌍 생성"""
    try:
        from openai import OpenAI
    except ImportError:
        print("[오류] openai 패키지가 필요합니다: pip install openai")
        return None

    client = OpenAI()

    user_prompt = f"문서 카테고리: {doc_category}\n\n문서 내용:\n{passage[:2000]}"

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": QA_GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content.strip())
            return result
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"[API 에러] {e}")
                return None

    return None


def convert_report_qa_to_training(
    passage: str,
    qa_result: dict,
    doc_category: str,
) -> dict:
    """GPT-4o 생성 QA 결과 → v2_qa 학습 데이터"""
    chunks = split_into_chunks(passage)
    if not chunks:
        chunks = [passage[:CHUNK_SIZE]]

    context_array = json.dumps(chunks, ensure_ascii=False)
    question = qa_result.get("question", "")
    user_prompt = f"Context:\n{context_array}\n\nQuestion: {question}"

    answer = qa_result.get("answer", "")
    citation_text = qa_result.get("citation_text", "")
    source_title = qa_result.get("source_title", doc_category)

    assistant_response = json.dumps({
        "answer": answer,
        "citations": [
            {
                "source": source_title,
                "content": citation_text[:200] if len(citation_text) > 200 else citation_text,
                "relevance": "높음",
            }
        ],
        "confidence": 0.90,
    }, ensure_ascii=False)

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_response},
        ]
    }


def process_report_source(
    label_dir: Path,
    target_count: int = 300,
    model: str = "gpt-4o",
    seed: int = 42,
) -> list[dict]:
    """SN 582 레포트 데이터 → GPT-4o로 QA 쌍 생성"""
    print(f"\n  [소스 2] 요약문 레포트 데이터 (SN 582) → QA 생성")

    if not label_dir.exists():
        print(f"    [오류] 디렉토리 없음: {label_dir}")
        return []

    # passage 로드
    docs = load_report_passages(label_dir, target_count)

    random.seed(seed)
    random.shuffle(docs)

    if len(docs) > target_count:
        docs = docs[:target_count]
    print(f"    선별: {len(docs)}건")

    # GPT-4o로 QA 쌍 생성
    training_samples = []
    failed = 0

    for i, doc in enumerate(docs):
        passage = doc["passage"]
        category = doc["category"]

        print(f"    [{i+1}/{len(docs)}] GPT-4o QA 생성...", end=" ", flush=True)

        qa_result = generate_qa_from_passage(passage, category, model=model)
        if not qa_result or not qa_result.get("question") or not qa_result.get("answer"):
            print("실패")
            failed += 1
            continue

        sample = convert_report_qa_to_training(passage, qa_result, category)
        training_samples.append(sample)
        print("OK")

        # Rate limiting
        if (i + 1) % 10 == 0:
            time.sleep(1)
            print(f"    --- {i+1}건 완료 (성공: {len(training_samples)}, 실패: {failed}) ---")

    print(f"    변환 완료: {len(training_samples)}건 (실패: {failed}건)")
    return training_samples


# ── 메인 ──

def save_training_data(samples: list[dict], output_path: Path, append: bool = False):
    """학습 데이터를 JSONL로 저장"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"

    with open(output_path, mode, encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"\n  저장 완료: {len(samples)}건 → {output_path}")


def validate_output(output_path: Path):
    """출력 파일 간이 검증"""
    if not output_path.exists():
        return

    with open(output_path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    print(f"\n  [검증 요약]")
    print(f"  총 데이터: {len(lines)}건")

    json_valid = 0
    has_citations = 0
    has_confidence = 0

    for line in lines:
        sample = json.loads(line)
        assistant = sample["messages"][2]["content"]
        try:
            parsed = json.loads(assistant)
            json_valid += 1
            if "citations" in parsed and isinstance(parsed["citations"], list):
                has_citations += 1
            if "confidence" in parsed and isinstance(parsed["confidence"], (int, float)):
                has_confidence += 1
        except json.JSONDecodeError:
            pass

    pct = json_valid / len(lines) * 100 if lines else 0
    print(f"  JSON 유효: {json_valid}/{len(lines)} ({pct:.1f}%)")
    print(f"  citations 존재: {has_citations}/{len(lines)}")
    print(f"  confidence 존재: {has_confidence}/{len(lines)}")


def main():
    parser = argparse.ArgumentParser(description="AI Hub → v2_qa 변환")
    parser.add_argument("--mrc-dir", type=str, default=str(MRC_LABEL_DIR), help="SN 569 라벨링 디렉토리")
    parser.add_argument("--report-dir", type=str, default=str(REPORT_LABEL_DIR), help="SN 582 TL1 디렉토리")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR / "aihub_qa.jsonl"), help="출력 파일")
    parser.add_argument("--source", type=str, choices=["mrc", "report", "all"], default="all")
    parser.add_argument("--mrc-count", type=int, default=300, help="MRC 변환 목표 건수")
    parser.add_argument("--report-count", type=int, default=300, help="레포트 QA 생성 목표 건수")
    parser.add_argument("--model", type=str, default="gpt-4o", help="QA 생성용 모델")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 MRC 변환만 수행")
    args = parser.parse_args()

    print("=" * 70)
    print("  AI Hub → v2_qa 변환")
    print("=" * 70)
    print(f"  MRC 입력: {args.mrc_dir}")
    print(f"  레포트 입력: {args.report_dir}")
    print(f"  출력: {args.output}")
    print(f"  목표: MRC {args.mrc_count}건 + 레포트 {args.report_count}건 = {args.mrc_count + args.report_count}건")

    output_path = Path(args.output)
    all_samples = []

    # 소스 1: MRC 데이터 변환 (API 불필요)
    if args.source in ("mrc", "all"):
        mrc_samples = process_mrc_source(
            Path(args.mrc_dir), args.mrc_count, args.seed
        )
        all_samples.extend(mrc_samples)

    # 소스 2: 레포트 데이터 기반 QA 생성 (API 필요)
    if args.source in ("report", "all") and not args.dry_run:
        if not os.getenv("OPENAI_API_KEY"):
            print(f"\n  [경고] OPENAI_API_KEY 미설정 — 레포트 QA 생성 건너뜀")
        else:
            report_samples = process_report_source(
                Path(args.report_dir), args.report_count, args.model, args.seed
            )
            all_samples.extend(report_samples)

    if args.dry_run and args.source in ("report", "all"):
        print(f"\n  [DRY RUN] 레포트 QA 생성은 건너뜁니다 (API 필요)")

    # 저장
    if all_samples:
        random.seed(args.seed)
        random.shuffle(all_samples)
        save_training_data(all_samples, output_path)
        validate_output(output_path)
    else:
        print(f"\n  변환된 데이터가 없습니다.")

    print(f"\n  완료!")


if __name__ == "__main__":
    main()
