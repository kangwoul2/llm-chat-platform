import pytest

from app.rag.retrieval import BM25Retriever, KnowledgeDocument
from app.rag.service import GroundedChatService
from app.rag.store import KnowledgeStore


class StubLLM:
    async def generate(self, message: str):
        return "grounded-answer", 1.0


def test_bm25_ranks_matching_document_first():
    retriever = BM25Retriever([
        KnowledgeDocument("queue", "bounded queue worker backpressure", "queue.md"),
        KnowledgeDocument("db", "postgres transaction isolation index", "db.md"),
    ])
    hits = retriever.search("queue backpressure")
    assert hits
    assert hits[0].document.document_id == "queue"


@pytest.mark.asyncio
async def test_grounding_guard_blocks_unsupported_question():
    store = KnowledgeStore([
        KnowledgeDocument("queue", "bounded queue worker backpressure", "queue.md"),
    ])
    service = GroundedChatService(store, StubLLM(), min_score=0.5)
    result = await service.answer("오늘 점심 메뉴가 뭐야?")
    assert result.grounded is False
    assert result.sources == []


@pytest.mark.asyncio
async def test_grounded_answer_keeps_sources():
    store = KnowledgeStore([
        KnowledgeDocument("queue", "bounded queue worker backpressure", "queue.md"),
    ])
    service = GroundedChatService(store, StubLLM(), min_score=0.1)
    result = await service.answer("queue backpressure")
    assert result.grounded is True
    assert result.sources == ["queue.md"]
