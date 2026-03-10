"""
LoRA v2: 문서 Agent 기능별 파인튜닝 (어댑터 분리 전략)

어댑터 3종:
  - v2_generate: 문서 생성 (회의록/보고서/제안서 JSON) — 1,500개 (train 1,350 / eval 150)
  - v2_qa: 문서 QA (answer + citations JSON) — 1,000개 (train 900 / eval 100)
  - v2_summary: 문서 요약 (마크다운) — 1,000개 (train 900 / eval 100)

베이스 모델: Qwen3-8B (1차 추천) — 비교 대상: EXAONE-3.5-7.8B, Kanana-1.5-8B

사용법:
    # 기능별 학습 (--task 필수)
    python ai/finetuning/train_v2_document.py --task generate --mode train
    python ai/finetuning/train_v2_document.py --task qa --mode train
    python ai/finetuning/train_v2_document.py --task summary --mode train

    # 기능별 평가
    python ai/finetuning/train_v2_document.py --task generate --mode eval --adapter_path outputs/v2_generate/Qwen3-8B/final

    # 학습 + 평가
    python ai/finetuning/train_v2_document.py --task generate --mode all

    # 3개 모델 비교 (기능별)
    python ai/finetuning/train_v2_document.py --task generate --mode compare

    # 다른 베이스 모델 지정
    python ai/finetuning/train_v2_document.py --task qa --mode all --base_model LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct

    # 전체 기능 일괄 학습
    python ai/finetuning/train_v2_document.py --task all --mode all

환경:
    pip install transformers peft trl bitsandbytes accelerate datasets torch pyyaml rouge-score bert-score
    GPU: RTX 5090 32GB (또는 RunPod A100 40GB)
"""

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

# EXAONE 등 커스텀 모델 코드 자동 승인 (y/N 프롬프트 제거)
os.environ["HF_HUB_TRUST_REMOTE_CODE"] = "1"
os.environ["TRUST_REMOTE_CODE"] = "True"

# EXAONE 호환성: transformers 5.x에서 제거된 함수를 미리 주입
# → EXAONE의 custom modeling 코드가 import할 때 에러 방지
import transformers.utils.generic as _trf_generic
if not hasattr(_trf_generic, "check_model_inputs"):
    _trf_generic.check_model_inputs = lambda func: func  # identity decorator
if not hasattr(_trf_generic, "maybe_autocast"):
    from contextlib import nullcontext
    _trf_generic.maybe_autocast = nullcontext

import torch
import yaml
from datasets import Dataset
from peft import LoraConfig, PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    EarlyStoppingCallback,
)
from trl import SFTConfig, SFTTrainer

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIGS_DIR = Path(__file__).resolve().parent / "configs"

# 태스크 → config 파일 매핑
TASK_CONFIGS = {
    "generate": CONFIGS_DIR / "v2_generate.yaml",
    "qa": CONFIGS_DIR / "v2_qa.yaml",
    "summary": CONFIGS_DIR / "v2_summary.yaml",
}

# doc_generate: 템플릿별 JSON 필수 필드
REQUIRED_FIELDS = {
    "meeting_minutes": ["title", "date", "attendees", "summary", "decisions", "action_items"],
    "report": ["title", "author", "date", "department", "report_type", "overview", "main_content", "tasks"],
    "proposal": [
        "title", "submit_date", "submit_to", "company", "manager",
        "proposal_name", "background", "purpose", "content", "schedule", "budget",
    ],
}

# doc_qa 필수 필드
QA_REQUIRED_FIELDS = ["answer", "citations"]


# ── 설정 로드 ──


def load_config(config_path: Path) -> dict:
    """YAML 설정 파일 로드"""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_output_base(task: str) -> Path:
    """태스크별 output 디렉토리"""
    output_base = BASE_DIR / "outputs" / f"v2_{task}"
    output_base.mkdir(parents=True, exist_ok=True)
    return output_base


# ── 데이터 로드 ──


