#!/usr/bin/env python3
"""QLoRA fine-tuning for English→Myanmar literary translation (cloud GPU).

Reads the ChatML JSONL produced by ``scripts/build_finetune_dataset.py`` and
trains a LoRA adapter, then exports it for Ollama. Heavy deps are imported lazily
so ``--dry-run`` works anywhere (incl. your RX 580 PC).

The Ollama ``padauk-gemma`` model is a LoRA adapter on ``unsloth/gemma-4-E4B-it``
(Gemma 3n E4B, ~8B), so our translation LoRA trains on that SAME base. Gemma 3n
is a non-standard architecture (MatFormer / per-layer embeddings) that plain
``AutoModelForCausalLM`` + bitsandbytes often won't load — so the DEFAULT and
recommended path here is **Unsloth** (``--use-unsloth``, on by default), which
has first-class Gemma-3n support, trains in less VRAM (fits a free 16 GB T4), and
exports GGUF directly. ``--no-unsloth`` falls back to the generic transformers/
trl path for standard Gemma-2 style bases.

Typical cloud run (after building the dataset):
    python scripts/train_lora_cloud.py \\
        --base-model unsloth/gemma-4-E4B-it \\
        --train data/finetune/train.jsonl \\
        --val   data/finetune/val.jsonl \\
        --out   models/adapters/en-my-lora \\
        --epochs 2

See docs/CLOUD_TRAINING.md for the full provider walkthrough + GGUF/Ollama export.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_chatml(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def dry_run(args) -> None:
    """Validate the dataset and print stats without importing torch."""
    train = load_chatml(args.train)
    val = load_chatml(args.val) if args.val and Path(args.val).exists() else []
    lens = []
    for r in train:
        msgs = r["messages"]
        assert [m["role"] for m in msgs] == ["system", "user", "assistant"], "bad ChatML"
        lens.append(len(msgs[1]["content"]) + len(msgs[2]["content"]))
    lens.sort()
    p50 = lens[len(lens) // 2] if lens else 0
    p95 = lens[int(len(lens) * 0.95)] if lens else 0
    print(f"train examples : {len(train)}")
    print(f"val examples   : {len(val)}")
    print(f"chars/example  : p50={p50}  p95={p95}  max={max(lens) if lens else 0}")
    print(f"base model     : {args.base_model}")
    print("Dry run OK — dataset is valid ChatML. Run on a GPU without --dry-run to train.")


_TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                   "gate_proj", "up_proj", "down_proj"]


def _build_unsloth(args):  # pragma: no cover - requires GPU + unsloth
    """Load + LoRA-wrap a Gemma-3n base with Unsloth (recommended for E4B)."""
    from unsloth import FastModel
    model, tokenizer = FastModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=args.max_seq_len,
        load_in_4bit=True,
        full_finetuning=False,
    )
    model = FastModel.get_peft_model(
        model,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.0,
        bias="none",
        target_modules=_TARGET_MODULES,
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )
    return model, tokenizer, None


def _build_transformers(args):  # pragma: no cover - requires GPU + heavy deps
    """Generic transformers/bitsandbytes load + PEFT LoRA config (Gemma-2 style)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model, quantization_config=bnb,
        device_map="auto", torch_dtype=torch.bfloat16,
    )
    model.config.use_cache = False
    peft_config = LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=0.05,
        bias="none", task_type="CAUSAL_LM", target_modules=_TARGET_MODULES,
    )
    return model, tokenizer, peft_config


def train(args) -> None:  # pragma: no cover - requires GPU + heavy deps
    from datasets import Dataset
    from trl import SFTTrainer, SFTConfig

    if args.use_unsloth:
        model, tokenizer, peft_config = _build_unsloth(args)
    else:
        model, tokenizer, peft_config = _build_transformers(args)

    def to_text(rec):
        # Apply the model's chat template so special tokens match inference.
        return {"text": tokenizer.apply_chat_template(
            rec["messages"], tokenize=False, add_generation_prompt=False)}

    train_ds = Dataset.from_list([to_text(r) for r in load_chatml(args.train)])
    eval_ds = None
    if args.val and Path(args.val).exists():
        eval_ds = Dataset.from_list([to_text(r) for r in load_chatml(args.val)])

    sft_config = SFTConfig(
        output_dir=args.out,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=20,
        save_strategy="epoch",
        eval_strategy="epoch" if eval_ds is not None else "no",
        bf16=True,
        max_length=args.max_seq_len,
        packing=False,
        # Unsloth handles gradient checkpointing internally (set in get_peft_model);
        # enabling it again here would double-wrap and error.
        gradient_checkpointing=not args.use_unsloth,
        optim="paged_adamw_8bit",
        report_to="none",
        dataset_text_field="text",
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        peft_config=peft_config,  # None under Unsloth (model is already PEFT-wrapped)
        processing_class=tokenizer,
    )
    trainer.train()
    trainer.save_model(args.out)
    tokenizer.save_pretrained(args.out)
    print(f"LoRA adapter saved to {args.out}")

    if args.use_unsloth and args.gguf:
        # Unsloth exports a merged, quantized GGUF in one step — ready for Ollama.
        print(f"Exporting merged GGUF ({args.gguf}) ...")
        model.save_pretrained_gguf(args.out, tokenizer, quantization_method=args.gguf)
        print(f"GGUF written under {args.out}. Next: `ollama create` "
              "(see docs/CLOUD_TRAINING.md).")
    else:
        print("Next: merge + convert to GGUF, then `ollama create` "
              "(see docs/CLOUD_TRAINING.md).")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-model", default="unsloth/gemma-4-E4B-it",
                    help="HF base model — the base padauk-gemma sits on (NOT the Ollama GGUF)")
    ap.add_argument("--train", default="data/finetune/train.jsonl")
    ap.add_argument("--val", default="data/finetune/val.jsonl")
    ap.add_argument("--out", default="models/adapters/en-my-lora")
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--max-seq-len", type=int, default=1536)
    ap.add_argument("--no-unsloth", dest="use_unsloth", action="store_false",
                    help="Use generic transformers/bitsandbytes instead of Unsloth "
                         "(only for standard Gemma-2 style bases; Gemma-3n needs Unsloth)")
    ap.set_defaults(use_unsloth=True)
    ap.add_argument("--gguf", default="q4_k_m",
                    help="Unsloth GGUF quant to export after training (e.g. q4_k_m, "
                         "q8_0); empty string to skip")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate dataset + print stats without importing torch")
    args = ap.parse_args()

    if not Path(args.train).exists():
        print(f"Train file not found: {args.train}\n"
              "Run scripts/build_finetune_dataset.py first.", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        dry_run(args)
    else:
        train(args)


if __name__ == "__main__":
    main()
