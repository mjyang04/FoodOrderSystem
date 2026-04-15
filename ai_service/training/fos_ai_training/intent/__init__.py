"""Intent classifier fine-tuning: data generation, training, configs, model card.

Submodules:
    - ``fos_ai_training.intent.data``: synthetic dataset generator
    - ``fos_ai_training.intent.train``: LoRA training entry point (heavy deps)

Lazy re-exports avoid RuntimeWarnings when submodules are executed as
``python -m fos_ai_training.intent.{data,train}``.
"""

from __future__ import annotations

__all__ = [
    "INTENT_LABELS",
    "SLOT_VALUES",
    "TEMPLATES",
    "generate_dataset",
    "load_jsonl",
    "save_as_jsonl",
    "split_dataset",
]


def __getattr__(name: str):  # pragma: no cover - simple lazy dispatch
    if name in __all__:
        from fos_ai_training.intent import data

        return getattr(data, name)
    raise AttributeError(f"module 'fos_ai_training.intent' has no attribute {name!r}")