def load_jsonl(path: str | Path) -> list[dict]:
    """JSONL 파일 로드"""
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def detect_task_type(sample: dict) -> str:
    """messages의 시스템 프롬프트에서 태스크 타입 감지"""
    messages = sample.get("messages", [])
    if not messages:
        return "unknown"

    sys_content = ""
    for msg in messages:
        if msg.get("role") == "system":
            sys_content = msg.get("content", "").lower()
            break

    if "문서 작성" in sys_content or "회의록" in sys_content or "보고서" in sys_content or "제안서" in sys_content:
        return "doc_generate"
    if "질의응답" in sys_content or "qa" in sys_content or "인용" in sys_content:
        return "doc_qa"
    if "요약" in sys_content or "summary" in sys_content:
        return "doc_summary"
    return "unknown"


def format_chat_sample(tokenizer, sample: dict) -> str:
    """messages 배열 → chat template 텍스트 변환"""
    messages = sample["messages"]
    try:
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
    except Exception:
        # fallback: 수동 포맷
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                parts.append(f"<|im_start|>system\n{content}<|im_end|>")
            elif role == "user":
                parts.append(f"<|im_start|>user\n{content}<|im_end|>")
            elif role == "assistant":
                parts.append(f"<|im_start|>assistant\n{content}<|im_end|>")
        return "\n".join(parts)


def load_train_eval_datasets(
    tokenizer, config: dict
) -> tuple[Dataset, Dataset]:
    """train/eval JSONL → Dataset 변환"""
    train_path = BASE_DIR / config["data"]["train_path"]
    eval_path = BASE_DIR / config["data"]["eval_path"]

    train_samples = load_jsonl(train_path)
    eval_samples = load_jsonl(eval_path)

    # 태스크 분포 확인
    task_counter = Counter(detect_task_type(s) for s in train_samples)
    print(f"  Train 태스크 분포: {dict(task_counter)}")

    train_texts = [{"text": format_chat_sample(tokenizer, s)} for s in train_samples]
    eval_texts = [{"text": format_chat_sample(tokenizer, s)} for s in eval_samples]

    train_dataset = Dataset.from_list(train_texts)
    eval_dataset = Dataset.from_list(eval_texts)

    print(f"  Train: {len(train_dataset)}건 / Eval: {len(eval_dataset)}건")
    return train_dataset, eval_dataset


# ── 모델 로드 ──


def load_base_model(config: dict, for_training: bool = True, base_model_override: str = None):
    """QLoRA 4-bit 모델 로드 (EXAONE은 bf16 풀로드)"""
    model_id = base_model_override or config["model"]["base_model"]
    is_exaone = "exaone" in model_id.lower()
    print(f"  모델: {model_id}")

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    if is_exaone:
        # EXAONE: 커스텀 아키텍처라 bitsandbytes 4-bit 양자화 비호환
        # H200 80GB VRAM이면 bf16 풀로드 + LoRA 충분
        print(f"  [EXAONE] bf16 풀로드 (4-bit 양자화 비호환)")
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )
        # EXAONE: get_input_embeddings 패치 (peft가 양쪽 클래스에서 호출함)
        outer_cls = type(model)
        outer_cls.get_input_embeddings = lambda self: self.transformer.wte
        outer_cls.set_input_embeddings = lambda self, v: setattr(self.transformer, "wte", v)
        inner_cls = type(model.transformer)
        inner_cls.get_input_embeddings = lambda self: self.wte
        inner_cls.set_input_embeddings = lambda self, v: setattr(self, "wte", v)
        print(f"  [EXAONE] get_input_embeddings 패치 완료 (outer + inner)")
    else:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )

    if for_training:
        model.config.use_cache = False
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
        else:
            model.get_input_embeddings().register_forward_hook(
                lambda module, args, output: output.requires_grad_(True)
            )

    vram_gb = torch.cuda.memory_allocated() / 1e9
    print(f"  VRAM - Allocated: {vram_gb:.1f} GB")
    return tokenizer, model


# ── 학습 ──


