"""EXAONE 모델 호환성 패치 스크립트
RunPod에서 실행: python ai/finetuning/fix_exaone.py
"""
import glob
import shutil
import sys

# 옵션: --clean 으로 캐시 완전 삭제 후 재다운로드
if "--clean" in sys.argv:
    for pattern in [
        "/root/.cache/huggingface/modules/transformers_modules/LGAI*",
        "/root/.cache/huggingface/hub/models--LGAI-EXAONE*",
    ]:
        for d in glob.glob(pattern):
            print(f"removing: {d}")
            shutil.rmtree(d, ignore_errors=True)
    print("cache cleaned. run training to re-download.")
    print("then run this script again WITHOUT --clean to patch.")
    sys.exit(0)

files = glob.glob("/root/.cache/huggingface/**/modeling_exaone.py", recursive=True)

if not files:
    print("modeling_exaone.py not found in cache. run training first to download the model.")
    sys.exit(1)

for p in files:
    t = open(p).read()
    changed = False

    # 1. check_model_inputs import 에러 수정
    old_import = "from transformers.utils.generic import check_model_inputs, maybe_autocast"
    new_import = (
        "try:\n"
        "    from transformers.utils.generic import check_model_inputs, maybe_autocast\n"
        "except ImportError:\n"
        "    check_model_inputs = lambda *a, **k: None\n"
        "    from contextlib import nullcontext as maybe_autocast"
    )
    if old_import in t:
        t = t.replace(old_import, new_import)
        changed = True
        print(f"  [fix] check_model_inputs import: {p}")

    # 2. ExaoneModel 에 get_input_embeddings 추가 (내부 transformer)
    anchor1 = "        self.wte = nn.Embedding(self.vocab_size, self.hidden_size, self.padding_idx)"
    patch1 = (
        "        self.wte = nn.Embedding(self.vocab_size, self.hidden_size, self.padding_idx)\n"
        "\n"
        "    def get_input_embeddings(self):\n"
        "        return self.wte\n"
        "\n"
        "    def set_input_embeddings(self, value):\n"
        "        self.wte = value"
    )
    if anchor1 in t and "def get_input_embeddings" not in t:
        t = t.replace(anchor1, patch1)
        changed = True
        print(f"  [fix] ExaoneModel get_input_embeddings: {p}")

    # 3. ExaoneForCausalLM 에 get_input_embeddings 추가 (최상위 모델)
    #    _tied_weights_keys 뒤에 삽입
    anchor2 = '    _tied_weights_keys = {"lm_head.weight": "transformer.wte.weight"}'
    patch2 = (
        '    _tied_weights_keys = {"lm_head.weight": "transformer.wte.weight"}\n'
        "\n"
        "    def get_input_embeddings(self):\n"
        "        return self.transformer.wte\n"
        "\n"
        "    def set_input_embeddings(self, value):\n"
        "        self.transformer.wte = value"
    )
    if anchor2 in t and t.count("def get_input_embeddings") < 2:
        t = t.replace(anchor2, patch2)
        changed = True
        print(f"  [fix] ExaoneForCausalLM get_input_embeddings: {p}")

    if changed:
        open(p, "w").write(t)
        print(f"  PATCHED: {p}")
    else:
        print(f"  already patched: {p}")

print("\ndone!")
