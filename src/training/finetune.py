"""
Fine-tuning scaffold for padauk-gemma using PEFT/LoRA.

Trains on human-rated translation pairs from the dataset DB.
Saves adapter weights to models/adapters/{name}/.

Usage:
    python -m src.main --finetune --novel outside-of-time [--adapter my_adapter]

Dependencies (optional, only loaded when --finetune is used):
    torch, transformers, peft, datasets, bitsandbytes
"""

import json
import logging
import sqlite3
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SETTINGS_PATH = Path("config/settings.yaml")
DATASET_DB = Path("data/novel_v1_dataset.db")
ADAPTER_DIR = Path("models/adapters")


def _load_config() -> dict:
    """Load LoRA training configuration from the single settings.yaml file.

    The LoRA hyperparameters live under the `lora_training:` section (formerly
    the separate src/training/config_lora.yaml).
    """
    if not SETTINGS_PATH.exists():
        logger.warning("Settings file not found at %s", SETTINGS_PATH)
        return {}
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        logger.warning("Could not read LoRA config from %s: %s", SETTINGS_PATH, e)
        return {}
    return settings.get("lora_training", {})


def _load_dataset(novel: Optional[str] = None, min_human_score: int = 3,
                  min_auto_score: int = 4) -> List[Dict[str, str]]:
    """Load training pairs from dataset DB.

    Prefers human-scored pairs; falls back to auto-scored.
    Returns empty list on any error.
    """
    if not DATASET_DB.exists():
        logger.error(f"Dataset DB not found at {DATASET_DB}")
        return []

    try:
        conn = sqlite3.connect(str(DATASET_DB))
    except sqlite3.Error as e:
        logger.error(f"Failed to connect to dataset DB: {e}")
        return []

    conn.row_factory = sqlite3.Row

    try:
        # Verify the table exists
        try:
            conn.execute("SELECT COUNT(*) FROM translation_pairs").fetchone()
        except sqlite3.OperationalError as e:
            logger.error(f"translation_pairs table missing or corrupt: {e}")
            return []

        def _fetch(sql: str, params: tuple) -> list:
            try:
                return conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError as e:
                logger.warning(f"SQL query failed (missing column?): {e}")
                return []

        # Prefer human-scored pairs
        if novel:
            rows = _fetch(
                "SELECT en_text, my_text, human_score, auto_score "
                "FROM translation_pairs "
                "WHERE (human_score IS NOT NULL AND human_score >= ?) "
                "AND novel_slug = ? ORDER BY RANDOM()",
                (min_human_score, novel),
            )
        else:
            rows = _fetch(
                "SELECT en_text, my_text, human_score, auto_score "
                "FROM translation_pairs "
                "WHERE (human_score IS NOT NULL AND human_score >= ?) "
                "ORDER BY RANDOM()",
                (min_human_score,),
            )

        if not rows:
            # Fallback to auto-scored pairs
            if novel:
                rows = _fetch(
                    "SELECT en_text, my_text, human_score, auto_score "
                    "FROM translation_pairs "
                    "WHERE auto_score >= ? AND novel_slug = ? ORDER BY RANDOM()",
                    (min_auto_score, novel),
                )
            else:
                rows = _fetch(
                    "SELECT en_text, my_text, human_score, auto_score "
                    "FROM translation_pairs "
                    "WHERE auto_score >= ? ORDER BY RANDOM()",
                    (min_auto_score,),
                )

        pairs = []
        for r in rows:
            pairs.append({
                "source": r["en_text"],
                "target": r["my_text"],
                "score": r["human_score"] if r["human_score"] is not None else r["auto_score"],
            })
        return pairs

    finally:
        conn.close()


