"""Intent classifier services: LoRA adapter path + LLM tool-call fallback.

Both implementations satisfy the :class:`IntentClassifier` protocol and
return ``(label, confidence)`` where ``label`` is one of the 9 canonical
FoodOrderSystem intent strings and ``confidence`` is in ``[0, 1]``.

- :class:`LoraIntentClassifier` loads `Qwen/Qwen2.5-0.5B-Instruct` plus a
  PEFT adapter lazily on first ``classify`` call. If the adapter files are
  missing at construction, the caller should fall back to the prompt
  classifier below.

- :class:`FallbackIntentClassifier` forces the LLM to emit
  ``{label, confidence}`` via tool calling. It works with any existing
  ``LlmClient`` (Anthropic or OpenAI).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

from fos_ai.services.llm_client import LlmClient, TextOnlyResult, ToolCallResult

logger = logging.getLogger(__name__)


# ---------- canonical labels ----------

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


class IntentUnavailable(RuntimeError):
    """Raised when the classifier cannot produce a label (e.g. model load failure)."""


# ---------- protocol ----------


class IntentClassifier(Protocol):
    """Any classifier must return ``(label, confidence)``."""

    def classify(self, text: str) -> tuple[str, float]: ...


# ---------- LoRA adapter path ----------


class LoraIntentClassifier:
    """Wraps a Qwen base + PEFT adapter. Lazy-loads on first classify().

    Raises immediately in ``__init__`` if the adapter directory is missing
    so callers can choose the fallback without catching a classify error.
    """

    def __init__(
        self,
        base_model: str,
        adapter_path: str,
        device: str | None = None,
    ) -> None:
        self._base_model = base_model
        self._adapter_path = adapter_path
        self._device = device
        self._model: Any = None
        self._tokenizer: Any = None
        self._label_token_ids: dict[str, int] | None = None

        if not Path(adapter_path).exists():
            raise IntentUnavailable(
                f"Adapter path not found: {adapter_path!r}. "
                "Train one via `python -m fos_ai_training.intent.train` "
                "or unset INTENT_ADAPTER_PATH."
            )
        logger.info(
            "LoraIntentClassifier configured — base=%s adapter=%s (lazy load)",
            base_model,
            adapter_path,
        )

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from peft import PeftModel  # type: ignore[import-not-found]
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise IntentUnavailable(
                "peft/transformers not installed — cannot load LoRA adapter. "
                "Install via `uv sync --extra training`."
            ) from exc

        try:
            tokenizer = AutoTokenizer.from_pretrained(
                self._base_model, trust_remote_code=True
            )
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            base = AutoModelForCausalLM.from_pretrained(
                self._base_model,
                torch_dtype=torch.float32,
                trust_remote_code=True,
            )
            model = PeftModel.from_pretrained(base, self._adapter_path)
            model.eval()
            if self._device:
                model = model.to(self._device)
        except Exception as exc:
            raise IntentUnavailable(f"Failed to load LoRA model: {exc}") from exc

        # Cache first-token id per label for fast scoring.
        label_ids: dict[str, int] = {}
        for label in INTENT_LABELS:
            ids = tokenizer(label, add_special_tokens=False)["input_ids"]
            if not ids:
                raise IntentUnavailable(
                    f"Tokeniser could not encode label {label!r}"
                )
            label_ids[label] = ids[0]

        self._tokenizer = tokenizer
        self._model = model
        self._label_token_ids = label_ids

    def classify(self, text: str) -> tuple[str, float]:
        self._ensure_loaded()
        if self._model is None or self._tokenizer is None or self._label_token_ids is None:
            raise IntentUnavailable("LoRA classifier not initialised")

        import torch
        from fos_ai_training.intent.train import build_chat_messages  # runtime dep

        messages = build_chat_messages(text)
        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)

        with torch.no_grad():
            out = self._model(**inputs)

        # Logits for the *next* token over the full vocab.
        next_logits = out.logits[0, -1, :]
        # Restrict to our 9 label tokens → softmax → pick argmax.
        label_ids = list(self._label_token_ids.values())
        sub = next_logits[label_ids]
        probs = torch.softmax(sub, dim=-1)
        idx = int(torch.argmax(probs).item())
        labels = list(self._label_token_ids.keys())
        label = labels[idx]
        conf = float(probs[idx].item())
        return label, conf


# ---------- LLM fallback path ----------


_CLASSIFY_TOOL: dict[str, Any] = {
    "name": "classify_intent",
    "description": (
        "Return the user's intent label and a calibrated confidence in [0, 1]. "
        "Always call this tool exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "label": {
                "type": "string",
                "enum": INTENT_LABELS,
                "description": "The single most likely intent.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence in the chosen label.",
            },
        },
        "required": ["label", "confidence"],
    },
}


_SYSTEM_PROMPT = (
    "You classify user utterances for a food-ordering app into one of "
    f"{len(INTENT_LABELS)} intents: {', '.join(INTENT_LABELS)}. "
    "Always reply by calling the classify_intent tool — no prose."
)


class FallbackIntentClassifier:
    """Few-shot prompt classifier via the existing ``LlmClient`` abstraction."""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    def classify(self, text: str) -> tuple[str, float]:
        if not text or not text.strip():
            raise IntentUnavailable("Empty text cannot be classified")

        try:
            result = self._llm.tool_call(
                system=_SYSTEM_PROMPT,
                user=text,
                tools=[_CLASSIFY_TOOL],
                max_tokens=128,
            )
        except Exception as exc:
            raise IntentUnavailable(f"LLM tool_call failed: {exc}") from exc

        if isinstance(result, TextOnlyResult):
            raise IntentUnavailable(
                f"LLM refused to call classify_intent: {result.text!r}"
            )
        assert isinstance(result, ToolCallResult)

        payload = result.tool_input or {}
        label = payload.get("label", "")
        conf = payload.get("confidence", 0.0)

        if label not in INTENT_LABELS:
            raise IntentUnavailable(f"LLM returned unknown label {label!r}")
        try:
            conf_f = float(conf)
        except (TypeError, ValueError) as exc:
            raise IntentUnavailable(f"LLM returned non-numeric confidence: {conf!r}") from exc
        # clip to [0, 1] — belt-and-braces
        conf_f = max(0.0, min(1.0, conf_f))
        return label, conf_f
