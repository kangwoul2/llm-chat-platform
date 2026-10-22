from app.rag.retrieval import BM25Retriever, KnowledgeDocument
from doc_chunking import ChunkedKnowledge, chunk_document, split_markdown
from ko_bm25 import KoBM25Retriever, stem_ko, tokenize_ko, tokenize_ngram


def test_tokenizer_matches_across_korean_particles():
    docs = [KnowledgeDocument("a", "세마포어로 외부 호출 수를 제한합니다", "a.md"), KnowledgeDocument("b", "대기열에 작업을 보관합니다", "b.md")]
    query = "세마포어가 왜 필요한가요"
    assert BM25Retriever(docs).search(query) == [], "현재 토크나이저는 '세마포어가' 와 '세마포어로' 를 만나게 하지 못한다"
    hits = KoBM25Retriever(docs).search(query)
    assert hits and hits[0].document.document_id == "a"


def test_stemmer_strips_one_particle_but_not_short_stems():
    assert stem_ko("세마포어가") == "세마포어" and stem_ko("대기열에서는") == "대기열" and stem_ko("호출을") == "호출"
    assert stem_ko("아이") == "아이" and stem_ko("나") == "나", "어간이 2글자 미만이 되면 떼지 않는다"
    toks = tokenize_ko("세마포어로 FastAPI")
    assert "세마포어로" in toks and "세마포어" in toks and "fastapi" in toks


def test_ngram_tokenizer_is_kept_only_as_a_documented_negative_result():
    assert "마포" in tokenize_ngram("세마포어로")


def test_ko_retriever_has_the_same_interface_as_bm25():
    docs = [KnowledgeDocument("a", "queue worker backpressure", "a.md")]
    for cls in (BM25Retriever, KoBM25Retriever):
        hit = cls(docs).search("queue backpressure")[0]
        assert hit.document.document_id == "a" and hit.score > 0
        assert cls([]).search("x") == [] and cls(docs).search("") == []


MD = """# 제목

도입 문장입니다. 이 문서는 예시입니다.

## 첫째 절

첫째 절의 문단 하나입니다. """ + "가나다라 " * 40 + """

둘째 문단입니다. """ + "마바사아 " * 40 + """

## 둘째 절

```python
x = 1

y = 2
```

코드 뒤 문장입니다.
"""


def test_split_keeps_heading_context_and_code_blocks_whole():
    chunks = split_markdown(MD, max_chars=300, min_chars=20)
    assert len(chunks) >= 3
    assert all(c.startswith("[제목") for c in chunks), "조각마다 문서·절 제목 맥락이 붙는다"
    code = [c for c in chunks if "x = 1" in c]
    assert code and "y = 2" in code[0], "코드 블록 안의 빈 줄에서 쪼개지 않는다"
    assert all(len(c) <= 420 for c in chunks)


def test_chunk_ids_are_stable_and_source_stays_the_file():
    doc = KnowledgeDocument("guide", MD, "docs/guide.md")
    a, b = chunk_document(doc, 300), chunk_document(doc, 300)
    assert [c.document_id for c in a] == [c.document_id for c in b]
    assert a[0].document_id == "guide#000" and {c.source for c in a} == {"docs/guide.md"}


def test_reindexing_is_idempotent_and_removes_stale_chunks():
    store = ChunkedKnowledge(max_chars=300)
    long_doc = KnowledgeDocument("guide", MD, "docs/guide.md")
    n1 = store.upsert(long_doc)
    assert store.upsert(long_doc) == n1 and store.size == n1, "같은 문서를 다시 넣어도 조각이 늘지 않는다"
    short = KnowledgeDocument("guide", "# 제목\n\n짧아진 문서입니다. 충분히 긴 문장으로 만들어 둡니다 " * 1, "docs/guide.md")
    n2 = store.upsert(short)
    assert n2 < n1 and store.size == n2
    assert not store.search("가나다라 마바사아"), "문서가 짧아진 뒤 옛 조각이 검색에 남지 않는다"


def test_chunked_store_is_a_drop_in_for_grounded_chat_service():
    import asyncio

    from app.rag.service import GroundedChatService

    class LLM:
        async def generate(self, message):
            return "ok", 1.0

    store = ChunkedKnowledge(max_chars=300)
    store.upsert(KnowledgeDocument("guide", MD, "docs/guide.md"))
    svc = GroundedChatService(store, LLM(), min_score=0.1)
    res = asyncio.run(svc.answer("둘째 문단 마바사아"))
    assert res.grounded and res.sources == ["docs/guide.md"]
