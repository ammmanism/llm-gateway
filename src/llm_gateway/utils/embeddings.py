import asyncio
import hashlib
import logging
import re
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


class HashingEmbedder:
    """Deterministic local embedder used when the optional ML extra is absent."""

    dimension = 384
    backend_name = "deterministic-token-hashing-v1"

    def encode(self, texts, normalize_embeddings=True):
        single = isinstance(texts, str)
        items = [texts] if single else list(texts)
        vectors = []
        for text in items:
            vector = np.zeros(self.dimension, dtype=np.float32)
            tokens = re.findall(r"[a-z0-9]+", text.lower())
            features = tokens + [
                f"{left}_{right}" for left, right in zip(tokens, tokens[1:])
            ]
            for feature in features:
                digest = hashlib.sha256(feature.encode()).digest()
                bucket = int.from_bytes(digest[:4], "little") % self.dimension
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[bucket] += sign
            norm = np.linalg.norm(vector)
            if norm:
                vector /= norm
            vectors.append(vector)
        result = np.asarray(vectors, dtype=np.float32)
        return result[0] if single else result


class EmbeddingEngine:
    """Lazy local embedding engine with an explicit deterministic fallback."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            instance = super().__new__(cls)
            instance.model_name = "sentence-transformers/all-MiniLM-L6-v2"
            instance.model = None
            instance.dimension = 384
            instance.backend_name = "not-loaded"
            cls._instance = instance
        return cls._instance

    def load(self) -> None:
        if self.model is not None:
            return
        logger.info("Loading embedding model %s", self.model_name)
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            self.backend_name = self.model_name
        except Exception as exc:
            logger.warning(
                "Neural embedding model unavailable (%s); using deterministic "
                "hashing embeddings. Install the 'ml' extra and pre-download the "
                "model for neural semantic search.",
                exc,
            )
            self.model = HashingEmbedder()
            self.dimension = self.model.dimension
            self.backend_name = self.model.backend_name

    def _normalize_text(self, text: str) -> str:
        return text.strip().lower()

    async def embed(self, text: str) -> np.ndarray:
        if self.model is None:
            self.load()
        normalized = self._normalize_text(text)
        return await asyncio.to_thread(
            self.model.encode,
            normalized,
            normalize_embeddings=True,
        )

    async def embed_batch(self, texts: List[str]) -> np.ndarray:
        if self.model is None:
            self.load()
        normalized = [self._normalize_text(text) for text in texts]
        return await asyncio.to_thread(
            self.model.encode,
            normalized,
            normalize_embeddings=True,
        )


embedding_engine = EmbeddingEngine()
