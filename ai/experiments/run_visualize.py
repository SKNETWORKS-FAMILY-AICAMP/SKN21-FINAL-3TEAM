"""
차트 생성: 방법론 비교 막대 그래프 + v1.0→v1.1 개선 차트

실행:
    pip install matplotlib
    python ai/experiments/run_visualize.py

사전 조건:
    results/method_comparison.json  (run_method_comparison.py 결과)
    results/gpt_comparison.json     (run_gpt_comparison.py 결과, 선택)
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def generate_method_comparison_chart():
    """실험 1: 방법론 비교 — 가로 막대 그래프"""

    all_results = []

    mc_path = RESULTS_DIR / "method_comparison.json"
    if mc_path.exists():
        with open(mc_path, "r", encoding="utf-8") as f:
            all_results.extend(json.load(f))

    gpt_path = RESULTS_DIR / "gpt_comparison.json"
    if gpt_path.exists():
        with open(gpt_path, "r", encoding="utf-8") as f:
            all_results.extend(json.load(f))

    if not all_results:
        print("  ERROR: 결과 파일이 없습니다.")
        return

    # F1 기준 정렬 (낮→높, 위→아래)
    all_results.sort(key=lambda x: x["f1_macro"])

    methods = [r["method"] for r in all_results]
    f1_scores = [r["f1_macro"] for r in all_results]

    colors = []
    for m in methods:
        if "Fine-tuned" in m:
            colors.append("#1976D2")
        elif "GPT" in m:
            colors.append("#FF9800")
        elif "Rule" in m:
            colors.append("#78909C")
        else:
            colors.append("#BDBDBD")

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(methods, f1_scores, color=colors, height=0.6)

    for bar, score in zip(bars, f1_scores):
        ax.text(
            bar.get_width() + 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{score:.1%}",
            va="center", fontsize=11, fontweight="bold",
        )

    ax.set_xlabel("F1 Score (macro)", fontsize=12)
    ax.set_title(
        "Intent Classification — Method Comparison\n"
        "(Adversarial Test Set, 70 samples)",
        fontsize=13,
    )
    ax.set_xlim(0, 1.15)
    ax.axvline(x=1 / 7, color="red", linestyle="--", alpha=0.4, label="Random (1/7)")
    ax.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "method_comparison.png", dpi=150)
    plt.close()
    print("    -> method_comparison.png")

    # 속도/비용 요약 테이블 출력
    all_results.sort(key=lambda x: x["f1_macro"], reverse=True)
    print(f"\n  {'Method':<20} {'F1':>8} {'Acc':>8} {'Speed':>10} {'Cost':>15}")
    print(f"  {'-' * 63}")
    for r in all_results:
        print(
            f"  {r['method']:<20} {r['f1_macro']:>8.4f} {r['accuracy']:>8.4f}"
            f" {r['time_ms']:>8.1f}ms {r.get('cost', ''):>15}"
        )


def generate_improvement_chart():
    """실험 3: v1.0 → v1.1 개선 차트 (TRAINING_LOG.md 수치 활용)"""

    versions = ["v1.0", "v1.1"]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    # 1) Eval F1
    eval_f1 = [99.08, 98.80]
    b1 = axes[0].bar(versions, eval_f1, color=["#90CAF9", "#1976D2"], width=0.5)
    axes[0].set_ylabel("F1 Score (%)")
    axes[0].set_title("Eval F1 (macro)")
    axes[0].set_ylim(97, 100)
    for bar, val in zip(b1, eval_f1):
        axes[0].text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
            f"{val}%", ha="center", fontsize=12, fontweight="bold",
        )

    # 2) Adversarial Accuracy
    adv_acc = [72.0, 88.0]
    b2 = axes[1].bar(versions, adv_acc, color=["#FFCC80", "#FF9800"], width=0.5)
    axes[1].set_ylabel("Accuracy (%)")
    axes[1].set_title("Adversarial Test (25 samples)")
    axes[1].set_ylim(0, 100)
    for bar, val in zip(b2, adv_acc):
        axes[1].text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
            f"{val}%", ha="center", fontsize=12, fontweight="bold",
        )
    # 화살표 + 개선폭
    axes[1].annotate(
        "+16%p", xy=(1, 88), xytext=(0.5, 95),
        fontsize=13, color="#E65100", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#E65100"),
        ha="center",
    )

    # 3) judgment→general 오분류
    errors = [5, 0]
    b3 = axes[2].bar(versions, errors, color=["#EF9A9A", "#4CAF50"], width=0.5)
    axes[2].set_ylabel("Error Count")
    axes[2].set_title("judgment -> general Errors")
    axes[2].set_ylim(0, 7)
    for bar, val in zip(b3, errors):
        axes[2].text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.15,
            str(val), ha="center", fontsize=14, fontweight="bold",
        )

    fig.suptitle(
        "Model Improvement: v1.0 -> v1.1\n"
        "(+50 casual judgment samples)",
        fontsize=14, fontweight="bold",
    )
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "improvement_v1.png", dpi=150)
    plt.close()
    print("    -> improvement_v1.png")


def generate_all_versions_chart():
    """전체 버전 비교 차트 (v1.0 ~ v1.4)"""

    versions = ["v1.0", "v1.1", "v1.2", "v1.3", "v1.4"]

    # ── 데이터 ──
    eval_f1 = [99.08, 98.80, 98.07, 97.87, 98.26]
    # v1.0/v1.1: 25-sample adversarial (다른 셋이므로 비교 불가 → None)
    # v1.2~v1.4: 120-sample adversarial
    adv_acc_120 = [None, None, 85.0, 90.0, 89.2]
    adv_f1_120 = [None, None, 85.57, 89.92, 89.02]
    data_count = [1405, 1455, 1755, 1918, 1918]
    errors_120 = [None, None, 18, 12, 13]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # ── 1) Eval F1 (전 버전) ──
    colors1 = ["#90CAF9", "#64B5F6", "#42A5F5", "#1976D2", "#0D47A1"]
    b1 = axes[0, 0].bar(versions, eval_f1, color=colors1, width=0.6)
    axes[0, 0].set_ylabel("F1 Score (%)")
    axes[0, 0].set_title("Eval F1 (macro) — All Versions")
    axes[0, 0].set_ylim(96.5, 100)
    for bar, val in zip(b1, eval_f1):
        axes[0, 0].text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
            f"{val:.2f}%", ha="center", fontsize=10, fontweight="bold",
        )

    # ── 2) Adversarial F1 (v1.2~v1.4, 120 samples) ──
    v_adv = ["v1.2", "v1.3", "v1.4"]
    f1_adv = [85.57, 89.92, 89.02]
    colors2 = ["#FFCC80", "#FF9800", "#E65100"]
    b2 = axes[0, 1].bar(v_adv, f1_adv, color=colors2, width=0.5)
    axes[0, 1].set_ylabel("F1 Score (%)")
    axes[0, 1].set_title("Adversarial F1 (120 samples)")
    axes[0, 1].set_ylim(80, 95)
    for bar, val in zip(b2, f1_adv):
        axes[0, 1].text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
            f"{val:.2f}%", ha="center", fontsize=11, fontweight="bold",
        )
    # 최고점 표시
    axes[0, 1].bar(["v1.3"], [89.92], color="#FF9800", width=0.5,
                    edgecolor="#E65100", linewidth=2.5)
    axes[0, 1].annotate(
        "BEST", xy=(1, 89.92), xytext=(1, 93),
        fontsize=12, color="#E65100", fontweight="bold", ha="center",
        arrowprops=dict(arrowstyle="->", color="#E65100"),
    )

    # ── 3) 오분류 건수 (v1.2~v1.4) ──
    err_vals = [18, 12, 13]
    colors3 = ["#EF9A9A", "#4CAF50", "#FFA726"]
    b3 = axes[1, 0].bar(v_adv, err_vals, color=colors3, width=0.5)
    axes[1, 0].set_ylabel("Error Count")
    axes[1, 0].set_title("Adversarial Misclassifications (of 120)")
    axes[1, 0].set_ylim(0, 25)
    for bar, val in zip(b3, err_vals):
        axes[1, 0].text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.4,
            str(val), ha="center", fontsize=13, fontweight="bold",
        )
    # 개선 화살표
    axes[1, 0].annotate(
        "-6", xy=(1, 12), xytext=(0.5, 5),
        fontsize=14, color="#2E7D32", fontweight="bold", ha="center",
        arrowprops=dict(arrowstyle="->", color="#2E7D32"),
    )

    # ── 4) 데이터 규모 변화 ──
    colors4 = ["#E0E0E0", "#BDBDBD", "#9E9E9E", "#757575", "#616161"]
    b4 = axes[1, 1].bar(versions, data_count, color=colors4, width=0.6)
    axes[1, 1].set_ylabel("Training Samples")
    axes[1, 1].set_title("Training Data Size")
    axes[1, 1].set_ylim(0, 2200)
    for bar, val in zip(b4, data_count):
        axes[1, 1].text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 20,
            f"{val:,}", ha="center", fontsize=10, fontweight="bold",
        )

    fig.suptitle(
        "Intent Classification — Version Progression (v1.0 -> v1.4)\n"
        "Data Quality > Hyperparameters",
        fontsize=14, fontweight="bold",
    )
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "improvement_all_versions.png", dpi=150)
    plt.close()
    print("    -> improvement_all_versions.png")


def main():
    print("=" * 60)
    print("  차트 생성")
    print("=" * 60)

    print("\n[1/2] 방법론 비교 차트...")
    generate_method_comparison_chart()

    print("\n[2/3] v1.0 → v1.1 개선 차트...")
    generate_improvement_chart()

    print("\n[3/3] 전체 버전 비교 차트...")
    generate_all_versions_chart()

    print(f"\n{'=' * 60}")
    print("  생성된 파일:")
    for f in sorted(RESULTS_DIR.glob("*.png")):
        print(f"    {f.name}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
