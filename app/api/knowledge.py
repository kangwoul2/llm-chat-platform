from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.observability import RAG_GROUNDED
from app.rag.retrieval import KnowledgeDocument

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class KnowledgeUpsertRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=100_000)
    source: str = Field(default="api", max_length=300)


class KnowledgeQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)


@router.post("/documents", status_code=201)
async def upsert_document(payload: KnowledgeUpsertRequest, request: Request):
    request.app.state.knowledge_store.add(
        KnowledgeDocument(
            document_id=payload.document_id,
            content=payload.content,
            source=payload.source,
        )
    )
    return {"document_id": payload.document_id, "knowledge_size": request.app.state.knowledge_store.size}


@router.post("/query")
async def grounded_query(payload: KnowledgeQueryRequest, request: Request):
    started = time.perf_counter()
    try:
        result = await request.app.state.grounded_chat.answer(payload.question)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="downstream llm error") from exc
    RAG_GROUNDED.labels(str(result.grounded).lower()).inc()
    return {
        "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
        "answer": result.answer,
        "grounded": result.grounded,
        "sources": result.sources,
        "top_score": result.top_score,
        "llm_ms": result.llm_ms,
        "total_ms": (time.perf_counter() - started) * 1000,
    }
