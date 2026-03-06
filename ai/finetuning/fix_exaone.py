"""EXAONE 모델 호환성 패치 스크립트
RunPod에서 실행: python ai/finetuning/fix_exaone.py
"""
import glob

files = glob.glob("/root/.cache/huggingface/**/modeling_exaone.py", recursive=True)

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

    # 2. get_input_embeddings / set_input_embeddings 추가
    anchor = "        self.wte = nn.Embedding(self.vocab_size, self.hidden_size, self.padding_idx)"
    patch = (
        "        self.wte = nn.Embedding(self.vocab_size, self.hidden_size, self.padding_idx)\n"
        "\n"
        "    def get_input_embeddings(self):\n"
        "        return self.wte\n"
        "\n"
        "    def set_input_embeddings(self, value):\n"
        "        self.wte = value"
    )
    if "def get_input_embeddings" not in t:
        t = t.replace(anchor, patch)
        changed = True

    if changed:
        open(p, "w").write(t)
        print(f"patched: {p}")
    else:
        print(f"already patched: {p}")

print("done!")
