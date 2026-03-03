"""
모델 평가 모듈 (공용)

정량적 평가 지표:
  - 판단 정확도: Yes/No/Conditional 일치율 (v1 judgment)
  - 근거 적합성: 정답 조항 포함 여부 (v1 judgment)
  - RAG 검색: MRR, Recall@K (RAG 파이프라인)
  - 문서 생성: JSON 유효율, 필드 완전성, 필드명 정확도 (v2 doc_generate)
  - 문서 QA: Token F1, 인용 정확도 (v2 doc_qa)
  - 문서 요약: ROUGE-L, BERTScore, 포맷 준수율 (v2 doc_summary)
  - Action Item 추출: Precision, Recall, F1 (v2 doc_generate 하위)
"""
import json
import re
from collections import Counter


# ── 판단 평가 (v1 judgment) ──


def evaluate_judgment(predictions: list[dict], labels: list[dict]) -> dict:
    """판단 정확도 평가

    Args:
        predictions: [{"result": "yes/no/conditional/no_regulation", "confidence": float, ...}]
        labels: 동일 형식의 정답

    Returns:
        {
            "total": int,
            "accuracy": float,
            "category_accuracy": {"yes": float, "no": float, ...},
            "confusion_matrix": {"yes": {"yes": N, "no": N, ...}, ...}
        }
    """
    if len(predictions) != len(labels):
        raise ValueError(f"predictions({len(predictions)})와 labels({len(labels)}) 길이 불일치")

    total = len(predictions)
    correct = 0
    category_stats = {}  # {category: {"correct": N, "total": N}}
    confusion = {}  # {gold: {pred: count}}

    for pred, gold in zip(predictions, labels):
        pred_result = pred.get("result", "").lower().strip()
        gold_result = gold.get("result", "").lower().strip()

        # 카테고리 통계 초기화
        if gold_result not in category_stats:
            category_stats[gold_result] = {"correct": 0, "total": 0}
        if gold_result not in confusion:
            confusion[gold_result] = Counter()

        category_stats[gold_result]["total"] += 1
        confusion[gold_result][pred_result] += 1

        if pred_result == gold_result:
            correct += 1
            category_stats[gold_result]["correct"] += 1

    category_accuracy = {
        cat: stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        for cat, stats in category_stats.items()
    }

    return {
        "total": total,
        "accuracy": correct / total if total > 0 else 0,
        "category_accuracy": category_accuracy,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
    }


# ── RAG 검색 평가 ──


def evaluate_rag(retrieved: list[list[str]], relevant: list[list[str]]) -> dict:
    """RAG 검색 평가 — MRR, Recall@K

    Args:
        retrieved: [[doc_id, ...], ...] — 각 쿼리별 검색된 문서 ID 리스트 (순위순)
        relevant: [[doc_id, ...], ...] — 각 쿼리별 정답 문서 ID 리스트

    Returns:
        {"mrr": float, "recall@1": float, "recall@3": float, "recall@5": float, "total": int}
    """
    if len(retrieved) != len(relevant):
        raise ValueError(f"retrieved({len(retrieved)})와 relevant({len(relevant)}) 길이 불일치")

    total = len(retrieved)
    mrr_sum = 0.0
    recall_at = {1: 0, 3: 0, 5: 0}

    for ret_docs, rel_docs in zip(retrieved, relevant):
        rel_set = set(rel_docs)

        # MRR: 첫 번째 정답 문서의 역순위
        rr = 0.0
        for rank, doc_id in enumerate(ret_docs, 1):
            if doc_id in rel_set:
                rr = 1.0 / rank
                break
        mrr_sum += rr

        # Recall@K
        for k in recall_at:
            top_k = set(ret_docs[:k])
            if rel_set & top_k:
                recall_at[k] += 1

    return {
        "total": total,
        "mrr": mrr_sum / total if total > 0 else 0,
        **{f"recall@{k}": v / total if total > 0 else 0 for k, v in recall_at.items()},
    }


# ── 문서 생성 평가 (v2 doc_generate) ──


# 템플릿별 필수 필드
_REQUIRED_FIELDS = {
    "meeting_minutes": ["title", "date", "attendees", "summary", "decisions", "action_items"],
    "report": ["title", "author", "date", "department", "report_type", "overview", "main_content", "tasks"],
    "proposal": [
        "title", "submit_date", "submit_to", "company", "manager",
        "proposal_name", "background", "purpose", "content", "schedule", "budget",
    ],
    "jd": ["position", "employment_type", "responsibilities", "requirements"],
}