def train(task: str, config: dict, base_model_override: str = None):
    """기능별 LoRA 학습"""
    model_id = base_model_override or config["model"]["base_model"]
    model_short = model_id.split("/")[-1]
    output_base = get_output_base(task)

    print(f"\n{'=' * 60}")
    print(f"  LoRA v2_{task} 학습 시작: {model_short}")
    print(f"{'=' * 60}")

    print("\n[1/4] 모델 로드 중...")
    tokenizer, model = load_base_model(config, for_training=True, base_model_override=base_model_override)

    print("\n[2/4] 데이터 준비 중...")
    train_dataset, eval_dataset = load_train_eval_datasets(tokenizer, config)

    use_bf16 = torch.cuda.is_bf16_supported()
    print(f"  bf16 지원: {use_bf16}")

    lora_cfg = config["lora"]
    target_modules = lora_cfg["target_modules"]

    # EXAONE 모델은 레이어 이름이 다름 — 자동 변환
    if "exaone" in model_id.lower():
        exaone_map = {"o_proj": "out_proj", "gate_proj": "c_fc_0", "up_proj": "c_fc_1"}
        target_modules = [exaone_map.get(t, t) for t in target_modules]
        print(f"  [EXAONE] target_modules 변환: {lora_cfg['target_modules']} -> {target_modules}")

    lora_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        target_modules=target_modules,
        lora_dropout=lora_cfg["lora_dropout"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    print(f"  LoRA: r={lora_cfg['r']}, alpha={lora_cfg['lora_alpha']}, "
          f"targets={target_modules}")

    train_cfg = config["training"]

    # 모델별 output_dir 분리 (비교 테스트)
    output_dir = str(output_base / model_short / "checkpoints")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Early stopping
    early_stopping_patience = config["training"].get("early_stopping_patience", 3)
    callbacks = [EarlyStoppingCallback(early_stopping_patience=early_stopping_patience)]

    training_args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=train_cfg["num_epochs"],
        per_device_train_batch_size=train_cfg["batch_size"],
        gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
        learning_rate=float(train_cfg["learning_rate"]),
        lr_scheduler_type="cosine",
        warmup_steps=max(1, int(len(train_dataset) / train_cfg["batch_size"] / train_cfg["gradient_accumulation_steps"] * train_cfg["warmup_ratio"])),
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=use_bf16,
        fp16=not use_bf16,
        gradient_checkpointing=True,
        optim="adamw_torch" if "exaone" in model_id.lower() else "paged_adamw_8bit",
        report_to="none",
        max_length=train_cfg["max_length"],
    )

    # trl 버전에 따라 dataset_text_field 위치가 다름
    try:
        training_args.dataset_text_field = "text"
    except Exception:
        pass

    print(f"\n[3/4] 학습 시작 (epochs={train_cfg['num_epochs']}, "
          f"early_stopping={early_stopping_patience})...")
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        peft_config=lora_config,
        callbacks=callbacks,
    )

    trainer.train()

    print("\n[4/4] 어댑터 저장 중...")
    final_path = output_base / model_short / "final"
    final_path.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(final_path))
    tokenizer.save_pretrained(str(final_path))
    print(f"  저장 완료: {final_path}")

    # 학습 로그 저장
    log_history = trainer.state.log_history
    log_path = output_base / model_short / "train_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_history, f, indent=2)
    print(f"  학습 로그: {log_path}")


# ── 평가 ──


