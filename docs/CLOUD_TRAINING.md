# Fine-tuning EN→Myanmar: build data locally, train in the cloud, run on your PC

Goal: make the local Ollama model translate **like your human translator** by
fine-tuning a LoRA adapter on your aligned `en/` + `mm/` corpus.

Your RX 580 (gfx803) cannot train (ROCm/bitsandbytes don't support it), so we
**train in the cloud** (a few hours, ~$5–20 — or free on Colab T4) and **run
inference locally**. Every other step runs on your PC.

**Base model.** The Ollama `padauk-gemma` is itself a LoRA adapter on
**`unsloth/gemma-4-E4B-it`** (Gemma 3n E4B, ~8B). Our translation LoRA trains on
that **same base**. Gemma 3n is a non-standard architecture (MatFormer / per-layer
embeddings), so we train with **Unsloth**, which supports it directly, fits a
16 GB GPU, and exports GGUF in one step. (Use the exact base id from the model
card: <https://huggingface.co/WYNN747/ai4burmese-padauk>.)

```
data (en/mm)  →  align (BGE-M3)  →  ChatML dataset  →  [CLOUD] QLoRA  →  GGUF  →  ollama create  →  chrF eval
   local            local             local            cloud GPU       local       local            local
```

---

## Step 0 — Align all novels (local, one-time, slow)

Sentence-align every novel that has both `en/` and `mm/` (handles the 001↔0001
naming and partial translations automatically):

```bash
python scripts/build_finetune_dataset.py --run-alignment --min-similarity 0.70
```

This runs BGE-M3 alignment, then writes:

```
data/finetune/train.jsonl
data/finetune/val.jsonl
data/finetune/test.jsonl      # held-out chapters — NEVER trained on
```

Tune `--holdout` (test chapters per novel, default 20) and `--min-similarity`
(0.70 is a good precision/recall balance; lower → more but noisier pairs).

Sanity-check the dataset without a GPU:

```bash
python scripts/train_lora_cloud.py --dry-run
```

> Already-aligned data lives in the SQLite alignment DB; re-running without
> `--run-alignment` just re-exports the JSONL (fast).

---

## Step 1 — Measure the baseline (local)

Before training, record where the current model stands so you can prove the LoRA
helped. Translate the held-out test chapters with your current model, then:

```bash
python -m src.utils.translation_eval \
    --hyp data/output/a-will-eternal \
    --ref data/input/a-will-eternal/mm
```

Note the **corpus chrF**. (Reminder: ~54 = unrelated-text floor; good literary
output lands meaningfully above it.)

---

## Step 2 — Train the LoRA with Unsloth (cloud GPU)

Pick a provider with a **16–24 GB GPU** (free Colab T4, or RunPod/Vast.ai
RTX 4090). Use a recent PyTorch 2.x + CUDA 12 image.

```bash
# on the cloud box
pip install unsloth "trl>=0.11" "datasets>=2.20"

# upload data/finetune/{train,val}.jsonl, then (Unsloth is the default):
python scripts/train_lora_cloud.py \
    --base-model unsloth/gemma-4-E4B-it \
    --train data/finetune/train.jsonl \
    --val   data/finetune/val.jsonl \
    --out   models/adapters/en-my-lora \
    --epochs 2 --lora-r 16 --max-seq-len 1536 \
    --gguf q4_k_m
```

Defaults (r=16, batch 1 × grad-accum 16, lr 2e-4, cosine, 2 epochs) fit 16 GB
with Unsloth. Watch the eval loss; stop if it stops improving.

> **Standard Gemma-2 base instead?** Pass `--no-unsloth --base-model
> google/gemma-2-9b-it` and `pip install transformers peft bitsandbytes
> accelerate`. Gemma **3n** (E4B) requires Unsloth — plain `AutoModelForCausalLM`
> won't load it.

---

## Step 3 — Export GGUF for Ollama

With Unsloth, `--gguf q4_k_m` already wrote a **merged, quantized GGUF** under
`models/adapters/en-my-lora/` during Step 2 — just download it (~5–7 GB) to your
PC. No separate merge/llama.cpp step needed.

<details><summary>Manual export (only for the <code>--no-unsloth</code> path)</summary>

```bash
python - <<'PY'
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer
m = AutoPeftModelForCausalLM.from_pretrained("models/adapters/en-my-lora").merge_and_unload()
m.save_pretrained("models/en-my-merged")
AutoTokenizer.from_pretrained("models/adapters/en-my-lora").save_pretrained("models/en-my-merged")
PY
git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp && pip install -r requirements.txt
python convert_hf_to_gguf.py ../models/en-my-merged --outfile en-my.f16.gguf
./llama-quantize en-my.f16.gguf en-my.Q4_K_M.gguf Q4_K_M
```
</details>

---

## Step 4 — Load into Ollama (local)

```bash
cat > Modelfile <<'EOF'
FROM ./en-my.Q4_K_M.gguf
PARAMETER temperature 0.2
PARAMETER num_ctx 8192
SYSTEM You are an expert literary translator specializing in English to Myanmar translation. Preserve tone, atmosphere, emotions, dialogue style, and character voice naturally.
EOF

ollama create en-my-translator -f Modelfile
```

Point the pipeline at it (config/settings.yaml `models:` → model name
`en-my-translator`). Keep `temperature ≤ 0.2` (Myanmar degrades above it).

---

## Step 5 — Re-measure and compare (local)

Translate the **same held-out chapters** with the fine-tuned model and re-run the
chrF eval from Step 1. A higher corpus chrF = measurably closer to your human
translator. Stack `rerank.enabled: true` (QE best-of-N) on top for a further bump.

| Run | Corpus chrF |
|-----|-------------|
| Baseline (current model) | _fill in_ |
| + LoRA fine-tune         | _fill in_ |
| + LoRA + QE rerank       | _fill in_ |

---

## Iterating

- **chrF flat/low?** Inspect the lowest-scoring test chapters the eval prints —
  usually alignment noise or a register mismatch. Raise `--min-similarity`, add
  more aligned novels, or train another epoch.
- **More data** is the biggest lever: align additional novels and rebuild.
- **Don't train on the held-out chapters** — that inflates chrF and hides real
  quality. The split in Step 0 already prevents this.
```
