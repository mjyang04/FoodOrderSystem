# Training a 9-class intent router with 500 samples and LoRA on Qwen2.5-0.5B

This post is the fine-tuning half of the Sprint 6 AI-depth work on
FoodOrderSystem. It covers why a food-ordering chat agent wants a cheap
dedicated intent classifier in front of its tool router, how I built a
500-sample bilingual synthetic dataset without touching an LLM, and the LoRA
recipe I used to specialise `Qwen/Qwen2.5-0.5B-Instruct` on it. The accuracy
numbers themselves are deferred — training is a follow-up the user will run
on a T4 — but the pipeline, the fallback strategy, and the honest limitations
are all in place.

## Why LoRA for this task

The chat agent already has an LLM in the loop for tool calls. Asking that
same LLM to first classify intent — even with a few-shot prompt — is an
expensive way to route. Few-shot examples eat context window (so prompt
caching helps less than you'd expect, and cost scales per-call), and the
latency of a round-trip to Anthropic for "is this a `search` or a
`menu_browse`?" is absurd for what is ultimately a 9-class decision. A small
specialised classifier collapses that to a single local forward pass.

LoRA is the obvious mechanism: a few million trainable parameters on top of
a frozen 0.5 B base, 8 MB adapter weights on disk, trainable on a free-tier
T4 in ten minutes. It also keeps the base model reusable — I can swap
adapters for other narrow tasks (e.g. cuisine classifier, sentiment) without
holding multiple full checkpoints.

## Choosing the base

`Qwen/Qwen2.5-0.5B-Instruct` ticks four boxes that matter for this project:
small enough to fit in Colab free tier, bilingual (the menu and the user base
mix English and Chinese), instruction-tuned so the chat template works
out-of-the-box, and Apache-2.0 licensed. Going smaller (TinyLlama-1.1B is
roughly double, Phi-3 is bigger) didn't feel worth it; going bigger would
have defeated the point of doing this locally.

## Data synthesis

Nine intent classes: `search`, `recommend`, `order`, `status_check`,
`cancel`, `rating`, `menu_browse`, `chitchat`, `complaint`. I wrote a
deterministic generator in `data.py` — no LLM calls — that produces ~56
samples per class from templates filled with slot values (food names,
restaurant names, order ids, star counts). Two rules I stuck to: every class
gets both English and Chinese templates, and the RNG is seeded so the
dataset is reproducible. Total: 500 rows, roughly 70% EN / 30% ZH, label
distribution balanced by construction.

The output is newline-delimited JSON:

```jsonl
{"text": "find me cheap spicy noodles", "label": "search"}
{"text": "取消订单 42", "label": "cancel"}
{"text": "rate order 100 five stars", "label": "rating"}
```

## Training recipe

LoRA config:

```yaml
r: 8
lora_alpha: 16
lora_dropout: 0.05
target_modules: all-linear
lr: 2e-4
epochs: 3
batch_size: 4
grad_accum: 4
```

`target_modules=all-linear` is Qwen's recommended setting — `peft` walks the
model and attaches LoRA to every linear layer automatically. The loss is
computed only on the assistant tokens via `trl.DataCollatorForCompletionOnlyLM`,
which is the right choice for classification-as-generation: I don't want the
model to learn to reproduce the prompt, only the label.

The chat template is straightforward:

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

A sweep config (`configs/r4.yaml`, `configs/r8.yaml`, `configs/r16.yaml`)
compares `r={4, 8, 16}` with matched `alpha`, and the training script has a
`--smoke --no-save` mode that runs a 5-step dry run for CI.

## Three-way comparison

The comparison that matters for the interview story is zero-shot prompt
vs few-shot prompt vs trained adapter, on all three axes — accuracy,
latency, per-call cost:

| Approach                        | Accuracy | p95 latency | $/1k calls |
|---------------------------------|----------|-------------|------------|
| Zero-shot, Claude Haiku         | TBD      | TBD         | TBD        |
| Few-shot (4 ex), Claude Haiku   | TBD      | TBD         | TBD        |
| LoRA, Qwen2.5-0.5B, local       | TBD      | TBD         | TBD        |

TBDs are intentional — the table gets filled after the user runs training on
real hardware. The columns and comparison design are published in
`ai_service/training/fos_ai_training/intent/model_card.md` §4.

## The fallback strategy

The service layer doesn't require the adapter to exist. `intent_classifier.py`
exposes a `LoraIntentClassifier` and a `FallbackIntentClassifier`; the
fallback uses the existing `LlmClient` tool-call with a static few-shot
prompt. At startup the service picks the LoRA path if `INTENT_ADAPTER_PATH`
is set and the weights load cleanly, otherwise it falls back. That means the
service boots on a laptop without `peft` / `torch` installed globally, and
the adapter can be rotated at runtime (stop, swap the path, restart) without
a redeploy.

## Honest limitations

The limitations deserve a paragraph because they'd be the first thing a
reviewer would hit:

- **Synthetic-only data.** Templates don't cover real phrasing drift, slang,
  sarcasm, or multi-intent utterances. Accuracy on real users will be lower
  than whatever the synthetic val split says.
- **Domain-specific.** The classifier knows FoodOrderSystem's 9 intents;
  feeding it "book a hotel" produces a confident garbage label. OOD
  detection (a softmax-threshold gate) is the minimum caller-side guard.
- **No confidence calibration.** The returned probability is the top label
  token's softmax; it correlates weakly with actual correctness. Production
  use should rely on thresholded routing and a fallback path, not raw
  confidence.
- **Evaluation is incomplete** until training runs and the table above has
  real numbers.

## Reproduce

```bash
cd ai_service

# 1) install training extras (peft, trl, accelerate, datasets)
uv sync --extra training

# 2) regenerate the dataset (fast, no GPU)
uv run python -m fos_ai_training.intent.data \
    --out training/fos_ai_training/intent/data.jsonl \
    --n 56 --seed 42

# 3) train (Colab T4 ~10 min; Mac MPS also works)
uv run python -m fos_ai_training.intent.train \
    --model Qwen/Qwen2.5-0.5B-Instruct \
    --data training/fos_ai_training/intent/data.jsonl \
    --output-dir training/fos_ai_training/intent/output/ \
    --r 8 --lora-alpha 16 --lora-dropout 0.05 \
    --lr 2e-4 --epochs 3 --batch-size 4 --grad-accum 4
```

Full recipe, evaluation protocol, and reproduction notes:
`ai_service/training/fos_ai_training/intent/model_card.md`.

— Mingjia Yang, 2026-04
