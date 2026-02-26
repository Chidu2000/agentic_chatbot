from __future__ import annotations

from pathlib import Path
from typing import Iterable

from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from chatbot.config import settings
from chatbot.models import build_embeddings


class PolicyVectorStore:
    def __init__(self) -> None:
        self.embeddings = build_embeddings()
        self.vectordb = Chroma(
            collection_name="policy_documents",
            embedding_function=self.embeddings,
            persist_directory=str(settings.chroma_persist_dir),
        )

    def ingest_pdfs(self, pdf_paths: Iterable[str]) -> int:
        splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
        chunks = []

        for pdf_path in pdf_paths:
            path = Path(pdf_path)
            if not path.exists() or path.suffix.lower() != ".pdf":
                continue
            loader = PyPDFLoader(str(path))
            pages = loader.load()
            chunks.extend(splitter.split_documents(pages))

        if not chunks:
            return 0

        self.vectordb.add_documents(chunks)
        if hasattr(self.vectordb, "persist"):
            self.vectordb.persist()
        return len(chunks)

    def search(self, query: str, k: int = 4) -> str:
        docs = self.vectordb.similarity_search(query, k=k)
        if not docs:
            return "No relevant policy content found."
        return "\n\n".join([doc.page_content for doc in docs])

    def search_with_sources(self, query: str, k: int = 4) -> tuple[str, list[str]]:
        docs = self.vectordb.similarity_search(query, k=k)
        if not docs:
            return "No relevant policy content found.", []

        context_blocks = []
        citations = []
        citation_map: dict[tuple[str, str], str] = {}
        for idx, doc in enumerate(docs, start=1):
            source = Path(str(doc.metadata.get("source", "unknown_source"))).name
            page = int(doc.metadata.get("page", -1)) + 1 if "page" in doc.metadata else "unknown"
            key = (source, str(page))
            citation_id = citation_map.get(key)
            if citation_id is None:
                citation_id = f"C{len(citation_map) + 1}"
                citation_map[key] = citation_id
                citations.append(f"[{citation_id}] {source}, page {page}")
            context_blocks.append(
                f"[{citation_id}] Source: {source}, page {page}\n{doc.page_content}"
            )

        return "\n\n".join(context_blocks), citations
