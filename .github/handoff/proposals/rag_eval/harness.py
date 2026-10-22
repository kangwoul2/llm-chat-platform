"""RAG 검색 평가 하네스 — 네트워크·LLM 없이 검색과 '근거 판정 기준값'만 잰다 (제안, 기존 코드는 수정하지 않음).

왜 필요한가
  tests/test_retrieval.py 의 RAG 테스트는 3개이고 모두 문서 1~2개짜리다. "검색이 좋아졌다"를 말할 숫자가 없다.
  또 rag_min_score=0.55 는 BM25 점수에 대한 절대값이라 문서 묶음·토크나이저가 바뀌면 의미가 달라진다.

무엇을 재나
  답할 수 있는 질문(answerable)
    hit@1 / hit@3   상위 k 개 결과 안에 '정답 문구를 담은 문서'가 있는가 (파일 단위)
    answer_hit@3    상위 3개 결과의 *본문*에 정답 문구가 들어 있는가 (조각으로 쪼갠 쪽이 더 엄격하다)
    MRR             정답 문서가 처음 나온 순위의 역수 평균
    context_chars   상위 3개 결과의 본문 글자 수 평균 (LLM 컨텍스트 크기의 대리 지표 — 낮을수록 싸다)
  답할 수 없는 질문(unanswerable)
    근거 판정 기준값(threshold)별로 '막았다/통과시켰다' 를 센다. 기준값 스윕 표를 만든다.

정답 문서는 사람이 파일명을 적지 않고, '정답 문구(phrase)를 실제로 담은 파일들'로 자동 계산한다.
(여러 문서에 같은 설명이 있어도 억울하게 틀린 것으로 세지 않기 위해)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.rag.retrieval import BM25Retriever, KnowledgeDocument, RetrievalHit
from app.rag.store import KnowledgeStore

HERE = Path(__file__).resolve().parent
_WS = re.compile(r"\s+")


def norm(text: str) -> str:
    return _WS.sub("", text).lower()


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    phrase: str | None = None
    expected_file: str | None = None

    @property
    def answerable(self) -> bool:
        return self.phrase is not None


def load_questions(path: Path | None = None) -> list[Question]:
    path = path or HERE / "questions.jsonl"
    return [Question(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_corpus(docs_dir: Path) -> list[KnowledgeDocument]:
    return [KnowledgeDocument(document_id=p.stem, content=p.read_text(encoding="utf-8"), source=p.name)
            for p in sorted(docs_dir.glob("*.md"))]


def answer_files(q: Question, corpus: list[KnowledgeDocument]) -> set[str]:
    """정답 문구를 실제로 담은 파일들."""
    return {d.source for d in corpus if q.phrase and norm(q.phrase) in norm(d.content)}


Search = Callable[[str, int], list[RetrievalHit]]


@dataclass
class Variant:
    name: str
    search: Search
    note: str = ""


def whole_file_variant(corpus: list[KnowledgeDocument], retriever_cls=BM25Retriever, name="") -> Variant:
    store = KnowledgeStore(corpus)          # 현재 코드 경로 (파일 하나 = 문서 하나)
    if retriever_cls is not BM25Retriever:
        store._retriever = retriever_cls(corpus)
    return Variant(name, lambda q, k: store.search(q, limit=k))


@dataclass
class Metrics:
    n: int
    hit1: float
    hit3: float
    answer_hit3: float
    mrr: float
    context_chars: float


def evaluate(variant: Variant, questions: list[Question], corpus: list[KnowledgeDocument]) -> Metrics:
    rows = [q for q in questions if q.answerable]
    h1 = h3 = a3 = rr = ctx = 0.0
    for q in rows:
        good = answer_files(q, corpus)
        hits = variant.search(q.question, 10)
        files = [h.document.source for h in hits]
        h1 += bool(files[:1] and files[0] in good)
        h3 += any(f in good for f in files[:3])
        a3 += any(norm(q.phrase) in norm(h.document.content) for h in hits[:3])
        rank = next((i for i, f in enumerate(files, start=1) if f in good), None)
        rr += 1 / rank if rank else 0.0
        ctx += sum(len(h.document.content) for h in hits[:3])
    n = len(rows)
    return Metrics(n, h1 / n, h3 / n, a3 / n, rr / n, ctx / n)


def top_scores(variant: Variant, questions: list[Question]) -> tuple[list[float], list[float]]:
    """(답할 수 있는 질문들의 1위 점수, 답할 수 없는 질문들의 1위 점수). 결과가 없으면 0."""
    pos, neg = [], []
    for q in questions:
        hits = variant.search(q.question, 1)
        (pos if q.answerable else neg).append(hits[0].score if hits else 0.0)
    return pos, neg


def threshold_sweep(pos: list[float], neg: list[float], thresholds: list[float]) -> list[dict]:
    """기준값 t 에서 '점수 >= t 면 근거 있음'으로 볼 때 통과/차단 정확도."""
    rows = []
    for t in thresholds:
        allowed = sum(s >= t for s in pos) / len(pos)        # 답할 수 있는 질문을 통과시킨 비율 (높을수록 좋다)
        blocked = sum(s < t for s in neg) / len(neg)         # 답할 수 없는 질문을 막은 비율 (높을수록 좋다)
        rows.append({"threshold": t, "allowed": allowed, "blocked": blocked, "balanced": (allowed + blocked) / 2})
    return rows


def best_threshold(pos: list[float], neg: list[float]) -> dict:
    """관측된 점수들 사이의 중간값 후보 중 균형 정확도가 가장 높은 기준값 (동률이면 낮은 쪽)."""
    scores = sorted(set(pos + neg))
    cands = [0.0] + [(a + b) / 2 for a, b in zip(scores, scores[1:])] + [scores[-1] + 1e-6]
    rows = threshold_sweep(pos, neg, cands)
    return max(rows, key=lambda r: (round(r["balanced"], 6), -r["threshold"]))