def parse_json_from_text(text: str) -> dict | None:
    """텍스트에서 JSON 추출"""
    text = text.strip()
    # ```json ... ``` 블록
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    # 첫 { ... } 블록
    if not text.startswith("{"):
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def compute_token_f1(prediction: str, reference: str) -> float:
    """토큰 단위 F1 스코어"""
    pred_tokens = set(prediction.split())
    ref_tokens = set(reference.split())
    if not pred_tokens or not ref_tokens:
        return 0.0
    common = pred_tokens & ref_tokens
    precision = len(common) / len(pred_tokens) if pred_tokens else 0
    recall = len(common) / len(ref_tokens) if ref_tokens else 0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate(task: str, config: dict, adapter_path: str, base_model_override: str = None):
    """기능별 평가"""
    model_id = base_model_override or config["model"]["base_model"]
    model_short = model_id.split("/")[-1]
    output_base = get_output_base(task)

    print(f"\n{'=' * 60}")
    print(f"  LoRA v2_{task} 평가: {model_short}")
    print(f"{'=' * 60}")
    print(f"  어댑터 로드: {adapter_path}")

    tokenizer, base_model = load_base_model(config, for_training=False, base_model_override=base_model_override)
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.eval()
    torch.cuda.empty_cache()

    eval_path = BASE_DIR / config["data"]["eval_path"]
    eval_samples = load_jsonl(eval_path)
    print(f"  평가 시작: {len(eval_samples)}건")

    # 통계
    stats = {
        "total": 0, "json_valid": 0, "field_complete": 0, "field_accurate": 0,
        "token_f1_sum": 0.0, "rouge_l_sum": 0.0, "citation_correct": 0,
        "format_ok": 0, "predictions": [],
    }

    for i, sample in enumerate(eval_samples, 1):
        messages = sample["messages"]
        gold_text = messages[-1]["content"]  # assistant 응답
        stats["total"] += 1

        # 추론 (system + user만 전달)
        infer_messages = [m for m in messages if m["role"] != "assistant"]
        try:
            prompt = tokenizer.apply_chat_template(
                infer_messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            prompt = "\n".join(
                f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>"
                for m in infer_messages
            ) + "\n<|im_start|>assistant\n"

        max_len = config["training"].get("max_length", 2560)
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_len).to(model.device)
        input_len = inputs["input_ids"].shape[1]

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=1024,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )

        pred_text = tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True).strip()

        # ── 태스크별 평가 ──
        if task == "generate":
            _eval_doc_generate(stats, pred_text, gold_text, sample)
        elif task == "qa":
            _eval_doc_qa(stats, pred_text, gold_text)
        elif task == "summary":
            _eval_doc_summary(stats, pred_text, gold_text)

        # 예측 저장 (처음 5개만)
        if len(stats["predictions"]) < 5:
            stats["predictions"].append({
                "gold": gold_text[:300],
                "pred": pred_text[:300],
            })

        if i % 20 == 0 or i <= 3:
            print(f"  [{i:03d}/{len(eval_samples)}]")

    # ── 결과 출력 ──
    total = stats["total"]
    print(f"\n{'=' * 60}")
    print(f"  LoRA v2_{task} 평가 결과 ({model_short}) — {total}건")
    print(f"{'=' * 60}")

    eval_results = {"model": model_id, "task": f"v2_{task}", "total": total}

    if task == "generate":
        json_rate = stats["json_valid"] / total if total else 0
        field_complete = stats["field_complete"] / total if total else 0
        field_accurate = stats["field_accurate"] / max(stats["json_valid"], 1)
        print(f"    JSON 유효율:    {stats['json_valid']}/{total} ({json_rate*100:.1f}%)")
        print(f"    필드 완전성:    {stats['field_complete']}/{total} ({field_complete*100:.1f}%)")
        print(f"    필드명 정확도:  {stats['field_accurate']}/{stats['json_valid']} ({field_accurate*100:.1f}%)")
        eval_results.update({
            "json_valid_rate": round(json_rate, 4),
            "field_completeness": round(field_complete, 4),
            "field_accuracy": round(field_accurate, 4),
        })

    elif task == "qa":
        json_rate = stats["json_valid"] / total if total else 0
        avg_f1 = stats["token_f1_sum"] / max(stats["json_valid"], 1)
        citation_acc = stats["citation_correct"] / max(stats["json_valid"], 1)
        print(f"    JSON 유효율:    {stats['json_valid']}/{total} ({json_rate*100:.1f}%)")
        print(f"    Token F1:       {avg_f1:.4f}")
        print(f"    인용 정확도:    {stats['citation_correct']}/{stats['json_valid']} ({citation_acc*100:.1f}%)")
        eval_results.update({
            "json_valid_rate": round(json_rate, 4),
            "token_f1": round(avg_f1, 4),
            "citation_accuracy": round(citation_acc, 4),
        })

    elif task == "summary":
        format_rate = stats["format_ok"] / total if total else 0
        avg_rouge = stats["rouge_l_sum"] / total if total else 0
        tag_count_rate = stats.get("tag_count_ok", 0) / total if total else 0
        avg_tags = stats.get("tag_count_sum", 0) / total if total else 0
        print(f"    포맷 준수율:    {stats['format_ok']}/{total} ({format_rate*100:.1f}%)")
        print(f"    태그수 준수율:  {stats.get('tag_count_ok', 0)}/{total} ({tag_count_rate*100:.1f}%)")
        print(f"    평균 태그 수:   {avg_tags:.1f}")
        print(f"    ROUGE-L:        {avg_rouge:.4f}")
        eval_results.update({
            "format_compliance": round(format_rate, 4),
            "tag_count_compliance": round(tag_count_rate, 4),
            "avg_tag_count": round(avg_tags, 1),
            "rouge_l": round(avg_rouge, 4),
        })

    print(f"\n{'=' * 60}")

    # 결과 저장
    result_path = output_base / model_short / "eval_results.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(eval_results, f, ensure_ascii=False, indent=2)
    print(f"  결과 저장: {result_path}")

    return eval_results


