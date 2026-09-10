from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

_TOKEN = re.compile(r"[0-9A-Za-z가-힣_]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(text)]


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    content: str
    source: str


@dataclass(frozen=True)
class RetrievalHit:
    document: KnowledgeDocument
    score: float


class BM25Retriever:
    """Small dependency-free BM25 implementation for deterministic local tests.

    The production adapter can be replaced by a vector store without changing
    GroundedChatService because retrieval is kept behind one interface.
    """

    def __init__(self, documents: Iterable[KnowledgeDocument], k1: float = 1.5, b: float = 0.75):
        self.documents = list(documents)
        self.k1 = k1
        self.b = b
        self._tokens = [tokenize(doc.content) for doc in self.documents]
        self._term_freqs = [Counter(tokens) for tokens in self._tokens]
        self._doc_freq: Counter[str] = Counter()
        for tokens in self._tokens:
            self._doc_freq.update(set(tokens))
        self._avgdl = (
            sum(len(tokens) for tokens in self._tokens) / len(self._tokens)
            if self._tokens
            else 0.0
        )

    def search(self, query: str, limit: int = 5) -> list[RetrievalHit]:
        if not self.documents:
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        n_docs = len(self.documents)
        hits: list[RetrievalHit] = []
        for idx, doc in enumerate(self.documents):
            doc_len = max(len(self._tokens[idx]), 1)
            score = 0.0
            for term in query_tokens:
                tf = self._term_freqs[idx][term]
                if tf == 0:
                    continue
                df = self._doc_freq[term]
                idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
                norm = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self._avgdl, 1.0))
                score += idf * (tf * (self.k1 + 1)) / norm
            if score > 0:
                hits.append(RetrievalHit(document=doc, score=score))

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]
