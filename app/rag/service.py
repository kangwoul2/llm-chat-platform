from __future__ import annotations

from dataclasses import dataclass

from app.rag.store import KnowledgeStore
from app.services.concurrency import LLMConcurrencyLimiter
from app.services.llm_client import LLMClient


@dataclass(frozen=True)
class GroundedAnswer:
    answer: str
    grounded: bool
    sources: list[str]
    top_score: float | None
    llm_ms: float | None


class GroundedChatService:
    def __init__(self, store: KnowledgeStore, llm: LLMClient, min_score: float = 0.55,
                 limiter: LLMConcurrencyLimiter | None = None):
        self.store = store
        self.llm = llm
        self.min_score = min_score
        self.limiter = limiter

    async def answer(self, question: str) -> GroundedAnswer:
        hits = self.store.search(question, limit=4)
        top_score = hits[0].score if hits else None
        if not hits or top_score is None or top_score < self.min_score:
            return GroundedAnswer(
                answer="등록된 지식에서 질문을 뒷받침할 근거를 찾지 못했습니다.",
                grounded=False,
                sources=[],
                top_score=top_score,
                llm_ms=None,
            )

        context = "\n\n".join(
            f"[source={hit.document.source}]\n{hit.document.content}" for hit in hits
        )
        prompt = (
            "아래 컨텍스트만 근거로 답하세요. 근거가 부족하면 모른다고 답하세요.\n\n"
            f"Context:\n{context}\n\nQuestion: {question}"
        )
        if self.limiter is None:
            answer, llm_ms = await self.llm.generate(prompt)
        else:
            async with self.limiter:
                answer, llm_ms = await self.llm.generate(prompt)
        return GroundedAnswer(
            answer=answer,
            grounded=True,
            sources=list(dict.fromkeys(hit.document.source for hit in hits)),
            top_score=top_score,
            llm_ms=llm_ms,
        )
