"""토크나이저 변형 비교 실험 (제안 — 기존 코드는 수정하지 않음).

처음 제안한 글자 2-gram 이 이 코퍼스에서 순위를 떨어뜨렸다. 그래서 더 가벼운 대안들을 같은 질문 세트로 비교해 기본값을 골랐다.

    PYTHONPATH=.:.github/handoff/proposals python .github/handoff/proposals/rag_eval/tokenizer_experiment.py

변형
  현재          공백·기호로만 자름 (main 의 tokenize)
  조사 떼기+원형  단어와, 끝의 흔한 조사를 뗀 어간을 함께 색인   ← ko_bm25.tokenize_ko (채택)
  조사 떼기만    어간만 색인
  앞 3글자+원형   한글 단어의 앞 3글자(어간 근사)를 함께 색인
  2-gram+원형    ko_bm25.tokenize_ngram (버림)

주의: 질문 24개를 한 사람이 문서를 보고 썼고, 조사 목록도 그 뒤에 골랐다. 과적합 가능성이 있다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE.parent), str(ROOT)]

from doc_chunking import ChunkedKnowledge  # noqa: E402
from ko_bm25 import KoBM25Retriever, stem_ko, tokenize_ko, tokenize_ngram  # noqa: E402
from rag_eval.harness import Variant, best_threshold, evaluate, load_corpus, load_questions, top_scores  # noqa: E402

WORD = re.compile(r"[0-9A-Za-z가-힣_]+")


def tok_current(text: str) -> list[str]:
    return WORD.findall(text.lower())


def tok_stem_only(text: str) -> list[str]:
    return [stem_ko(w) for w in WORD.findall(text.lower())]


def tok_prefix3_plus_original(text: str) -> list[str]:
    out: list[str] = []
    for w in WORD.findall(text.lower()):
        out.append(w)
        if len(w) > 3 and re.search("[가-힣]", w):
            out.append(w[:3])
    return out


TOKENIZERS = {
    "현재 (공백·기호)": tok_current,
    "조사 떼기+원형 (채택)": tokenize_ko,
    "조사 떼기만": tok_stem_only,
    "앞 3글자+원형": tok_prefix3_plus_original,
    "2-gram+원형 (버림)": tokenize_ngram,
}


def main() -> int:
    corpus = load_corpus(ROOT / "docs")
    questions = load_questions()
    lines = ["| 토크나이저 | 단위 | hit@1 | hit@3 | MRR | 상위3 컨텍스트(글자) | 균형 기준값 → 통과 / 차단 |", "|---|---|---|---|---|---|---|"]
    for name, tok in TOKENIZERS.items():
        for kind in ("파일 통째", "조각"):
            if kind == "파일 통째":
                r = KoBM25Retriever(corpus, tokenizer=tok)
                v = Variant(name, lambda q, k, r=r: r.search(q, k))
            else:
                store = ChunkedKnowledge(retriever_factory=lambda docs, tok=tok: KoBM25Retriever(docs, tokenizer=tok))
                store.upsert_many(corpus)
                v = Variant(name, lambda q, k, s=store: s.search(q, limit=k))
            m = evaluate(v, questions, corpus)
            pos, neg = top_scores(v, questions)
            b = best_threshold(pos, neg)
            lines.append(f"| {name} | {kind} | {m.hit1:.0%} | {m.hit3:.0%} | {m.mrr:.3f} | {m.context_chars:,.0f} | {b['threshold']:.2f} → {b['allowed']:.0%} / {b['blocked']:.0%} |")
    out = "\n".join(lines) + "\n"
    (HERE / "tokenizer_results.md").write_text("# 토크나이저 변형 비교\n\n" + out, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
