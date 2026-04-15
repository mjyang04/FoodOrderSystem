"""Training-time package for fos_ai (LoRA fine-tuning, data generation).

Kept separate from the runtime ``fos_ai`` package so heavy deps
(``peft``, ``trl``, ``accelerate``) stay out of the production image.
Install with ``uv sync --extra training``.
"""
