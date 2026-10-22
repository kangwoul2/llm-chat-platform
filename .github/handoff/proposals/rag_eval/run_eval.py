"""RAG 검색 평가 실행. 결과 표를 출력하고 results.md 로 저장한다.

    # 저장소 루트에서
    PYTHONPATH=.:.github/handoff/proposals python .github/handoff/proposals/rag_eval/run_eval.py
    PYTHONPATH=.:.github/handoff/proposals python .github/handoff/proposals/rag_eval/run_eval.py --docs docs --out /tmp/results.md

비교하는 네 가지
  A  파일 통째 + 현재 토크나이저          ← 지금 main 의 동작 (KnowledgeStore.from_directory 와 같은 경로)
  B  조각(청크) + 현재 토크나이저
  C  파일 통째 + 조사 떼기(ko_bm25.tokenize_ko)
  D  조각(청크) + 조사 떼기          ← 제안
  E  파일 통째 + 글자 2-gram          ← 처음 제안했다가 측정 후 버린 안
"""
from __future__ import annotations

import argparse
import platform
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(ROOT))

from doc_chunking import ChunkedKnowledge  # noqa: E402
from rag_eval.harness import (Variant, best_threshold, evaluate, load_corpus, load_questions, threshold_sweep,  # noqa: E402
                     top_scores, whole_file_variant)
from ko_bm25 import KoBM25Retriever, tokenize_ngram  # noqa: E402

from app.rag.retrieval import BM25Retriever  # noqa: E402


def chunked_variant(corpus, retriever_cls, name) -> Variant:
    store = ChunkedKnowledge(retriever_factory=lambda docs: retriever_cls(docs))
    store.upsert_many(corpus)
    return Variant(name, lambda q, k: store.search(q, limit=k), note=f"{store.size}조각")


def build_variants(corpus) -> list[Variant]:
    return [
        whole_file_variant(corpus, BM25Retriever, "A 파일 통째 + 현재 토크나이저 (현재 main)"),
        chunked_variant(corpus, BM25Retriever, "B 조각 + 현재 토크나이저"),
        whole_file_variant(corpus, KoBM25Retriever, "C 파일 통째 + 조사 떼기"),
        chunked_variant(corpus, KoBM25Retriever, "D 조각 + 조사 떼기 (제안)"),
        whole_file_variant(corpus, lambda docs: KoBM25Retriever(docs, tokenizer=tokenize_ngram), "E 파일 통째 + 2-gram (버린 안)"),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs", default=str(ROOT / "docs"))
    ap.add_argument("--questions", default=str(HERE / "questions.jsonl"))
    ap.add_argument("--out", default=str(HERE / "results.md"))
    ap.add_argument("--min-score", type=float, default=0.55, help="현재 설정의 근거 판정 기준값")
    args = ap.parse_args()

    corpus = load_corpus(Path(args.docs))
    questions = load_questions(Path(args.questions))
    answerable = [q for q in questions if q.answerable]
    variants = build_variants(corpus)

    lines = [
        "# RAG 검색 평가 결과\n",
        f"> 실행 {date.today()} · Python {platform.python_version()} · {platform.system()} · 코퍼스 `{Path(args.docs).name}/*.md` {len(corpus)}개 파일 · "
        f"질문 {len(answerable)}개(답 있음) + {len(questions) - len(answerable)}개(답 없음) · LLM·네트워크 호출 없음\n",
        "## 1. 검색 품질\n",
        "| 구성 | hit@1 | hit@3 | 정답 문구 포함@3 | MRR | 상위3 컨텍스트(글자) |", "|---|---|---|---|---|---|",
    ]
    results = {}
    for v in variants:
        m = evaluate(v, questions, corpus)
        results[v.name] = m
        lines.append(f"| {v.name}{' · ' + v.note if v.note else ''} | {m.hit1:.0%} | {m.hit3:.0%} | {m.answer_hit3:.0%} | {m.mrr:.3f} | {m.context_chars:,.0f} |")

    lines += ["", "## 2. 근거 판정 기준값 (답 없는 질문을 막고, 답 있는 질문은 통과시키는가)\n",
              f"현재 설정은 `rag_min_score = {args.min_score}` 이다. 구성마다 BM25 점수의 크기가 달라서 같은 기준값이 다른 뜻을 가진다.\n",
              "| 구성 | 답 있는 질문의 1위 점수 (중앙값 · 최소) | 답 없는 질문의 1위 점수 (중앙값 · 최대) | 현재 기준값에서 통과 / 차단 | 균형이 가장 좋은 기준값 → 통과 / 차단 |",
              "|---|---|---|---|---|"]
    for v in variants:
        pos, neg = top_scores(v, questions)
        med = lambda xs: sorted(xs)[len(xs) // 2]  # noqa: E731
        cur = threshold_sweep(pos, neg, [args.min_score])[0]
        best = best_threshold(pos, neg)
        lines.append(f"| {v.name} | {med(pos):.2f} · {min(pos):.2f} | {med(neg):.2f} · {max(neg):.2f} | {cur['allowed']:.0%} / {cur['blocked']:.0%} | "
                     f"{best['threshold']:.2f} → {best['allowed']:.0%} / {best['blocked']:.0%} |")

    lines += ["", "## 3. 기준값 스윕 (구성 A, 현재 main)\n", "| 기준값 | 답 있는 질문 통과 | 답 없는 질문 차단 |", "|---|---|---|"]
    pos, neg = top_scores(variants[0], questions)
    for r in threshold_sweep(pos, neg, [0.55, 1, 2, 3, 4, 5, 6, 8]):
        lines.append(f"| {r['threshold']} | {r['allowed']:.0%} | {r['blocked']:.0%} |")

    lines += ["", "## 4. 틀린 질문 (구성 A 와 D 비교)\n", "| 질문 | A 의 1위 파일 | D 의 1위 파일 | 정답 파일 |", "|---|---|---|---|"]
    for q in answerable:
        from rag_eval.harness import answer_files

        good = answer_files(q, corpus)
        a = variants[0].search(q.question, 1)
        d = variants[3].search(q.question, 1)
        fa = a[0].document.source if a else "(없음)"
        fd = d[0].document.source if d else "(없음)"
        if fa not in good or fd not in good:
            lines.append(f"| {q.question} | {fa}{' ✅' if fa in good else ' ❌'} | {fd}{' ✅' if fd in good else ' ❌'} | {', '.join(sorted(good))} |")

    lines += ["", "## 읽을 때 주의", "",
              "- 질문은 이 저장소의 문서 24개를 보고 사람이 쓴 것이라 문서와 표현이 비슷한 편이다. 실제 사용자 질문의 분포가 아니다.",
              "- 질문이 24 + 6개뿐이라 한 문항이 3~4%p 를 움직인다. 방향을 보는 용도이지 통계적 결론이 아니다.",
              "- 코퍼스는 이 저장소의 `docs/` 다. `data/knowledge/service_guide.md`(8줄) 하나로는 검색 품질을 비교할 수 없어 대신 썼다.",
              "- 기준값은 이 질문·이 코퍼스에서 정한 값이다. 코퍼스가 바뀌면 다시 정해야 한다."]
    out = "\n".join(lines) + "\n"
    Path(args.out).write_text(out, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
