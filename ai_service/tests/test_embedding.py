"""Tests for the PyTorch embedder — shape, normalisation, determinism."""

from __future__ import annotations

import pytest
import torch

from fos_ai.ml.embedding import Embedder


@pytest.fixture(scope="module")
def embedder() -> Embedder:
    """Module-scoped: load the model once for all tests in this file."""
    return Embedder()


class TestEmbedder:

    def test_encode_shape(self, embedder: Embedder):
        """Output tensor has (N, 384) shape."""
        texts = ["hello world", "你好世界", "spicy chicken"]
        result = embedder.encode(texts)
        assert result.shape == (3, 384)

    def test_encode_l2_normalised(self, embedder: Embedder):
        """Every row has unit L2 norm."""
        result = embedder.encode(["test sentence", "another one"])
        norms = result.norm(dim=1)
        assert torch.allclose(norms, torch.ones(2), atol=1e-5)

    def test_encode_single(self, embedder: Embedder):
        """Single text input works."""
        result = embedder.encode(["just one"])
        assert result.shape == (1, 384)

    def test_encode_deterministic(self, embedder: Embedder):
        """Same input → same output (model is in eval mode)."""
        text = ["determinism check"]
        a = embedder.encode(text)
        b = embedder.encode(text)
        assert torch.allclose(a, b, atol=1e-6)

    def test_encode_batching(self, embedder: Embedder):
        """Batched encoding produces same results as single encoding."""
        texts = [f"text {i}" for i in range(10)]
        batched = embedder.encode(texts, batch_size=3)
        single = embedder.encode(texts, batch_size=100)
        assert torch.allclose(batched, single, atol=1e-5)

    def test_dim_property(self, embedder: Embedder):
        """dim property matches actual output."""
        assert embedder.dim == 384
