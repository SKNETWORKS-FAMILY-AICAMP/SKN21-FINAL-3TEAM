"""EXAONE modeling 코드 핵심 부분 출력"""
import glob

files = glob.glob("/root/.cache/huggingface/**/modeling_exaone.py", recursive=True)
p = files[0]
lines = open(p).readlines()

# 클래스 정의 + __init__ 부분만 출력
targets = ["class Exaone", "class ExaoneMLP", "class ExaoneAttention", "class ExaoneDecoder"]
for i, line in enumerate(lines):
    if any(t in line for t in targets):
        start = max(0, i)
        end = min(len(lines), i + 40)
        print(f"\n{'='*60}")
        print(f"Line {i+1}: {line.rstrip()}")
        print(f"{'='*60}")
        for j in range(start, end):
            print(f"{j+1:4d} | {lines[j].rstrip()}")