def _prepare_dataset(pairs: List[Dict[str, str]], val_split: float = 0.1,
                     test_split: float = 0.1) -> Tuple:
    """Split pairs into train/val/test and format for HuggingFace."""
    from datasets import Dataset, DatasetDict

    if not pairs:
        logger.warning("_prepare_dataset called with empty pairs list")
        empty = Dataset.from_dict({"source": [], "target": []})
        return DatasetDict({"train": empty, "val": empty, "test": empty})

    total = len(pairs)
    test_count = int(total * test_split)
    val_count = int(total * val_split)
    train_count = total - test_count - val_count

    train = pairs[:train_count]
    val = pairs[train_count:train_count + val_count]
    test = pairs[train_count + val_count:]

    def _to_dict(ps):
        return {"source": [p["source"] for p in ps],
                "target": [p["target"] for p in ps]}

    return DatasetDict({
        "train": Dataset.from_dict(_to_dict(train)),
        "val": Dataset.from_dict(_to_dict(val)),
        "test": Dataset.from_dict(_to_dict(test)),
    })


def run_finetuning(novel: Optional[str] = None,
                   adapter_name: Optional[str] = None) -> int:
    """Run LoRA fine-tuning on the dataset.

    Args:
        novel: Optional novel slug to filter by
        adapter_name: Name for the saved adapter (default: auto-generated)

    Returns:
        0 on success, 1 on error, 2 if dependencies missing
    """
    # ── Lazy imports for heavy ML deps ──
    try:
        import torch
        from transformers import (
            AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer,
            BitsAndBytesConfig,
        )
        from peft import LoraConfig, get_peft_model
    except ImportError as e:
        logger.error(
            f"Missing ML dependency: {e}. "
            f"Install with: pip install torch transformers peft datasets bitsandbytes"
        )
        return 2

    config = _load_config()
    if not config:
        logger.error("Failed to load LoRA config")
        return 1

    lora_cfg = config.get("lora", {})
    train_cfg = config.get("training", {})
    ds_cfg = config.get("dataset", {})

    # ── Load dataset ──
    logger.info("Loading dataset...")
    pairs = _load_dataset(
        novel=novel,
        min_human_score=ds_cfg.get("min_human_score", 3),
        min_auto_score=ds_cfg.get("min_auto_score", 4),
    )
    if not pairs:
        logger.error("No training pairs found in dataset DB")
        return 1

    max_samples = ds_cfg.get("max_train_samples", 10000)
    if len(pairs) > max_samples:
        pairs = pairs[:max_samples]

    logger.info(f"Loaded {len(pairs)} training pairs")

    dataset = _prepare_dataset(
        pairs,
        val_split=ds_cfg.get("val_split", 0.1),
        test_split=ds_cfg.get("test_split", 0.1),
    )
    logger.info(f"Train: {len(dataset['train'])} | Val: {len(dataset['val'])} | Test: {len(dataset['test'])}")

    # ── Determine device ──
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    # ── Load base model with optional 4-bit quantization ──
    logger.info("Loading base model (this may take a while)...")
    hf_model = config.get("model", {}).get("hf_model_name", "google/gemma-2b")
    logger.info(f"HF base model: {hf_model}")

    quant_cfg = config.get("quantization", {})
    bnb_config = None
    if quant_cfg.get("load_in_4bit", False) and device == "cuda":
        try:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type=quant_cfg.get("bnb_4bit_quant_type", "nf4"),
            )
        except Exception:
            logger.warning("bitsandbytes not available; loading in 8-bit")

    try:
        tokenizer = AutoTokenizer.from_pretrained(hf_model)
        tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            hf_model,
            quantization_config=bnb_config,
            device_map="auto" if device == "cuda" else None,
            torch_dtype=torch.float32 if device == "cpu" else torch.float16,
        )
    except Exception as e:
        logger.error(f"Failed to load base model: {e}")
        return 1

    # ── Apply LoRA ──
    logger.info("Applying LoRA configuration...")
    peft_config = LoraConfig(
        r=lora_cfg.get("r", 16),
        lora_alpha=lora_cfg.get("lora_alpha", 32),
        lora_dropout=lora_cfg.get("lora_dropout", 0.05),
        target_modules=lora_cfg.get("target_modules", ["q_proj", "v_proj"]),
        bias=lora_cfg.get("bias", "none"),
        task_type=lora_cfg.get("task_type", "CAUSAL_LM"),
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # ── Tokenize dataset with label masking ──
    # Only train on target (Myanmar) tokens, not source (English) tokens.
    def tokenize_fn(examples):
        sources = examples["source"]
        targets = examples["target"]
        all_input_ids = []
        all_labels = []
        for s, t in zip(sources, targets):
            # Format: source\n\ntarget<eos>
            source_tokens = tokenizer.encode(
                s, add_special_tokens=False, truncation=True, max_length=256
            )
            target_tokens = tokenizer.encode(
                t, add_special_tokens=False, truncation=True, max_length=256
            )
            eos = tokenizer.eos_token_id
            input_ids = source_tokens + [eos] + target_tokens + [eos]
            # Mask source tokens: -100 means "ignore in loss computation"
            labels = ([-100] * len(source_tokens)) + [-100] + target_tokens + [eos]
            # Truncate/pad to max_length
            max_len = 512
            input_ids = (input_ids[:max_len] if len(input_ids) > max_len
                         else input_ids + [tokenizer.pad_token_id] * (max_len - len(input_ids)))
            labels = (labels[:max_len] if len(labels) > max_len
                      else labels + [-100] * (max_len - len(labels)))
            all_input_ids.append(input_ids)
            all_labels.append(labels)
        return {"input_ids": all_input_ids, "labels": all_labels, "attention_mask": [[1 if i != tokenizer.pad_token_id else 0 for i in ids] for ids in all_input_ids]}

    tokenized = dataset.map(tokenize_fn, batched=True, remove_columns=["source", "target"])

    # ── Training arguments ──
    adapter_name = adapter_name or f"padauk-lora-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = ADAPTER_DIR / adapter_name
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=train_cfg.get("per_device_train_batch_size", 4),
        gradient_accumulation_steps=train_cfg.get("gradient_accumulation_steps", 2),
        learning_rate=train_cfg.get("learning_rate", 2e-4),
        num_train_epochs=train_cfg.get("num_train_epochs", 3),
        warmup_steps=train_cfg.get("warmup_steps", 50),
        logging_steps=train_cfg.get("logging_steps", 10),
        evaluation_strategy=train_cfg.get("evaluation_strategy", "epoch"),
        save_strategy=train_cfg.get("save_strategy", "epoch"),
        load_best_model_at_end=train_cfg.get("load_best_model_at_end", True),
        metric_for_best_model=train_cfg.get("metric_for_best_model", "eval_loss"),
        greater_is_better=train_cfg.get("greater_is_better", False),
        fp16=train_cfg.get("fp16", False) and device == "cuda",
        bf16=train_cfg.get("bf16", False) and device == "cuda",
        report_to="none",
        dataloader_num_workers=train_cfg.get("dataloader_num_workers", 2),
        save_total_limit=2,
    )

    # ── Trainer ──
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["val"],
        tokenizer=tokenizer,
    )

    # ── Train ──
    logger.info("Starting training...")
    try:
        trainer.train()
    except Exception as e:
        logger.error(f"Training failed: {e}")
        return 1

    # ── Save adapter ──
    logger.info(f"Saving adapter to {output_dir}")
    trainer.model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    # Save training metadata
    metadata = {
        "adapter_name": adapter_name,
        "base_model": hf_model,
        "trained_at": datetime.now().isoformat(),
        "novel": novel,
        "train_samples": len(dataset["train"]),
        "val_samples": len(dataset["val"]),
        "test_samples": len(dataset["test"]),
        "lora_config": lora_cfg,
        "training_config": train_cfg,
    }
    with open(output_dir / "training_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # ── Evaluate on test set ──
    logger.info("Evaluating on test set...")
    test_results = trainer.evaluate(tokenized["test"])
    logger.info(f"Test loss: {test_results.get('eval_loss', 'N/A')}")

    print("\n=== Fine-tuning Complete! ===")
    print(f"  Adapter: {adapter_name}")
    print(f"  Location: {output_dir}")
    print(f"  Train samples: {len(dataset['train'])}")
    print(f"  Test loss: {test_results.get('eval_loss', 'N/A')}")
    print(f"\nUsage: python -m src.main --novel X --chapter 1 --use-adapter {adapter_name}")

    return 0
