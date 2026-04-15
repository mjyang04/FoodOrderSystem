"""LoRA fine-tuning for a 9-class intent classifier on Qwen2.5-0.5B-Instruct.

Approach: **causal LM with label tokens**.

Each example is framed as a chat turn where the assistant must reply with
only the label string. Loss is computed on the assistant tokens only
(via ``trl.DataCollatorForCompletionOnlyLM``).

This module is import-safe without the ``training`` optional group —
heavy imports live inside ``main()`` so unit tests on a plain dev install
still pass. Run with::

    uv run python -m fos_ai_training.intent.train --help
    uv run python -m fos_ai_training.intent.train \\
        --model Qwen/Qwen2.5-0.5B-Instruct \\
        --data ai_service/training/fos_ai_training/intent/data.jsonl \\
        --output-dir ai_service/training/fos_ai_training/intent/output/ \\
        --r 8 --lora-alpha 16 --epochs 3

Or a smoke test that caps to 1 step on the real model::

    uv run python -m fos_ai_training.intent.train --smoke --no-save

"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------- prompt / label helpers (safe to import anywhere) ----------

SYSTEM_PROMPT = (
    "Classify the user intent into one of: "
    "search, recommend, order, status_check, cancel, rating, menu_browse, chitchat, complaint. "
    "Reply with only the label."
)


def build_chat_messages(text: str, label: str | None = None) -> list[dict[str, str]]:
    """Build a 2- or 3-message list for ``apply_chat_template``.

    If ``label`` is provided, an assistant turn is appended for training.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]
    if label is not None:
        messages.append({"role": "assistant", "content": label})
    return messages


# ---------- CLI ----------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fos_ai_training.intent.train",
        description="LoRA fine-tune Qwen2.5-0.5B for 9-class intent classification.",
    )
    p.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument(
        "--data",
        default="ai_service/training/fos_ai_training/intent/data.jsonl",
        help="Path to JSONL training data with {text, label} rows.",
    )
    p.add_argument(
        "--output-dir",
        default="ai_service/training/fos_ai_training/intent/output/",
    )
    p.add_argument("--r", type=int, default=8)
    p.add_argument("--lora-alpha", type=int, default=16)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--grad-accum", type=int, default=4)
    p.add_argument("--max-steps", type=int, default=-1)
    p.add_argument("--val-frac", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--smoke",
        action="store_true",
        help="Cap data to 10 rows, epochs=1, max_steps=1. Honours SMOKE_STUB_MODEL env.",
    )
    p.add_argument(
        "--no-save",
        action="store_true",
        help="Do not write the adapter to disk (for CI smoke).",
    )
    return p


# ---------- main (heavy imports deferred) ----------


def main(argv: list[str] | None = None) -> int:
    """Entry point. Heavy deps (transformers.Trainer / peft / trl) are imported here.

    Guarded so that ``ImportError`` surfaces clearly if the ``training``
    optional group is not installed.
    """
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    args = _build_arg_parser().parse_args(argv)

    # ---- deferred, optional heavy imports ----
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model  # type: ignore[import-not-found]
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
        from trl import DataCollatorForCompletionOnlyLM  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Missing training dependencies. Install with: "
            "uv sync --extra training\n"
            f"Underlying error: {exc}"
        ) from exc

    # ---- smoke overrides ----
    model_name = args.model
    if args.smoke:
        stub = os.environ.get("SMOKE_STUB_MODEL")
        if stub:
            model_name = stub
            logger.info("smoke: using SMOKE_STUB_MODEL=%s", stub)
        args.epochs = 1
        args.max_steps = 1
        logger.info("smoke mode: epochs=1, max_steps=1")

    # ---- data ----
    from fos_ai_training.intent.data import (
        INTENT_LABELS,
        generate_dataset,
        load_jsonl,
        split_dataset,
    )

    data_path = Path(args.data)
    if data_path.exists():
        records = load_jsonl(data_path)
    else:
        logger.warning("data file %s not found — generating synthetic set", data_path)
        records = generate_dataset(seed=args.seed)

    if args.smoke:
        records = records[:10]

    train_rows, val_rows = split_dataset(records, val_frac=args.val_frac, seed=args.seed)
    logger.info("data: %d train / %d val", len(train_rows), len(val_rows))

    # ---- tokenizer + model ----
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def _format_row(row: dict[str, str]) -> dict[str, str]:
        messages = build_chat_messages(row["text"], row["label"])
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
        return {"text": text}

    train_ds = Dataset.from_list([_format_row(r) for r in train_rows])
    val_ds = Dataset.from_list([_format_row(r) for r in val_rows])

    def _tokenize(batch: dict[str, list[str]]) -> dict[str, list[list[int]]]:
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=256,
            padding=False,
        )

    train_ds = train_ds.map(_tokenize, batched=True, remove_columns=["text"])
    val_ds = val_ds.map(_tokenize, batched=True, remove_columns=["text"])

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float32,
        trust_remote_code=True,
    )

    lora_cfg = LoraConfig(
        r=args.r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules="all-linear",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    # ---- loss-on-completion collator ----
    # The Qwen chat template uses "<|im_start|>assistant\n" before the reply.
    response_template = "<|im_start|>assistant\n"
    collator = DataCollatorForCompletionOnlyLM(
        response_template=response_template,
        tokenizer=tokenizer,
    )

    # ---- training args ----
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        max_steps=args.max_steps,
        logging_steps=10,
        save_strategy="no" if args.no_save else "epoch",
        eval_strategy="epoch",
        report_to=[],
        seed=args.seed,
    )

    # transformers ≥ 4.46 renamed `tokenizer=` to `processing_class=`; keep
    # backward compatibility with older installs via a try/except.
    trainer_kwargs: dict = {
        "model": model,
        "args": training_args,
        "train_dataset": train_ds,
        "eval_dataset": val_ds,
        "data_collator": collator,
    }
    try:
        trainer = Trainer(**trainer_kwargs, processing_class=tokenizer)
    except TypeError:
        trainer = Trainer(**trainer_kwargs, tokenizer=tokenizer)

    trainer.train()

    # ---- simple val accuracy (generation style) ----
    acc = _evaluate_accuracy(model, tokenizer, val_rows, INTENT_LABELS)
    logger.info("val accuracy: %.4f", acc)
    metrics_path = Path(args.output_dir) / "metrics.json"
    if not args.no_save:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(json.dumps({"val_accuracy": acc}, indent=2))
        trainer.save_model(args.output_dir)
        tokenizer.save_pretrained(args.output_dir)
        logger.info("adapter saved to %s", args.output_dir)
    return 0


def _evaluate_accuracy(
    model,
    tokenizer,
    val_rows: list[dict[str, str]],
    labels: list[str],
) -> float:
    """Greedy-decode the label token for each val row and return accuracy."""
    import torch

    model.eval()
    correct = 0
    label_set = set(labels)
    for row in val_rows:
        messages = build_chat_messages(row["text"])
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        ids = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(
                **ids,
                max_new_tokens=8,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        generated = tokenizer.decode(
            out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True
        ).strip()
        pred = generated.split()[0] if generated else ""
        # normalise: accept exact match against known labels
        if pred in label_set and pred == row["label"]:
            correct += 1
    return correct / max(1, len(val_rows))


if __name__ == "__main__":
    raise SystemExit(main())
