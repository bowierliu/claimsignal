"""Lexical BM25 baseline (Okapi, k1=1.5, b=0.75). Pure Python; the corpus is ~2k chunks."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "which",
        "who",
        "why",
        "with",
        "how",
        "does",
        "do",
        "did",
        "can",
        "may",
        "must",
        "shall",
        "should",
    ]
)


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    score: float


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]


class BM25Index:
    def __init__(self, chunk_ids: list[str], texts: list[str], k1: float = 1.5, b: float = 0.75):
        if len(chunk_ids) != len(texts):
            raise ValueError("chunk_ids and texts must have equal length")
        self._ids = chunk_ids
        self._k1 = k1
        self._b = b
        docs = [tokenize(t) for t in texts]
        self._lengths = [len(d) for d in docs]
        self._avg_len = sum(self._lengths) / max(1, len(docs))
        self._tf = [Counter(d) for d in docs]
        df: Counter[str] = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self._postings: dict[str, list[int]] = {}
        for i, tf in enumerate(self._tf):
            for term in tf:
                self._postings.setdefault(term, []).append(i)

    def search(self, query: str, k: int = 10) -> list[Hit]:
        scores: dict[int, float] = {}
        for term in set(tokenize(query)):
            idf = self._idf.get(term)
            if idf is None:
                continue
            for i in self._postings[term]:
                tf = self._tf[i][term]
                norm = 1 - self._b + self._b * self._lengths[i] / self._avg_len
                scores[i] = scores.get(i, 0.0) + idf * tf * (self._k1 + 1) / (tf + self._k1 * norm)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
        return [Hit(self._ids[i], s) for i, s in ranked]
