"""
qualitative_samples.json에서 BERTScore만 계산하는 스크립트
추론 없이 저장된 pred/gold 텍스트에서 바로 계산

사용법:
    python ai/finetuning/scripts/compute_bertscore.py \
        --input outputs/v2_summary/kanana-1.5-8b-instruct-2505/qualitative_samples.json
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="BERTScore 계산 (qualitative_samples.json)")
    parser.add_argument("--input", required=True, help="qualitative_samples.json 경로")
    args = parser.parse_args()

    input_path = Path(args.input)
    with open(input_path, encoding="utf-8") as f:
        samples = json.load(f)

    preds = [s["pred_summary"] or "" for s in samples]
    refs = [s["gold_summary"] or "" for s in samples]

    print(f"샘플 수: {len(samples)}건")
    print(f"BERTScore 계산 중 (klue/roberta-large, num_layers=24)...")

    from bert_score import score as bert_score_fn
    P, R, F1 = bert_score_fn(
        preds, refs,
        model_type="klue/roberta-large",
        num_layers=24,
        lang="ko",
        verbose=True,
        device="cuda",
    )

    avg_p = P.mean().item()
    avg_r = R.mean().item()
    avg_f1 = F1.mean().item()

    print(f"\n{'='*50}")
    print(f"  BERTScore 결과 ({len(samples)}건)")
    print(f"{'='*50}")
    print(f"  Precision: {avg_p:.4f}")
    print(f"  Recall:    {avg_r:.4f}")
    print(f"  F1:        {avg_f1:.4f}")

    # 개별 점수 분포
    f1_list = F1.tolist()
    print(f"\n  F1 분포:")
    print(f"    min:  {min(f1_list):.4f}")
    print(f"    max:  {max(f1_list):.4f}")
    print(f"    <0.7: {sum(1 for x in f1_list if x < 0.7)}건")
    print(f"    0.7~0.8: {sum(1 for x in f1_list if 0.7 <= x < 0.8)}건")
    print(f"    0.8~0.9: {sum(1 for x in f1_list if 0.8 <= x < 0.9)}건")
    print(f"    ≥0.9: {sum(1 for x in f1_list if x >= 0.9)}건")

    # 최하위 5건
    indexed = sorted(enumerate(f1_list), key=lambda x: x[1])
    print(f"\n  최하위 5건:")
    for idx, score in indexed[:5]:
        s = samples[idx]
        print(f"    [{idx}] F1={score:.4f} | {s['gold_summary'][:60]}...")

    # 결과 저장
    result = {
        "bertscore_precision": round(avg_p, 4),
        "bertscore_recall": round(avg_r, 4),
        "bertscore_f1": round(avg_f1, 4),
        "per_sample_f1": [round(x, 4) for x in f1_list],
    }
    out_path = input_path.parent / "bertscore_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {out_path}")


if __name__ == "__main__":
    main()