def _parse_field_spec_from_user(user_content: str) -> list[str]:
    """user prompt의 [필드 명세]에서 필드 이름 목록 추출"""
    fields = []
    in_spec = False
    for line in user_content.splitlines():
        stripped = line.strip()
        if "[필드 명세]" in stripped:
            in_spec = True
            continue
        if in_spec:
            if stripped.startswith("[") and "필드" not in stripped:
                break
            if stripped.startswith("- ") and ":" in stripped:
                field_name = stripped[2:].split(":")[0].strip()
                if field_name:
                    fields.append(field_name)
    return fields


def _eval_doc_generate(st: dict, pred_text: str, gold_text: str, sample: dict):
    """doc_generate 평가 (동적 필드 명세 기반)"""
    pred_json = parse_json_from_text(pred_text)
    if pred_json is None:
        return

    st["json_valid"] += 1

    # user prompt에서 동적 필드 명세 추출
    user_content = ""
    for msg in sample.get("messages", []):
        if msg.get("role") == "user":
            user_content = msg.get("content", "")
            break

    expected_fields = _parse_field_spec_from_user(user_content)
    present_fields = set(pred_json.keys())

    if expected_fields:
        # 필드 완전성: 명세의 모든 필드가 존재?
        if all(f in present_fields for f in expected_fields):
            st["field_complete"] += 1

        # 필드명 정확도: 명세 필드와 정확히 일치?
        expected_set = set(expected_fields)
        if expected_set == present_fields or expected_set.issubset(present_fields):
            st["field_accurate"] += 1
    else:
        # 필드 명세 파싱 실패 시 gold JSON 기준 fallback
        gold_json = parse_json_from_text(gold_text)
        if gold_json:
            gold_keys = set(gold_json.keys())
            if gold_keys and gold_keys.issubset(present_fields):
                st["field_complete"] += 1
                st["field_accurate"] += 1


def _eval_doc_qa(st: dict, pred_text: str, gold_text: str):
    """doc_qa 평가"""
    pred_json = parse_json_from_text(pred_text)
    if pred_json is None:
        return

    st["json_valid"] += 1

    # Token F1 (answer 필드)
    pred_answer = pred_json.get("answer", "")
    gold_json = parse_json_from_text(gold_text)
    gold_answer = gold_json.get("answer", gold_text) if gold_json else gold_text
    f1 = compute_token_f1(pred_answer, gold_answer)
    st["token_f1_sum"] += f1

    # 인용 정확도: citations 존재 여부
    citations = pred_json.get("citations", [])
    if isinstance(citations, list) and len(citations) > 0:
        st["citation_correct"] += 1


def _eval_doc_summary(st: dict, pred_text: str, gold_text: str):
    """doc_summary 평가 — 태그+요약 형식

    기대 형식:
        태그: #태그1 #태그2 #태그3
        요약: 2~3문장 요약 텍스트
    """
    # 포맷 준수: 태그+요약 구조 체크
    lines = pred_text.strip().split("\n")
    has_tag = any(line.strip().startswith("태그:") for line in lines)
    has_summary = any(line.strip().startswith("요약:") for line in lines)

    # 태그 개수 체크 (3~7개)
    tag_count = 0
    for line in lines:
        if line.strip().startswith("태그:"):
            tag_count = line.count("#")
            break

    tag_count_ok = 3 <= tag_count <= 7
    format_ok = has_tag and has_summary and tag_count_ok

    if format_ok:
        st["format_ok"] += 1

    # 태그 개수 통계 (별도 집계)
    if "tag_count_ok" not in st:
        st["tag_count_ok"] = 0
        st["tag_count_sum"] = 0
    if tag_count_ok:
        st["tag_count_ok"] += 1
    st["tag_count_sum"] += tag_count

    # ROUGE-L (간이 구현 — LCS 기반)
    rouge_l = _compute_rouge_l(pred_text, gold_text)
    st["rouge_l_sum"] += rouge_l


