from __future__ import annotations

import hashlib
import math
import re
from typing import Sequence

import httpx
import numpy as np

from app.config import Settings, get_settings


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    ascii_tokens = re.findall(r"[a-z0-9_]+", text)
    cjk = re.findall(r"[\u4e00-\u9fff]{1,3}", text)
    return ascii_tokens + cjk


class EmbeddingService:
    """OpenAI-compatible embeddings with deterministic local fallback for offline demos."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def dim(self) -> int:
        return self.settings.embedding_dim

    @property
    def mode(self) -> str:
        if self.settings.use_local_embeddings or not self.settings.effective_embedding_api_key:
            return "local"
        return "api"

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.mode == "local":
            return [self._local_embed(t) for t in texts]
        return self._api_embed(list(texts))

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def _local_embed(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float64)
        tokens = _tokenize(text) or ["empty"]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vec[idx] += sign * weight
            # bigram-ish second hash for denser signal
            digest2 = hashlib.md5(token.encode("utf-8")).digest()
            idx2 = int.from_bytes(digest2[:4], "big") % self.dim
            vec[idx2] += 0.35 * (1.0 if digest2[0] % 2 == 0 else -1.0)
        norm = np.linalg.norm(vec)
        if norm < 1e-12:
            return [0.0] * self.dim
        return (vec / norm).astype(float).tolist()

    def _api_embed(self, texts: list[str]) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self.settings.effective_embedding_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.settings.embedding_model, "input": texts}
        url = self.settings.effective_embedding_base_url.rstrip("/") + "/embeddings"
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()["data"]
            data = sorted(data, key=lambda x: x["index"])
            vectors = [row["embedding"] for row in data]
        # If provider dim differs, project/pad to configured dim for Neo4j index consistency
        out: list[list[float]] = []
        for v in vectors:
            if len(v) == self.dim:
                out.append(v)
            elif len(v) > self.dim:
                arr = np.array(v[: self.dim], dtype=np.float64)
                n = np.linalg.norm(arr) or 1.0
                out.append((arr / n).tolist())
            else:
                arr = np.zeros(self.dim, dtype=np.float64)
                arr[: len(v)] = v
                n = np.linalg.norm(arr) or 1.0
                out.append((arr / n).tolist())
        return out


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    aa = np.array(a, dtype=np.float64)
    bb = np.array(b, dtype=np.float64)
    denom = (np.linalg.norm(aa) * np.linalg.norm(bb)) or 1.0
    return float(np.dot(aa, bb) / denom)


def lexical_score(query: str, text: str) -> float:
    q = set(_tokenize(query))
    t = set(_tokenize(text))
    if not q or not t:
        return 0.0
    overlap = len(q & t)
    return overlap / math.sqrt(len(q) * len(t))
