"""Synthetic data generation for the 9-class intent classifier.

Fills bilingual (English + Chinese) templates with plausible slot values
drawn from the seed menu. Deterministic under a seed. No LLM calls.

Usage::

    python -m fos_ai_training.intent.data --out data.jsonl --n 56

Target: ``n * 9 ≈ 500`` labelled samples.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


# ---------- 9 intent labels (order is the canonical label index) ----------

INTENT_LABELS: list[str] = [
    "search",
    "recommend",
    "order",
    "status_check",
    "cancel",
    "rating",
    "menu_browse",
    "chitchat",
    "complaint",
]


# ---------- slot values drawn from the seed menu ----------

SLOT_VALUES: dict[str, list[str]] = {
    "food": [
        "kung pao chicken",
        "mapo tofu",
        "dan dan noodles",
        "dim sum",
        "roast duck",
        "pasta",
        "pizza",
        "sushi",
        "ramen",
        "fried rice",
        "宫保鸡丁",
        "麻婆豆腐",
        "担担面",
        "点心",
        "烤鸭",
    ],
    "restaurant": [
        "Sichuan Delight",
        "Cantonese Kitchen",
        "La Dolce Vita",
        "Sushi Bar",
        "Ramen House",
        "川味轩",
        "粤膳轩",
        "意式餐厅",
    ],
    "order_id": ["42", "100", "1024", "7", "2048", "88", "316", "999"],
    "cuisine": [
        "Sichuan",
        "Cantonese",
        "Italian",
        "Japanese",
        "Thai",
        "Korean",
        "川菜",
        "粤菜",
        "意餐",
        "日料",
    ],
    "price": ["10", "15", "20", "25", "30", "50"],
    "adj": ["spicy", "cheap", "fresh", "healthy", "light", "辣的", "便宜的", "清淡的"],
    "greeting": ["hi", "hello", "hey", "你好", "嗨"],
    "stars": ["4", "5", "3", "五星", "四星"],
}


# ---------- per-class templates (EN + ZH, 5-10 each) ----------

TEMPLATES: dict[str, list[str]] = {
    "search": [
        "find {adj} {food}",
        "search for {food} near me",
        "show me {cuisine} food under {price} dollars",
        "any {food} at {restaurant}?",
        "look up {food}",
        "is there {food} available",
        "帮我找一下{food}",
        "搜一下{cuisine}的菜",
        "有没有{adj}{food}",
    ],
    "recommend": [
        "what should I eat tonight?",
        "recommend something {adj}",
        "suggest a {cuisine} dish for me",
        "what do you recommend for dinner?",
        "give me a popular {food} pick",
        "I don't know what to eat, help me choose",
        "surprise me with something good",
        "推荐个{cuisine}吧",
        "今晚吃啥好呢？",
        "给我来点{adj}的推荐",
    ],
    "order": [
        "I want to order two {food}",
        "place an order for {food} from {restaurant}",
        "get me one {food} and one {food}",
        "order {food} for delivery",
        "I'll take the {food}",
        "add {food} to my cart and checkout",
        "来一份{food}",
        "帮我下单两份{food}",
        "我要点{restaurant}的{food}",
    ],
    "status_check": [
        "where is my order?",
        "what's the status of order {order_id}?",
        "has order {order_id} been delivered yet",
        "track my latest order",
        "when will my food arrive",
        "is my delivery on the way",
        "我的订单{order_id}到哪儿了",
        "{order_id}号订单状态是什么",
        "外卖还有多久到",
    ],
    "cancel": [
        "cancel order {order_id}",
        "please cancel my last order",
        "I want to cancel order {order_id}",
        "abort the order I just placed",
        "cancel the {food} I ordered",
        "stop the delivery of {order_id}",
        "取消订单{order_id}",
        "帮我把刚才下的单取消了",
        "不想要了，取消{order_id}",
    ],
    "rating": [
        "rate order {order_id} {stars} stars",
        "I want to leave a {stars}-star review on order {order_id}",
        "give {stars} stars to {restaurant}",
        "review my last order as {stars} stars",
        "submit a rating for {order_id}",
        "the {food} was great, {stars} stars",
        "给{order_id}号订单打{stars}分",
        "{restaurant}评个{stars}星",
        "这次体验不错，打{stars}分",
    ],
    "menu_browse": [
        "show me the menu of {restaurant}",
        "what does {restaurant} serve?",
        "list all dishes at {restaurant}",
        "open the {cuisine} menu",
        "browse {restaurant}",
        "see available dishes for {restaurant}",
        "看一下{restaurant}的菜单",
        "{restaurant}都卖啥",
        "浏览{cuisine}餐厅",
    ],
    "chitchat": [
        "{greeting}, how are you?",
        "{greeting}",
        "good morning",
        "thanks a lot!",
        "you are helpful",
        "lol ok",
        "{greeting}，今天怎么样",
        "谢啦",
        "嗯嗯",
    ],
    "complaint": [
        "my {food} arrived cold",
        "the order is late and I'm upset",
        "the delivery person was rude",
        "order {order_id} is wrong, I got the wrong dish",
        "the {food} tasted bad, want a refund",
        "this is unacceptable service",
        "{food}送来的时候是凉的",
        "{order_id}号订单送错了",
        "骑手态度特别差",
    ],
}


# ---------- generation ----------


def _fill_template(tpl: str, rng: random.Random) -> str:
    """Replace ``{placeholder}`` occurrences by sampling from SLOT_VALUES."""
    out = tpl
    # Process each distinct placeholder; reuse the same value for repeated keys
    # inside a single template to keep wording consistent.
    for slot in SLOT_VALUES:
        token = "{" + slot + "}"
        while token in out:
            out = out.replace(token, rng.choice(SLOT_VALUES[slot]), 1)
    return out


def generate_dataset(
    n_per_class: int = 56,
    seed: int = 42,
) -> list[dict[str, str]]:
    """Return a deterministic list of ``{"text", "label"}`` records.

    Default ``n_per_class=56`` gives ``56 * 9 = 504`` samples.
    """
    rng = random.Random(seed)
    records: list[dict[str, str]] = []

    for label in INTENT_LABELS:
        tpls = TEMPLATES[label]
        if not tpls:
            raise ValueError(f"No templates for label {label!r}")
        for _ in range(n_per_class):
            tpl = rng.choice(tpls)
            text = _fill_template(tpl, rng).strip()
            if not text:
                raise ValueError(f"Empty text from template {tpl!r}")
            records.append({"text": text, "label": label})

    rng.shuffle(records)
    return records


# ---------- serialisation ----------


def save_as_jsonl(records: list[dict[str, str]], path: str | Path) -> None:
    """Write each record as one JSON object per line."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    logger.info("Wrote %d records to %s", len(records), p)


