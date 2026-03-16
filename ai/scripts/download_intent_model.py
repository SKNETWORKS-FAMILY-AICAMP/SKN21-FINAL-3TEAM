"""
HuggingFace Hub에서 Intent 앙상블 모델 다운로드 (EC2 배포용)

사용법:
  export HF_TOKEN=hf_xxxxx
  python -m ai.scripts.download_intent_model

다운로드 위치: ai/models/intent_multilabel_ensemble/
"""

from huggingface_hub import snapshot_download
from pathlib import Path

REPO_ID = "jiyouxg/dudu-intent-ensemble"
LOCAL_DIR = Path(__file__).resolve().parent.parent / "models" / "intent_multilabel_ensemble"


def main():
    print(f"Downloading intent ensemble from {REPO_ID}...")
    snapshot_download(
        repo_id=REPO_ID,
        local_dir=str(LOCAL_DIR),
        repo_type="model",
    )
    print(f"Done! Models saved to {LOCAL_DIR}")

    # 확인
    seeds = [d.name for d in LOCAL_DIR.iterdir() if d.is_dir() and d.name.startswith("seed_")]
    print(f"Loaded seeds: {seeds}")


if __name__ == "__main__":
    main()
