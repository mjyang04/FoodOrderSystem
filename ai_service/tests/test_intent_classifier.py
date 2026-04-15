"""Tests for the intent classifier services (LoRA + LLM fallback)."""

from __future__ import annotations

from typing import Any

import pytest

from fos_ai.services.intent_classifier import (
    INTENT_LABELS,
    FallbackIntentClassifier,
    IntentUnavailable,
    LoraIntentClassifier,
)
from fos_ai.services.llm_client import TextOnlyResult, ToolCallResult


# ---------- LoraIntentClassifier ----------


def test_lora_raises_when_adapter_missing(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(IntentUnavailable):
        LoraIntentClassifier(
            base_model="Qwen/Qwen2.5-0.5B-Instruct",
            adapter_path=str(missing),
        )


def test_lora_classify_uses_softmax_over_label_tokens(tmp_path, monkeypatch):
    """Stub transformers + peft so no download happens; verify the label path."""
    pytest.importorskip(
        "peft",
        reason="peft not installed — skipping LoRA classify smoke. "
        "Install with `uv sync --extra training`.",
    )
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}")

    import torch

    class _Tok:
        pad_token = None
        eos_token = "<eos>"

        def __call__(self, text, add_special_tokens=True, return_tensors=None):
            # Deterministic 1-token id per label; enough for _ensure_loaded.
            token_map = {label: [idx + 1] for idx, label in enumerate(INTENT_LABELS)}
            if text in token_map:
                return {"input_ids": token_map[text]}
            # For the full prompt, return a dummy tensor
            ids = torch.tensor([[0, 0, 0]])
            return _TokenizedInput(ids)

        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
            return "<prompt>"

    class _TokenizedInput(dict):
        def __init__(self, ids):
            super().__init__(input_ids=ids)
            self._ids = ids

        def to(self, device):
            return self

    class _FakeLogits:
        def __init__(self):
            # vocab of at least 10 entries; boost index 3 (= "order" token id)
            self.logits = torch.zeros((1, 3, 20))
            # label token ids are 1..9 per _Tok; pick idx=3 → label "order"
            self.logits[0, -1, 3] = 10.0

    class _Model:
        device = "cpu"

        def __call__(self, **inputs):
            return _FakeLogits()

        def eval(self):
            return self

        def to(self, device):
            return self

    def _fake_from_peft(base, path):
        return _Model()

    import transformers  # noqa: F401

    monkeypatch.setattr(
        "transformers.AutoTokenizer.from_pretrained",
        lambda *a, **kw: _Tok(),
    )
    monkeypatch.setattr(
        "transformers.AutoModelForCausalLM.from_pretrained",
        lambda *a, **kw: _Model(),
    )
    import peft  # noqa: F401

    monkeypatch.setattr("peft.PeftModel.from_pretrained", _fake_from_peft)

    clf = LoraIntentClassifier(
        base_model="stub/tiny",
        adapter_path=str(adapter),
    )
    label, conf = clf.classify("I want to order two kung pao chicken")
    assert label == "order"
    assert 0.0 < conf <= 1.0


def test_lora_load_failure_raises_intent_unavailable(tmp_path, monkeypatch):
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}")

    def _boom(*a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr("transformers.AutoTokenizer.from_pretrained", _boom)

    clf = LoraIntentClassifier(
        base_model="stub/tiny",
        adapter_path=str(adapter),
    )
    with pytest.raises(IntentUnavailable):
        clf.classify("hello")


# ---------- FallbackIntentClassifier ----------


class _FakeLlm:
    def __init__(self, result: Any):
        self._result = result
        self.last_tools: list[dict] = []

    def tool_call(self, *, system: str, user: str, tools, max_tokens: int = 1024):
        self.last_tools = tools
        if isinstance(self._result, Exception):
            raise self._result
        return self._result

    def messages(self, **_):  # pragma: no cover
        raise NotImplementedError

    def messages_stream(self, **_):  # pragma: no cover
        raise NotImplementedError


def test_fallback_happy_path():
    llm = _FakeLlm(ToolCallResult(
        tool_name="classify_intent",
        tool_input={"label": "search", "confidence": 0.91},
    ))
    clf = FallbackIntentClassifier(llm=llm)
    label, conf = clf.classify("find spicy food near me")
    assert label == "search"
    assert conf == pytest.approx(0.91)
    # Tool schema shipped with all 9 labels
    schema = llm.last_tools[0]["input_schema"]["properties"]["label"]["enum"]
    assert set(schema) == set(INTENT_LABELS)


def test_fallback_rejects_empty_text():
    clf = FallbackIntentClassifier(llm=_FakeLlm(None))
    with pytest.raises(IntentUnavailable):
        clf.classify("")
    with pytest.raises(IntentUnavailable):
        clf.classify("   ")


def test_fallback_rejects_refusal_as_text():
    llm = _FakeLlm(TextOnlyResult(text="I cannot classify this", stop_reason="end_turn"))
    clf = FallbackIntentClassifier(llm=llm)
    with pytest.raises(IntentUnavailable):
        clf.classify("hi")


def test_fallback_rejects_unknown_label():
    llm = _FakeLlm(ToolCallResult(
        tool_name="classify_intent",
        tool_input={"label": "not_a_real_label", "confidence": 0.9},
    ))
    clf = FallbackIntentClassifier(llm=llm)
    with pytest.raises(IntentUnavailable):
        clf.classify("hi")


def test_fallback_rejects_non_numeric_confidence():
    llm = _FakeLlm(ToolCallResult(
        tool_name="classify_intent",
        tool_input={"label": "chitchat", "confidence": "high"},
    ))
    clf = FallbackIntentClassifier(llm=llm)
    with pytest.raises(IntentUnavailable):
        clf.classify("hi")


def test_fallback_clips_confidence_to_unit_interval():
    llm = _FakeLlm(ToolCallResult(
        tool_name="classify_intent",
        tool_input={"label": "chitchat", "confidence": 2.5},
    ))
    clf = FallbackIntentClassifier(llm=llm)
    label, conf = clf.classify("hi")
    assert label == "chitchat"
    assert conf == 1.0


def test_fallback_wraps_llm_exception():
    llm = _FakeLlm(RuntimeError("upstream 500"))
    clf = FallbackIntentClassifier(llm=llm)
    with pytest.raises(IntentUnavailable):
        clf.classify("hi")
