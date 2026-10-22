"""한국어 조사에 덜 흔들리는 BM25 (제안 — 기존 코드는 수정하지 않음).

문제
  app/rag/retrieval.py 의 tokenize() 는 공백·기호로만 자른다. 그래서
  질문의 "세마포어가" 와 문서의 "세마포어로" 가 서로 다른 단어가 되어 검색에서 만나지 못한다.

제안 (측정으로 고른 것 — rag_eval/tokenizer_results.md)
  단어 전체와, 끝의 흔한 조사·어미를 뗀 어간을 함께 색인한다. ("세마포어로" → 세마포어로, 세마포어)
  형태소 분석기·사전 없이 표준 라이브러리만 쓰고, 조사 목록은 40개 안팎의 짧은 상수다.

처음 제안했다가 버린 것
  글자 2-gram(tokenize_ngram) — 이 코퍼스에서 hit@1 이 75% → 62% 로 떨어졌다. 흔한 조각("어로", "하는")이 노이즈를 만든다.
  측정 없이 "n-gram 이 한국어에 좋다"는 통념을 따랐다면 나빠졌을 것이다. 코드는 비교용으로 남겨 둔다.

사용
  KoBM25Retriever 는 BM25Retriever 와 같은 search(query, limit) -> list[RetrievalHit] 규격이라
  KnowledgeStore 의 검색기 자리에, 또는 GroundedChatService(store=...) 의 store 자리에 그대로 끼울 수 있다.

한계
  - 조사 목록은 사람이 고른 것이고 질문 24개로만 평가했다. 과적합 가능성이 있으니 실제 사용자 질문으로 다시 확인한다.
  - '이', '가' 처럼 한 글자 조사는 어간이 2글자 이상일 때만 뗀다. ('아이' → '아' 가 되는 오류를 막는다)
  - rag_min_score(0.55) 같은 절대 기준값은 토크나이저를 바꾸면 의미가 달라진다. 반드시 평가 세트로 다시 정한다.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Callable, Iterable

from app.rag.retrieval import KnowledgeDocument, RetrievalHit

_WORD = re.compile(r"[0-9A-Za-z가-힣_]+")
_HANGUL = re.compile(r"[가-힣]")

# 긴 것부터 먼저 맞춘다. ('에서는' 을 '는' 보다 먼저)
PARTICLES: tuple[str, ...] = tuple(sorted({
    "은", "는", "이", "가", "을", "를", "의", "에", "에서", "으로", "로", "와", "과", "도", "만", "까지", "부터", "보다", "처럼",
    "에게", "한테", "이나", "나", "라고", "인가요", "인가", "나요", "가요", "합니다", "입니다", "하는", "하면", "하고", "되는",
    "에는", "에서는", "으로는",
}, key=len, reverse=True))


def stem_ko(word: str) -> str:
    """끝의 조사·어미 하나를 뗀다. 어간이 2글자 미만이 되면 떼지 않는다."""
    for p in PARTICLES:
        if word.endswith(p) and len(word) - len(p) >= 2:
            return word[: -len(p)]
    return word


def tokenize_ko(text: str) -> list[str]:
    """권장: 단어 + 조사를 뗀 어간."""
    out: list[str] = []
    for w in _WORD.findall(text.lower()):
        out.append(w)
        s = stem_ko(w) if _HANGUL.search(w) else w
        if s != w:
            out.append(s)
    return out


def tokenize_ngram(text: str, ngram: int = 2) -> list[str]:
    """비교용(부정 결과): 단어 + 한글 단어의 글자 n-gram."""
    tokens: list[str] = []
    for word in _WORD.findall(text.lower()):
        tokens.append(word)
        if len(word) > ngram and _HANGUL.search(word):
            tokens.extend(word[i:i + ngram] for i in range(len(word) - ngram + 1))
    return tokens


class KoBM25Retriever:
    """BM25Retriever 와 같은 규격. 토크나이저만 바꿀 수 있다."""

    def __init__(self, documents: Iterable[KnowledgeDocument], k1: float = 1.5, b: float = 0.75,
                 tokenizer: Callable[[str], list[str]] = tokenize_ko):
        self.documents = list(documents)
        self.k1, self.b, self.tokenizer = k1, b, tokenizer
        self._tokens = [tokenizer(d.content) for d in self.documents]
        self._term_freqs = [Counter(t) for t in self._tokens]
        self._doc_freq: Counter[str] = Counter()
        for tokens in self._tokens:
            self._doc_freq.update(set(tokens))
        self._avgdl = sum(len(t) for t in self._tokens) / len(self._tokens) if self._tokens else 0.0

    def search(self, query: str, limit: int = 5) -> list[RetrievalHit]:
        if not self.documents:
            return []
        query_tokens = self.tokenizer(query)
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
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]
