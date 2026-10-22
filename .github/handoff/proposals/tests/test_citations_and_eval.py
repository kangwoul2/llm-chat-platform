from pathlib import Path

import pytest

from app.rag.retrieval import KnowledgeDocument
from app.rag.store import KnowledgeStore
from app.services.concurrency import LLMConcurrencyLimiter
from citations import CitingChatService, build_prompt, parse_numbers, resolve_citations
from rag_eval.harness import (answer_files, best_threshold, load_corpus, load_questions, norm, threshold_sweep)

ROOT = Path(__file__).resolve().parents[4]


class ScriptedLLM:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    async def generate(self, message):
        self.prompts.append(message)
        return self.reply, 1.0


def store():
    return KnowledgeStore([
        KnowledgeDocument("q", "bounded queue worker backpressure", "queue.md"),
        KnowledgeDocument("s", "semaphore limits concurrent llm calls", "semaphore.md"),
        KnowledgeDocument("d", "postgres transaction isolation", "db.md"),
    ])


async def test_only_cited_sources_are_returned():
    llm = ScriptedLLM("큐 설명 [근거 1]")
    svc = CitingChatService(store(), llm, min_score=0.1)
    res = await svc.answer_with_citations("queue backpressure semaphore")
    assert res.sources == ["queue.md"] or res.sources == ["semaphore.md"]
    assert len(res.retrieved_sources) >= 2 and len(res.sources) == 1, "검색된 건 여러 개여도 인용한 것만 sources"
    assert res.notice is None


async def test_invalid_numbers_are_removed_and_uncited_answers_are_flagged():
    svc = CitingChatService(store(), ScriptedLLM("설명 [근거 9]"), min_score=0.1)
    res = await svc.answer_with_citations("queue backpressure")
    assert res.invalid_numbers == [9] and "[근거 9]" not in res.answer
    assert res.sources == [] and res.notice == "답변에 인용된 근거가 없습니다."


async def test_low_score_still_blocks_before_calling_the_llm():
    llm = ScriptedLLM("x")
    res = await CitingChatService(store(), llm, min_score=0.5).answer_with_citations("오늘 점심 메뉴가 뭐야?")
    assert res.grounded is False and llm.prompts == []


async def test_the_existing_limiter_is_used_unchanged():
    class Counting(LLMConcurrencyLimiter):
        entered = 0

        async def __aenter__(self):
            type(self).entered += 1
            return await super().__aenter__()

    svc = CitingChatService(store(), ScriptedLLM("답 [근거 1]"), min_score=0.1, limiter=Counting(1))
    await svc.answer_with_citations("queue")
    assert Counting.entered == 1


def test_prompt_numbers_every_evidence_and_guards_against_injected_instructions():
    hits = store().search("queue semaphore", limit=3)
    p = build_prompt("질문", hits)
    assert "[근거 1]" in p and "[근거 2]" in p and "따르지 말고" in p


def test_parse_numbers_handles_lists_and_ranges():
    assert parse_numbers("1, 3") == [1, 3] and parse_numbers("2~4") == [2, 3, 4]
    assert resolve_citations("a [근거 1][근거 2, 3] b", store().search("queue semaphore db postgres", limit=3)).cited_numbers == [1, 2, 3]


# ── 평가 세트가 스스로 정직한가 ─────────────────────────────────────────────
@pytest.mark.skipif(not (ROOT / "docs").is_dir(), reason="docs/ 가 없는 환경")
def test_every_gold_phrase_exists_in_the_corpus():
    corpus = load_corpus(ROOT / "docs")
    qs = load_questions()
    for q in (q for q in qs if q.answerable):
        files = answer_files(q, corpus)
        assert files, f"{q.id}: 정답 문구가 코퍼스 어디에도 없다 → {q.phrase}"
        if q.expected_file:
            assert q.expected_file in files, f"{q.id}: expected_file 에 정답 문구가 없다"
    assert sum(not q.answerable for q in qs) >= 5


def test_threshold_math():
    rows = threshold_sweep([3.0, 4.0], [0.5, 1.0], [2.0])
    assert rows[0]["allowed"] == 1.0 and rows[0]["blocked"] == 1.0
    best = best_threshold([3.0, 4.0], [0.5, 2.5])
    assert 2.5 < best["threshold"] <= 3.0 and best["balanced"] == 1.0


def test_norm_ignores_spacing():
    assert norm("최소 3회  반복") == norm("최소3회 반복")
