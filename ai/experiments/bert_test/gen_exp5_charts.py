"""실험 5 통합 비교 차트 생성 (일회성 스크립트)"""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"

# ── 데이터 로드 ──
def load_all():
    models = {}
    for fname in ["model_comparison_bert.json", "model_comparison.json", "model_comparison_koelectra.json"]:
        with open(RESULTS / fname, encoding="utf-8") as f:
            d = json.load(f)
        key = list(d.keys())[0]
        models[key] = d[key]

    grids = {}
    for fname, label in [("grid_search_bert.json", "BERT"), ("grid_search_full.json", "RoBERTa"), ("grid_search_koelectra.json", "KoELECTRA")]:
        with open(RESULTS / fname, encoding="utf-8") as f:
            grids[label] = json.load(f)

    return models, grids


# ── Chart 1: 3모델 성능 비교 (4지표 막대 그래프) ──
def plot_model_comparison(models):
    labels_short = ["BERT", "RoBERTa", "KoELECTRA"]
    keys = ["klue/bert-base", "klue/roberta-base", "monologg/koelectra-base-v3-discriminator"]

    metrics = {
        "Eval F1": [models[k]["best_result"]["eval_f1"] for k in keys],
        "Adv Accuracy": [models[k]["best_result"]["adv_acc"] for k in keys],
        "Adv F1": [models[k]["best_result"]["adv_f1"] for k in keys],
    }

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    colors = ["#2196F3", "#4CAF50", "#FF9800"]

    for ax, (metric_name, values) in zip(axes, metrics.items()):
        bars = ax.bar(labels_short, values, color=colors, edgecolor="black", linewidth=0.5, width=0.6)
        ax.set_title(metric_name, fontsize=13, fontweight="bold")
        ax.set_ylim(min(values) - 0.02, max(values) + 0.015)

        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.002,
                    f"{val:.4f}", ha="center", va="bottom", fontsize=10, fontweight="bold")

        # best 표시
        best_idx = np.argmax(values)
        bars[best_idx].set_edgecolor("#D32F2F")
        bars[best_idx].set_linewidth(2.5)

    plt.suptitle("Experiment 5: Model Comparison (Best Config per Model)",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(RESULTS / "model_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  -> model_comparison.png")


# ── Chart 2: 추론 속도 + 학습 시간 비교 ──
def plot_speed_comparison(models):
    labels_short = ["BERT", "RoBERTa", "KoELECTRA"]
    keys = ["klue/bert-base", "klue/roberta-base", "monologg/koelectra-base-v3-discriminator"]

    infer_ms = [models[k]["best_result"]["infer_ms"] for k in keys]
    train_sec = [models[k]["best_result"]["train_time"] for k in keys]
    epochs = [models[k]["best_config"]["epochs"] for k in keys]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    colors = ["#2196F3", "#4CAF50", "#FF9800"]

    # 추론 속도
    bars1 = ax1.bar(labels_short, infer_ms, color=colors, edgecolor="black", linewidth=0.5, width=0.6)
    ax1.set_title("Inference Speed (ms/sample)", fontsize=13, fontweight="bold")
    ax1.set_ylabel("ms")
    ax1.set_ylim(0, max(infer_ms) + 2)
    for bar, val in zip(bars1, infer_ms):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.15,
                f"{val:.2f}ms", ha="center", va="bottom", fontsize=11, fontweight="bold")

    # 학습 시간 (best config 기준)
    bars2 = ax2.bar(labels_short, train_sec, color=colors, edgecolor="black", linewidth=0.5, width=0.6)
    ax2.set_title("Training Time — Best Config (seconds)", fontsize=13, fontweight="bold")
    ax2.set_ylabel("seconds")
    ax2.set_ylim(0, max(train_sec) + 20)
    for bar, val, ep in zip(bars2, train_sec, epochs):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                f"{val:.0f}s\n(ep={ep})", ha="center", va="bottom", fontsize=10)

    plt.suptitle("Experiment 5: Speed Comparison", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(RESULTS / "inference_speed.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  -> inference_speed.png")


# ── Chart 3: 3모델 그리드 서치 Adv F1 분포 (Box/Strip) ──
def plot_grid_distribution(grids):
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#2196F3", "#4CAF50", "#FF9800"]
    model_names = ["BERT", "RoBERTa", "KoELECTRA"]

    data = []
    positions = []
    for i, (name, runs) in enumerate(grids.items()):
        adv_f1s = [r["adv_f1"] for r in runs]
        data.append(adv_f1s)
        positions.append(i)

    bp = ax.boxplot(data, positions=positions, widths=0.5, patch_artist=True,
                    showmeans=True, meanline=True,
                    meanprops=dict(color="red", linewidth=2),
                    medianprops=dict(color="black", linewidth=1.5))

    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    # 각 모델 best 표시
    model_keys_full = ["klue/bert-base", "klue/roberta-base", "monologg/koelectra-base-v3-discriminator"]
    models, _ = load_all()
    for i, key in enumerate(model_keys_full):
        best_f1 = models[key]["best_result"]["adv_f1"]
        ax.scatter(i, best_f1, color="red", s=120, zorder=5, marker="*", label="Best" if i == 0 else None)
        ax.annotate(f"{best_f1:.4f}", (i, best_f1), textcoords="offset points",
                   xytext=(15, 5), fontsize=9, fontweight="bold", color="red")

    ax.set_xticks(positions)
    ax.set_xticklabels(model_names, fontsize=12)
    ax.set_ylabel("Adversarial F1", fontsize=12)
    ax.set_title("Experiment 5: Grid Search Adv F1 Distribution (51 runs each)",
                 fontsize=13, fontweight="bold")
    ax.legend(loc="lower right")
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(RESULTS / "grid_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  -> grid_distribution.png")


# ── Chart 4: 종합 레이더 차트 ──
def plot_radar(models):
    labels_short = ["BERT", "RoBERTa", "KoELECTRA"]
    keys = ["klue/bert-base", "klue/roberta-base", "monologg/koelectra-base-v3-discriminator"]
    colors = ["#2196F3", "#4CAF50", "#FF9800"]

    # 지표 (높을수록 좋게 정규화)
    categories = ["Eval F1", "Adv Acc", "Adv F1", "Speed\n(1/ms)", "Train Efficiency\n(1/time)"]

    values = []
    for k in keys:
        r = models[k]["best_result"]
        values.append([
            r["eval_f1"],
            r["adv_acc"],
            r["adv_f1"],
            1.0 / r["infer_ms"] * 7,  # normalize: faster = higher
            1.0 / r["train_time"] * 60,  # normalize: faster = higher
        ])

    # min-max normalize per metric
    values = np.array(values)
    for j in range(values.shape[1]):
        vmin, vmax = values[:, j].min(), values[:, j].max()
        if vmax > vmin:
            values[:, j] = 0.3 + 0.7 * (values[:, j] - vmin) / (vmax - vmin)
        else:
            values[:, j] = 1.0

    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    for i, (label, vals, color) in enumerate(zip(labels_short, values, colors)):
        v = vals.tolist() + [vals[0]]
        ax.plot(angles, v, "o-", linewidth=2, label=label, color=color)
        ax.fill(angles, v, alpha=0.15, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=10)
    ax.set_ylim(0, 1.15)
    ax.set_title("Experiment 5: Model Comparison Radar", fontsize=14, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

    plt.tight_layout()
    plt.savefig(RESULTS / "model_radar.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  -> model_radar.png")


# ── 메인 ──
if __name__ == "__main__":
    print("=" * 50)
    print("  Experiment 5: Generating Charts")
    print("=" * 50)

    models, grids = load_all()

    plot_model_comparison(models)
    plot_speed_comparison(models)
    plot_grid_distribution(grids)
    plot_radar(models)

    print("\nDone!")
