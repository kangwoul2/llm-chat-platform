from __future__ import annotations

from pathlib import Path

from app.rag.retrieval import BM25Retriever, KnowledgeDocument


class KnowledgeStore:
    def __init__(self, documents: list[KnowledgeDocument] | None = None):
        self._documents = documents or []
        self._retriever = BM25Retriever(self._documents)

    @classmethod
    def from_directory(cls, directory: str | Path) -> "KnowledgeStore":
        path = Path(directory)
        documents: list[KnowledgeDocument] = []
        if path.exists():
            for file in sorted(path.rglob("*")):
                if file.is_file() and file.suffix.lower() in {".md", ".txt"}:
                    documents.append(
                        KnowledgeDocument(
                            document_id=file.stem,
                            content=file.read_text(encoding="utf-8"),
                            source=str(file.as_posix()),
                        )
                    )
        return cls(documents)

    @property
    def size(self) -> int:
        return len(self._documents)

    def add(self, document: KnowledgeDocument) -> None:
        self._documents = [doc for doc in self._documents if doc.document_id != document.document_id]
        self._documents.append(document)
        self._retriever = BM25Retriever(self._documents)

    def search(self, query: str, limit: int = 5):
        return self._retriever.search(query, limit=limit)
