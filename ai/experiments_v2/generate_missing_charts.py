"""발표 누락 차트 2장 생성: 슬라이드 3 (클래스 분포) + 슬라이드 9 (시나리오 테스트)"""
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import json
from pathlib import Path

matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── 색상 팔레트 ──
COLORS = {
    'doc_generate': '#4CAF50',
    'doc_qa': '#2196F3',
    'doc_search': '#FF9800',
    'doc_summary': '#9C27B0',
    'general': '#607D8B',
    'judgment': '#F44336',
    'schedule_add': '#00BCD4',
    'schedule_view': '#795548',
}

CATEGORY_COLORS = {
    'normal': '#4CAF50',
    'boundary': '#FF9800',
    'short': '#F44336',
    'informal': '#2196F3',
}


def chart_class_distribution():
    """슬라이드 3: 8개 intent 클래스 분포 (train/val/test 스택 바)"""

    # 데이터 (탐색 결과 기반)
    intents = ['doc_generate', 'doc_qa', 'doc_search', 'doc_summary',
               'general', 'judgment', 'schedule_add', 'schedule_view']
    train = [290, 324, 326, 308, 265, 295, 264, 255]
    val =   [36,  40,  40,  38,  32,  36,  32,  31]
    test =  [36,  40,  40,  38,  33,  36,  32,  31]

    labels = [i.replace('_', '\n') for i in intents]
    x = np.arange(len(intents))
    width = 0.6

    fig, ax = plt.subplots(figsize=(12, 6))

    bars_train = ax.bar(x, train, width, label=f'Train (2,327)', color='#2196F3', alpha=0.85)
    bars_val = ax.bar(x, val, width, bottom=train, label=f'Val (285)', color='#FF9800', alpha=0.85)
    bars_test = ax.bar(x, test, width, bottom=[t+v for t,v in zip(train, val)],
                       label=f'Test (286)', color='#4CAF50', alpha=0.85)

    # 총 수 표시
    for i, (t, v, te) in enumerate(zip(train, val, test)):
        total = t + v + te
        ax.text(i, total + 5, str(total), ha='center', va='bottom', fontweight='bold', fontsize=10)

    ax.set_xlabel('Intent', fontsize=12, fontweight='bold')
    ax.set_ylabel('Samples', fontsize=12, fontweight='bold')
    ax.set_title('Intent Classification Dataset — Class Distribution\n'
                 '(GPT-4o + Claude Sonnet 4 생성, 총 2,898개)', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.legend(loc='upper right', fontsize=11)
    ax.set_ylim(0, max([t+v+te for t,v,te in zip(train,val,test)]) + 40)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3)

    # 균형도 주석
    ax.annotate('Max/Min ratio: 1.28x (균형 양호)',
                xy=(0.02, 0.95), xycoords='axes fraction',
                fontsize=10, color='#666', style='italic')

    plt.tight_layout()
    out = RESULTS_DIR / "class_distribution.png"
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ 슬라이드 3: {out}")


def chart_scenario_test():
    """슬라이드 9: 시나리오 테스트 유형별 정확도 바 차트"""

    categories = ['normal\n(표준)', 'boundary\n(경계)', 'informal\n(비속어)', 'short\n(초단문)', '전체']
    correct =    [7,   7,    6,     6,    26]
    total =      [7,   8,    7,     8,    30]
    accuracy =   [c/t*100 for c, t in zip(correct, total)]

    colors = ['#4CAF50', '#FF9800', '#2196F3', '#F44336', '#333333']

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(categories))
    width = 0.55

    bars = ax.bar(x, accuracy, width, color=colors, alpha=0.85, edgecolor='white', linewidth=1.5)

    # 수치 표시
    for i, (bar, c, t, acc) in enumerate(zip(bars, correct, total, accuracy)):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                f'{acc:.1f}%\n({c}/{t})', ha='center', va='bottom',
                fontweight='bold', fontsize=11)

    # threshold line
    ax.axhline(y=85, color='#999', linestyle='--', linewidth=1, alpha=0.7)
    ax.text(len(categories)-0.5, 86, 'clarify threshold (0.85)',
            ha='right', fontsize=9, color='#999', style='italic')

    ax.set_xlabel('입력 유형', fontsize=12, fontweight='bold')
    ax.set_ylabel('정확도 (%)', fontsize=12, fontweight='bold')
    ax.set_title('Stage 6 시나리오 테스트 — 유형별 정확도\n'
                 '(30문장 실제 라우팅 시뮬레이션, KoELECTRA + Label Smoothing)',
                 fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=10)
    ax.set_ylim(0, 115)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3)

    # 오분류 해결 주석
    ax.annotate('* 오분류 4건 모두 confidence < 0.85\n  -> clarify 라우팅으로 100% 커버',
                xy=(0.02, 0.02), xycoords='axes fraction',
                fontsize=9, color='#666', style='italic',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFF9C4', alpha=0.8))

    plt.tight_layout()
    out = RESULTS_DIR / "scenario_test_accuracy.png"
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ 슬라이드 9: {out}")


if __name__ == "__main__":
    print("=" * 50)
    print("발표 누락 차트 생성 시작")
    print("=" * 50)
    chart_class_distribution()
    chart_scenario_test()
    print("\n✅ 완료! 2장 생성됨 → ai/experiments_v2/results/")
