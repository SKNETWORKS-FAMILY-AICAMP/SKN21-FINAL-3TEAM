"""학습 결과 확인 스크립트
Usage: python ai/finetuning/check_results.py [model_name]
  예: python ai/finetuning/check_results.py Qwen3-8B
  예: python ai/finetuning/check_results.py  (전체 확인)
"""
import json
import sys
from pathlib import Path

BASE = Path("/workspace/SKN21-FINAL-3TEAM/outputs")

models = [sys.argv[1]] if len(sys.argv) > 1 else None

for task_dir in sorted(BASE.glob("v2_*")):
    task = task_dir.name
    for model_dir in sorted(task_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        if models and model_dir.name not in models:
            continue

        print(f"\n{'='*60}")
        print(f"  {task} / {model_dir.name}")
        print(f"{'='*60}")

        # 1. train_log.json
        log_file = model_dir / "train_log.json"
        if log_file.exists():
            log = json.loads(log_file.read_text())
            print(f"\n[학습 로그]")
            if isinstance(log, list):
                # trainer log_history 형식
                for entry in log[-3:]:  # 마지막 3개만
                    print(f"  {json.dumps({k: round(v,4) if isinstance(v,float) else v for k,v in entry.items()}, ensure_ascii=False)}")
            else:
                for k, v in log.items():
                    if isinstance(v, float):
                        print(f"  {k}: {v:.4f}")
                    else:
                        print(f"  {k}: {v}")
        else:
            print(f"\n[학습 로그] 없음")

        # 2. checkpoints
        ckpt_dir = model_dir / "checkpoints"
        if ckpt_dir.exists():
            ckpts = sorted(ckpt_dir.glob("checkpoint-*"))
            print(f"\n[체크포인트] {len(ckpts)}개")
            for c in ckpts:
                trainer_state = c / "trainer_state.json"
                if trainer_state.exists():
                    state = json.loads(trainer_state.read_text())
                    best = state.get("best_metric", "N/A")
                    epoch = state.get("epoch", "N/A")
                    print(f"  {c.name}: epoch={epoch}, best_eval_loss={best}")

        # 3. final adapter
        final_dir = model_dir / "final"
        if final_dir.exists():
            files = list(final_dir.iterdir())
            print(f"\n[Final 어댑터] {len(files)}개 파일")
            for f in sorted(files):
                size = f.stat().st_size / 1024 / 1024
                print(f"  {f.name}: {size:.1f}MB")
        else:
            print(f"\n[Final 어댑터] 없음")

        # 4. eval results
        eval_file = model_dir / "eval_results.json"
        if eval_file.exists():
            results = json.loads(eval_file.read_text())
            print(f"\n[평가 결과]")
            for k, v in results.items():
                if isinstance(v, float):
                    print(f"  {k}: {v:.4f}")
                elif isinstance(v, dict):
                    print(f"  {k}:")
                    for kk, vv in v.items():
                        if isinstance(vv, float):
                            print(f"    {kk}: {vv:.4f}")
                        else:
                            print(f"    {kk}: {vv}")
                else:
                    print(f"  {k}: {v}")
        else:
            print(f"\n[평가 결과] 없음")

if not any(BASE.glob("v2_*")):
    print("outputs 폴더가 비어있습니다.")
