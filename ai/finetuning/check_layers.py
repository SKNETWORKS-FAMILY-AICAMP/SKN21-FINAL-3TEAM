"""EXAONE 모델 레이어 이름 확인 스크립트"""
from transformers import AutoModelForCausalLM

m = AutoModelForCausalLM.from_pretrained(
    "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct",
    trust_remote_code=True,
    device_map="cpu",
)
for n, _ in m.named_modules():
    if any(k in n for k in ["proj", "fc", "gate", "dense"]):
        print(n)
