---
language:
  - en
  - zh
library_name: peft
license: apache-2.0
base_model: Qwen/Qwen2.5-0.5B-Instruct
tags:
  - text-classification
  - intent-classification
  - lora
  - food-ordering
  - fos_ai
pipeline_tag: text-classification
---

# FoodOrderSystem Intent Classifier (LoRA on Qwen2.5-0.5B-Instruct)

A LoRA adapter that specialises `Qwen/Qwen2.5-0.5B-Instruct` to classify a
user utterance in the FoodOrderSystem chat agent into **one of 9 intents**.
The base model is unchanged; only the adapter weights are trained.

> **Status:** this card is a template. Fill the Evaluation and Reproduction
> sections after running the training command on real hardware. See the
> "How to train" block at the bottom.

---

## 1. Model overview

- **Base model:** `Qwen/Qwen2.5-0.5B-Instruct` (0.5 B params, Apache-2.0)
- **Adapter method:** LoRA, `r=8`, `alpha=16`, `dropout=0.05`, `target_modules="all-linear"`
- **Task:** 9-class intent classification (causal LM framing, label-token decoding)
- **Intended use:** gate the FoodOrderSystem chat agent's tool router so that
  cheap "search / menu_browse / chitchat" turns skip the expensive LLM call.

### Intent labels

| # | Label           | Example utterance                         |
|---|-----------------|-------------------------------------------|
| 0 | `search`        | "find cheap spicy noodles"                |
| 1 | `recommend`     | "what should I eat tonight?"              |
| 2 | `order`         | "I want two Kung Pao Chicken"             |
| 3 | `status_check`  | "where is my order 1024?"                 |
| 4 | `cancel`        | "cancel order 42"                         |
| 5 | `rating`        | "rate order 100 five stars"               |
| 6 | `menu_browse`   | "show me La Dolce Vita's menu"            |
| 7 | `chitchat`      | "hi, how are you?"                        |
| 8 | `complaint`     | "my food arrived cold"                    |

---

## 2. Training data

- **Size:** ~500 synthetic labelled samples (~56 per class).
- **Generation:** bilingual (EN + ZH) templates filled from a curated list of
  slot values (food names, restaurants, order ids, cuisines, star counts).
- **No LLM involvement** — data is produced by a deterministic RNG, fully
  reproducible under a seed.

### Regenerate the dataset

```bash
cd ai_service
uv run python -m fos_ai_training.intent.data \
    --out training/fos_ai_training/intent/data.jsonl \
    --n 56 --seed 42
```

Output: `data.jsonl` with one `{"text": ..., "label": ...}` per line.

---

## 3. Training recipe

- **Framework:** `transformers.Trainer` + `peft` + `trl`
- **Loss:** causal LM loss computed **only on the assistant tokens**
  (via `trl.DataCollatorForCompletionOnlyLM`).
- **Chat template:** each sample is framed as:

```text
<|im_start|>system
Classify the user intent into one of: search, recommend, order, status_check,
cancel, rating, menu_browse, chitchat, complaint. Reply with only the label.
<|im_end|>
<|im_start|>user
{text}
<|im_end|>
<|im_start|>assistant
{label}<|im_end|>
```

### Hyperparameter sweep

Three configs live in `configs/`:

| File     | r  | alpha | lr     | epochs | Notes                     |
|----------|----|-------|--------|--------|---------------------------|
| `r4.yaml`  | 4  | 8     | 2e-4   | 3      | cheapest baseline         |
| `r8.yaml`  | 8  | 16    | 2e-4   | 3      | **recommended default**   |
| `r16.yaml` | 16 | 32    | 1e-4   | 3      | higher capacity           |

---

## 4. Evaluation

Fill this section after running training.

| Metric              | Dev  | Notes                                   |
|---------------------|------|-----------------------------------------|
| Accuracy (overall)  | TBD  | 9-way                                   |
| Macro F1            | TBD  | per-class support is balanced           |
| Per-class accuracy  | TBD  | expect weakest on `complaint` / `chitchat` |
| Prompt-only baseline| TBD  | Qwen2.5-0.5B-Instruct, few-shot (4 ex) |
| Haiku 4.5 baseline  | TBD  | tool-call fallback classifier           |

Compare against:

1. **Zero-shot / few-shot with the base model** (same prompt, no adapter).
2. **`FallbackIntentClassifier`** — few-shot prompt to Claude Haiku via the
   existing `LlmClient`. Serves as the production fallback when no adapter
   is loaded.

---

## 5. Limitations and biases

- **Synthetic data:** templates cover only a narrow slice of real user
  language. Expect degraded accuracy on rare slang, sarcasm, or
  multi-intent utterances.
- **Bilingual coverage is uneven:** roughly 70% EN / 30% ZH; performance in
  other languages is undefined.
- **Confidence is not calibrated:** the returned softmax value is the
  probability of the top label *token*, which does not necessarily reflect
  real uncertainty.
- **Out-of-distribution handling:** utterances outside the 9 classes are
  force-mapped to the closest label rather than rejected. Use a confidence
  threshold on the caller side (e.g. route to the fallback LLM below 0.5).

---

## 6. Reproduction

### 6.1 Train the adapter locally

```bash
cd ai_service

# 1) install the optional training deps (heavy — peft, trl, accelerate, datasets)
uv sync --extra training

# 2) regenerate the dataset (fast, no GPU)
uv run python -m fos_ai_training.intent.data \
    --out training/fos_ai_training/intent/data.jsonl \
    --n 56 --seed 42

# 3) train (Colab T4 free tier is plenty; Mac MPS also works)
uv run python -m fos_ai_training.intent.train \
    --model Qwen/Qwen2.5-0.5B-Instruct \
    --data training/fos_ai_training/intent/data.jsonl \
    --output-dir training/fos_ai_training/intent/output/ \
    --r 8 --lora-alpha 16 --lora-dropout 0.05 \
    --lr 2e-4 --epochs 3 --batch-size 4 --grad-accum 4
```

Training completes in ~10 min on a single T4. Adapter weights are ~8 MB.

### 6.2 Smoke-test without training

```bash
uv run python -m fos_ai_training.intent.train --smoke --no-save
```

### 6.3 Push to HuggingFace Hub (optional)

```bash
huggingface-cli login
huggingface-cli upload mjyangnb/fos-intent-classifier-qwen2.5-0.5b-lora \
    ai_service/training/fos_ai_training/intent/output/
```

### 6.4 Wire into the service

```bash
export INTENT_ADAPTER_PATH=/abs/path/to/training/fos_ai_training/intent/output
uv run uvicorn fos_ai.main:app --host 127.0.0.1 --port 8000

# test
curl -X POST http://127.0.0.1:8000/ai/intent \
    -H 'Content-Type: application/json' \
    -H 'X-User-Id: 1' \
    -d '{"text": "cancel order 42"}'
# → {"label": "cancel", "confidence": 0.93, "source": "lora"}
```

---

## 7. License

- Adapter weights + code: **MIT**
- Base model (`Qwen/Qwen2.5-0.5B-Instruct`): **Apache-2.0** (inherited)
- Training data: synthetic, no third-party content.

## 8. Citation

```bibtex
@misc{fos_intent_classifier_2026,
  title  = {FoodOrderSystem Intent Classifier (LoRA on Qwen2.5-0.5B)},
  author = {Yang, Mingjia},
  year   = {2026},
  url    = {https://huggingface.co/mjyangnb/fos-intent-classifier-qwen2.5-0.5b-lora},
  note   = {Adapter trained as part of FoodOrderSystem Sprint 6 Phase 4.}
}
```