def evaluate_doc_generate(
    predictions: list[str],
    references: list[str],
    template_types: list[str],
) -> dict:
    """문서 생성 평가

    Args:
        predictions: LLM이 생성한 JSON 문자열 리스트
        references: 정답 JSON 문자열 리스트
        template_types: 각 샘플의 템플릿 타입 ("meeting_minutes", "report", ...)

    Returns:
        {
            "total": int,
            "json_valid_rate": float,    # JSON 파싱 성공률
            "field_completeness": float, # 필수 필드 존재율
            "field_accuracy": float,     # 필드명 정확도
            "per_template": {template_type: {...}, ...}
        }
    """
    total = len(predictions)
    json_valid = 0
    field_complete = 0
    field_accurate = 0
    per_template = {}

    for pred_str, ref_str, ttype in zip(predictions, references, template_types):
        if ttype not in per_template:
            per_template[ttype] = {"total": 0, "json_valid": 0, "field_complete": 0, "field_accurate": 0}
        per_template[ttype]["total"] += 1

        # JSON 파싱
        pred_json = _safe_parse_json(pred_str)
        if pred_json is None:
            continue

        json_valid += 1
        per_template[ttype]["json_valid"] += 1

        # 필드 완전성
        required = _REQUIRED_FIELDS.get(ttype, [])
        pred_keys = set(pred_json.keys())
        if all(f in pred_keys for f in required):
            field_complete += 1
            per_template[ttype]["field_complete"] += 1

        # 필드명 정확도: 정답 JSON의 모든 키가 예측에 존재하는지
        ref_json = _safe_parse_json(ref_str)
        if ref_json:
            ref_keys = set(ref_json.keys())
            if ref_keys.issubset(pred_keys):
                field_accurate += 1
                per_template[ttype]["field_accurate"] += 1

    # 비율 계산
    per_template_rates = {}
    for ttype, stats in per_template.items():
        t = stats["total"]
        jv = stats["json_valid"]
        per_template_rates[ttype] = {
            "total": t,
            "json_valid_rate": jv / t if t > 0 else 0,
            "field_completeness": stats["field_complete"] / t if t > 0 else 0,
            "field_accuracy": stats["field_accurate"] / max(jv, 1),
        }

    return {
        "total": total,
        "json_valid_rate": json_valid / total if total > 0 else 0,
        "field_completeness": field_complete / total if total > 0 else 0,
        "field_accuracy": field_accurate / max(json_valid, 1),
        "per_template": per_template_rates,
    }


# ── 문서 QA 평가 (v2 doc_qa) ──


def evaluate_doc_qa(
    predictions: list[str],
    references: list[str],
) -> dict:
    """문서 QA 평가

    Args:
        predictions: LLM이 생성한 JSON 문자열 (answer, citations, confidence)
        references: 정답 JSON 문자열

    Returns:
        {
            "total": int,
            "json_valid_rate": float,
            "token_f1": float,
            "citation_accuracy": float,
        }
    """
    total = len(predictions)
    json_valid = 0
    f1_sum = 0.0
    citation_correct = 0

    for pred_str, ref_str in zip(predictions, references):
        pred_json = _safe_parse_json(pred_str)
        if pred_json is None:
            continue

        json_valid += 1

        # Token F1
        pred_answer = pred_json.get("answer", "")
        ref_json = _safe_parse_json(ref_str)
        ref_answer = ref_json.get("answer", ref_str) if ref_json else ref_str
        f1_sum += _token_f1(pred_answer, ref_answer)

        # 인용 정확도: citations 배열이 존재하고 비어있지 않으면 정확
        citations = pred_json.get("citations", [])
        if isinstance(citations, list) and len(citations) > 0:
            # 각 citation에 source, content 키가 있는지
            valid_citations = [c for c in citations if isinstance(c, dict) and "content" in c]
            if valid_citations:
                citation_correct += 1

    return {
        "total": total,
        "json_valid_rate": json_valid / total if total > 0 else 0,
        "token_f1": f1_sum / max(json_valid, 1),
        "citation_accuracy": citation_correct / max(json_valid, 1),
    }


