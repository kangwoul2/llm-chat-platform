"""문서를 쪼개 색인하는 저장소 (제안 — 기존 코드는 수정하지 않음).

문제
  KnowledgeStore.from_directory() 는 파일 하나를 통째로 문서 하나로 본다.
  질문과 관련된 문단이 한 줄뿐이어도 파일 전체가 LLM 컨텍스트로 들어간다.
  또 KnowledgeStore.add() 는 같은 document_id 를 통째로 바꾸므로, 조각 단위로 쓰려면 ID 규칙이 필요하다.

제안
  1. 마크다운 제목(#, ##, ###) 경계로 자르고, 긴 절은 문단 단위로 max_chars 안에 묶는다. 코드 블록은 쪼개지 않는다.
  2. 청크 ID 는 "{문서ID}#{순번}" 으로 고정한다. 다시 색인해도 같은 ID 가 같은 자리에 덮어써진다.
  3. 문서를 다시 넣을 때 그 문서의 옛 청크를 모두 지운 뒤 새로 넣는다. (문서가 짧아지면 남는 옛 조각이 검색에 섞이지 않게)
  4. 청크의 source 는 원본 파일 그대로 둔다. GroundedChatService 가 돌려주는 sources 는 파일 단위 그대로다.

사용
  store = ChunkedKnowledge()
  store.upsert(KnowledgeDocument("guide", text, "docs/guide.md"))
  GroundedChatService(store, llm, ...)       # store.search(question, limit=4) 규격이 같다
"""
from __future__ import annotations

import re
from typing import Callable, Iterable

from app.rag.retrieval import BM25Retriever, KnowledgeDocument, RetrievalHit

_HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_FENCE = re.compile(r"^```")


def split_markdown(content: str, max_chars: int = 700, min_chars: int = 60) -> list[str]:
    """제목 경계 → 문단 순으로 자른다. 각 조각 앞에 '문서 제목 > 절 제목' 맥락을 한 줄 붙인다."""
    sections: list[tuple[list[str], list[str]]] = []   # (제목 경로, 본문 줄)
    path: list[str] = []
    body: list[str] = []
    in_fence = False
    for line in content.splitlines():
        if _FENCE.match(line.strip()):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            if body:
                sections.append((list(path), body))
            level = len(m.group(1))
            path = path[: level - 1] + [m.group(2)]
            body = []
        else:
            body.append(line)
    if body:
        sections.append((list(path), body))

    chunks: list[str] = []
    for heading, lines in sections:
        text = "\n".join(lines).strip()
        if not text:
            continue
        context = " > ".join(heading)
        for piece in _pack_paragraphs(text, max_chars):
            chunks.append(f"[{context}]\n{piece}" if context else piece)
    # 너무 짧은 조각은 앞 조각에 붙인다 (제목만 있는 절 등)
    merged: list[str] = []
    for c in chunks:
        if merged and len(c) < min_chars:
            merged[-1] += "\n" + c
        else:
            merged.append(c)
    return merged


def _pack_paragraphs(text: str, max_chars: int) -> list[str]:
    """빈 줄로 나눈 문단을 max_chars 안에서 묶는다. 코드 블록(```)은 한 문단으로 취급."""
    paragraphs: list[str] = []
    cur: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line.strip()):
            in_fence = not in_fence
        if not line.strip() and not in_fence:
            if cur:
                paragraphs.append("\n".join(cur))
                cur = []
        else:
            cur.append(line)
    if cur:
        paragraphs.append("\n".join(cur))
    packed: list[str] = []
    buf = ""
    for p in paragraphs:
        if buf and len(buf) + len(p) + 2 > max_chars:
            packed.append(buf)
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        packed.append(buf)
    return packed


def chunk_document(doc: KnowledgeDocument, max_chars: int = 700) -> list[KnowledgeDocument]:
    pieces = split_markdown(doc.content, max_chars)
    return [KnowledgeDocument(document_id=f"{doc.document_id}#{i:03d}", content=p, source=doc.source)
            for i, p in enumerate(pieces)]


class ChunkedKnowledge:
    """KnowledgeStore 와 같은 검색 규격(search)을 가진 청크 저장소."""

    def __init__(self, retriever_factory: Callable[[list[KnowledgeDocument]], object] = BM25Retriever, max_chars: int = 700):
        self._factory = retriever_factory
        self.max_chars = max_chars
        self._chunks: dict[str, list[KnowledgeDocument]] = {}    # 문서ID → 청크들
        self._retriever = retriever_factory([])

    def upsert(self, doc: KnowledgeDocument) -> int:
        """문서 하나를 (다시) 색인한다. 같은 문서의 옛 청크는 모두 지운다. 새 청크 수를 돌려준다."""
        self._chunks[doc.document_id] = chunk_document(doc, self.max_chars)
        self._rebuild()
        return len(self._chunks[doc.document_id])

    def upsert_many(self, docs: Iterable[KnowledgeDocument]) -> None:
        for d in docs:
            self._chunks[d.document_id] = chunk_document(d, self.max_chars)
        self._rebuild()

    def remove(self, document_id: str) -> None:
        self._chunks.pop(document_id, None)
        self._rebuild()

    def _rebuild(self) -> None:
        self._retriever = self._factory([c for chunks in self._chunks.values() for c in chunks])

    @property
    def size(self) -> int:
        return sum(len(c) for c in self._chunks.values())

    @property
    def document_count(self) -> int:
        return len(self._chunks)

    def chunk_ids(self) -> list[str]:
        return [c.document_id for chunks in self._chunks.values() for c in chunks]

    def search(self, query: str, limit: int = 5) -> list[RetrievalHit]:
        return self._retriever.search(query, limit=limit)
