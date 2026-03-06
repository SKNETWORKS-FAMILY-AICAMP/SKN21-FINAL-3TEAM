"""EXAONE 로딩 문제 진단 스크립트"""
import os
import sys
import traceback

os.environ["HF_HUB_TRUST_REMOTE_CODE"] = "1"
os.environ["TRUST_REMOTE_CODE"] = "True"

# Step 1: monkey-patch
print("=== Step 1: monkey-patch ===")
import transformers.utils.generic as _g
if not hasattr(_g, "check_model_inputs"):
    _g.check_model_inputs = lambda *a, **k: None
    print("  patched check_model_inputs")
if not hasattr(_g, "maybe_autocast"):
    from contextlib import nullcontext
    _g.maybe_autocast = nullcontext
    print("  patched maybe_autocast")

import transformers
print(f"  transformers: {transformers.__version__}")

# Step 2: config 로드
print("\n=== Step 2: config ===")
from transformers import AutoConfig
try:
    config = AutoConfig.from_pretrained(
        "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct",
        trust_remote_code=True,
    )
    print(f"  model_type: {config.model_type}")
    print(f"  architectures: {getattr(config, 'architectures', 'N/A')}")
    print(f"  auto_map: {getattr(config, 'auto_map', 'N/A')}")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# Step 3: custom code import 테스트
print("\n=== Step 3: custom code import ===")
import glob
files = glob.glob("/root/.cache/huggingface/**/modeling_exaone.py", recursive=True)
print(f"  found {len(files)} modeling files")
for f in files:
    print(f"    {f}")
    try:
        # 파일을 직접 import 시도
        import importlib.util
        spec = importlib.util.spec_from_file_location("modeling_exaone", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        print(f"    -> import OK")
        # 클래스 확인
        for name in dir(mod):
            if "Exaone" in name and "ForCausal" in name:
                print(f"    -> class found: {name}")
    except Exception as e:
        print(f"    -> IMPORT FAILED: {e}")
        traceback.print_exc()

# Step 4: 모델 로드 (CPU, 작은 메모리)
print("\n=== Step 4: model load (CPU) ===")
from transformers import AutoModelForCausalLM
import torch
try:
    model = AutoModelForCausalLM.from_pretrained(
        "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct",
        trust_remote_code=True,
        device_map="cpu",
        torch_dtype=torch.bfloat16,
    )
    print(f"  model type: {type(model).__name__}")
    print(f"  model class module: {type(model).__module__}")
    # 레이어 확인
    named = [n for n, _ in model.named_modules() if "proj" in n or "fc" in n]
    print(f"  layers with proj/fc: {len(named)}")
    if named:
        print(f"  first 5: {named[:5]}")
    # 파라미터 수
    total = sum(p.numel() for p in model.parameters())
    print(f"  total params: {total:,} ({total/1e9:.1f}B)")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# Step 5: GPU 로드
print("\n=== Step 5: model load (GPU, bf16) ===")
try:
    del model
    torch.cuda.empty_cache()
    model = AutoModelForCausalLM.from_pretrained(
        "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct",
        trust_remote_code=True,
        device_map="auto",
        torch_dtype=torch.bfloat16,
    )
    print(f"  model type: {type(model).__name__}")
    total = sum(p.numel() for p in model.parameters())
    print(f"  total params: {total:,} ({total/1e9:.1f}B)")
    vram = torch.cuda.memory_allocated() / 1e9
    print(f"  VRAM: {vram:.1f} GB")
    named = [n for n, _ in model.named_modules() if "proj" in n or "fc" in n]
    print(f"  layers with proj/fc: {len(named)}")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

print("\n=== Done ===")