def _compute_rouge_l(prediction: str, reference: str) -> float:
    """ROUGE-L (LCS 기반) 간이 구현"""
    pred_tokens = prediction.split()
    ref_tokens = reference.split()
    if not pred_tokens or not ref_tokens:
        return 0.0

    # LCS 길이 계산
    m, n = len(pred_tokens), len(ref_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if pred_tokens[i - 1] == ref_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs_len = dp[m][n]

    precision = lcs_len / m if m > 0 else 0
    recall = lcs_len / n if n > 0 else 0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ── 모델 비교 ──


def compare_models(task: str, config: dict):
    """3개 모델 비교 학습 + 평가 (기능별)"""
    output_base = get_output_base(task)
    candidates = config.get("model_candidates", [config["model"]["base_model"]])
    all_results = {}

    for model_id in candidates:
        model_short = model_id.split("/")[-1]
        print(f"\n{'#' * 60}")
        print(f"  v2_{task} 모델 비교: {model_short}")
        print(f"{'#' * 60}")

        # 학습
        train(task, config, base_model_override=model_id)

        # 평가
        adapter_path = str(output_base / model_short / "final")
        results = evaluate(task, config, adapter_path, base_model_override=model_id)
        all_results[model_short] = results

    # 비교 요약
    print(f"\n{'=' * 60}")
    print(f"  v2_{task} 모델 비교 요약")
    print(f"{'=' * 60}")

    comparison_path = output_base / "model_comparison.json"
    with open(comparison_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"  비교 결과 저장: {comparison_path}")

    for model_name, results in all_results.items():
        metrics_str = ", ".join(
            f"{k}={v}" for k, v in results.items()
            if k not in ("model", "task", "total", "predictions")
        )
        print(f"\n  [{model_name}] {metrics_str}")


# ── 엔트리포인트 ──


TASK_CHOICES = ["generate", "qa", "summary", "all"]


def run_single_task(task: str, mode: str, args):
    """단일 태스크 실행"""
    config_path = TASK_CONFIGS[task]
    config = load_config(config_path)
    model_id = args.base_model or config["model"]["base_model"]
    model_short = model_id.split("/")[-1]
    output_base = get_output_base(task)

    print(f"\n{'#' * 60}")
    print(f"  태스크: v2_{task}")
    print(f"  설정: {config_path}")
    print(f"  base_model: {model_id}")
    print(f"  LoRA r={config['lora']['r']}, alpha={config['lora']['lora_alpha']}")
    print(f"  targets={config['lora']['target_modules']}")
    print(f"  epochs={config['training']['num_epochs']}, "
          f"batch={config['training']['batch_size']}, "
          f"lr={config['training']['learning_rate']}")
    print(f"{'#' * 60}")

    if mode == "compare":
        compare_models(task, config)
        return

    if mode in ("train", "all"):
        train(task, config, base_model_override=args.base_model)

    if mode in ("eval", "all"):
        adapter_path = args.adapter_path or str(output_base / model_short / "final")
        evaluate(task, config, adapter_path, base_model_override=args.base_model)


def main():
    parser = argparse.ArgumentParser(description="문서 Agent LoRA v2 기능별 파인튜닝")
    parser.add_argument("--task", choices=TASK_CHOICES, required=True,
                        help="generate: 문서생성 / qa: 문서QA / summary: 문서요약 / all: 전체")
    parser.add_argument("--mode", choices=["train", "eval", "all", "compare"], default="all",
                        help="train: 학습만 / eval: 평가만 / all: 학습+평가 / compare: 3개 모델 비교")
    parser.add_argument("--adapter_path", default=None, help="eval 모드 시 어댑터 경로")
    parser.add_argument("--base_model", default=None, help="베이스 모델 오버라이드")
    args = parser.parse_args()

    if args.task == "all":
        # 전체 기능 순차 실행
        for task in ["generate", "qa", "summary"]:
            run_single_task(task, args.mode, args)
    else:
        run_single_task(args.task, args.mode, args)


if __name__ == "__main__":
    main()