# ── 문서 요약 평가 (v2 doc_summary) ──


def evaluate_summary(predictions: list[str], references: list[str]) -> dict:
    """요약 평가 — ROUGE-L, 포맷 준수율

    Args:
        predictions: LLM이 생성한 요약 텍스트 (마크다운)
        references: 정답 요약 텍스트

    Returns:
        {
            "total": int,
            "rouge_l": float,
            "format_compliance": float,
            "avg_length": float,
        }
    """
    total = len(predictions)
    rouge_l_sum = 0.0
    format_ok = 0
    total_length = 0

    for pred, ref in zip(predictions, references):
        # ROUGE-L
        rouge_l_sum += _rouge_l(pred, ref)

        # 포맷 준수: 마크다운 구조 (제목/키포인트/키워드 중 2개 이상)
        structure_markers = 0
        if "##" in pred or "**" in pred:
            structure_markers += 1
        if "포인트" in pred or "요점" in pred or "핵심" in pred or "-" in pred:
            structure_markers += 1
        if "키워드" in pred or "keyword" in pred.lower():
            structure_markers += 1
        if len(pred) > 50:
            structure_markers += 1

        if structure_markers >= 2:
            format_ok += 1

        total_length += len(pred)

    return {
        "total": total,
        "rouge_l": rouge_l_sum / total if total > 0 else 0,
        "format_compliance": format_ok / total if total > 0 else 0,
        "avg_length": total_length / total if total > 0 else 0,
    }


# ── Action Item 추출 평가 ──


def evaluate_action_items(predictions: list[list[dict]], labels: list[list[dict]]) -> dict:
    """Action Item 추출 평가 — Precision, Recall, F1

    Args:
        predictions: [[{"content": "...", "assignee": "...", "due_date": "..."}, ...], ...]
        labels: 동일 형식의 정답

    Returns:
        {"precision": float, "recall": float, "f1": float, "total_pred": int, "total_gold": int}
    """
    total_pred = 0
    total_gold = 0
    total_match = 0

    for pred_items, gold_items in zip(predictions, labels):
        # content 기준으로 매칭 (부분 일치)
        pred_contents = [item.get("content", "").strip() for item in pred_items if item.get("content")]
        gold_contents = [item.get("content", "").strip() for item in gold_items if item.get("content")]

        total_pred += len(pred_contents)
        total_gold += len(gold_contents)

        matched_gold = set()
        for pc in pred_contents:
            for j, gc in enumerate(gold_contents):
                if j not in matched_gold and _is_partial_match(pc, gc):
                    total_match += 1
                    matched_gold.add(j)
                    break

    precision = total_match / total_pred if total_pred > 0 else 0
    recall = total_match / total_gold if total_gold > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "total_pred": total_pred,
        "total_gold": total_gold,
        "total_match": total_match,
    }


# ── 유틸리티 ──


def _safe_parse_json(text: str) -> dict | None:
    """텍스트에서 JSON 추출 (```json 블록, 순수 JSON 등)"""
    if not text:
        return None
    text = text.strip()
    # ```json ... ``` 블록 추출
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    # 첫 { ... } 블록
    if not text.startswith("{"):
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _token_f1(prediction: str, reference: str) -> float:
    """토큰 단위 F1 스코어"""
    pred_tokens = set(prediction.split())
    ref_tokens = set(reference.split())
    if not pred_tokens or not ref_tokens:
        return 0.0
    common = pred_tokens & ref_tokens
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(ref_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _rouge_l(prediction: str, reference: str) -> float:
    """ROUGE-L (LCS 기반)"""
    pred_tokens = prediction.split()
    ref_tokens = reference.split()
    if not pred_tokens or not ref_tokens:
        return 0.0

    m, n = len(pred_tokens), len(ref_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if pred_tokens[i - 1] == ref_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs_len = dp[m][n]

    precision = lcs_len / m if m > 0 else 0
    recall = lcs_len / n if n > 0 else 0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _is_partial_match(pred: str, gold: str, threshold: float = 0.5) -> bool:
    """부분 일치 판정 (토큰 기반)"""
    pred_tokens = set(pred.split())
    gold_tokens = set(gold.split())
    if not gold_tokens:
        return False
    overlap = len(pred_tokens & gold_tokens)
    return overlap / len(gold_tokens) >= threshold
