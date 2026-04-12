"""PyTorch embedding using HuggingFace transformers.

Loads ``paraphrase-multilingual-MiniLM-L12-v2`` (384-dim, 50 languages)
and implements mean-pooling + L2-normalisation in raw PyTorch — no
``sentence_transformers`` wrapper.
"""

from __future__ import annotations

import logging

import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class Embedder:
    """Encode text into L2-normalised 384-dim vectors."""

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        logger.info("Loading embedding model: %s", model_name)
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModel.from_pretrained(model_name)
        self._model.eval()
        self._dim = self._model.config.hidden_size
        logger.info("Embedding model ready — dim=%d", self._dim)

    @property
    def dim(self) -> int:
        return self._dim

    @torch.no_grad()
    def encode(self, texts: list[str], batch_size: int = 32) -> torch.Tensor:
        """Encode a list of texts into an (N, dim) L2-normalised tensor.

        Args:
            texts: Strings to encode.
            batch_size: Tokenisation / forward-pass batch size.

        Returns:
            Float tensor of shape ``(len(texts), self.dim)``.
        """
        all_embeddings: list[torch.Tensor] = []

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt",
            )
            output = self._model(**encoded)

            # Mean-pooling over token dimension, respecting attention mask
            mask = encoded["attention_mask"].unsqueeze(-1).float()
            token_emb = output.last_hidden_state
            summed = (token_emb * mask).sum(dim=1)
            counted = mask.sum(dim=1).clamp(min=1e-9)
            mean_pooled = summed / counted

            # L2 normalise
            normed = F.normalize(mean_pooled, p=2, dim=1)
            all_embeddings.append(normed)

        return torch.cat(all_embeddings, dim=0)