def load_jsonl(path: str | Path) -> list[dict[str, str]]:
    """Read a JSONL dataset from disk."""
    p = Path(path)
    out: list[dict[str, str]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def split_dataset(
    records: list[dict[str, str]],
    val_frac: float = 0.1,
    seed: int = 42,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Deterministic train/val split.

    Shuffles a copy with a fixed RNG, then cuts at ``val_frac``.
    Returns ``(train, val)``.
    """
    if not 0.0 < val_frac < 1.0:
        raise ValueError(f"val_frac must be in (0, 1), got {val_frac}")
    rng = random.Random(seed)
    shuffled = list(records)
    rng.shuffle(shuffled)
    cut = max(1, int(len(shuffled) * val_frac))
    val = shuffled[:cut]
    train = shuffled[cut:]
    return train, val


# ---------- CLI ----------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fos_ai_training.intent.data",
        description="Generate synthetic labelled intent data (EN + ZH).",
    )
    parser.add_argument(
        "--out",
        default="ai_service/training/fos_ai_training/intent/data.jsonl",
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=56,
        help="Samples per class (default 56 → ~504 total).",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--val-frac",
        type=float,
        default=0.0,
        help="If >0, also write a .val.jsonl sibling file with this fraction.",
    )
    return parser


def _iter_counts(records: list[dict[str, str]]) -> Iterator[tuple[str, int]]:
    counts: dict[str, int] = {label: 0 for label in INTENT_LABELS}
    for r in records:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    yield from counts.items()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _build_arg_parser().parse_args(argv)

    records = generate_dataset(n_per_class=args.n, seed=args.seed)

    if args.val_frac > 0:
        train, val = split_dataset(records, val_frac=args.val_frac, seed=args.seed)
        save_as_jsonl(train, args.out)
        val_path = str(Path(args.out).with_suffix(".val.jsonl"))
        save_as_jsonl(val, val_path)
        print(f"Wrote {len(train)} train records to {args.out}")
        print(f"Wrote {len(val)} val records to {val_path}")
    else:
        save_as_jsonl(records, args.out)
        print(f"Wrote {len(records)} records to {args.out}")

    print("Per-class counts:")
    for label, count in _iter_counts(records):
        print(f"  {label:15s} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
