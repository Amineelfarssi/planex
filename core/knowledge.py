"""Knowledge store — LanceDB vector DB, invisible tool that grows silently.

Uses KBChunkMetadata (Pydantic) as the structured schema for all chunks.
Simplified from RAG Fusion to plain vector search — it's a tool, not a showcase.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa
import tiktoken

from core.llm import LLMProvider
from core.models import KBChunkMetadata, DocumentMetadata, KBIngestResult

_ENC = tiktoken.get_encoding("cl100k_base")

# PyArrow schema derived from KBChunkMetadata
SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("text", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 1536)),
    # All KBChunkMetadata fields
    pa.field("chunk_index", pa.int32()),
    pa.field("source", pa.string()),
    pa.field("source_type", pa.string()),
    pa.field("doc_title", pa.string()),
    pa.field("ingested_by", pa.string()),
    pa.field("created_at", pa.string()),
    pa.field("source_date", pa.string()),
    pa.field("tags", pa.string()),       # JSON array
    pa.field("content_type", pa.string()),
    pa.field("language", pa.string()),
    pa.field("file_hash", pa.string()),
    pa.field("token_count", pa.int32()),
])

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt", ".html", ".htm"}
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50


class KnowledgeStore:

    def __init__(self, llm: LLMProvider, db_path: str | None = None) -> None:
        self._llm = llm
        self._db_path = db_path or str(Path.home() / ".planex" / "knowledge.lance")
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(self._db_path)
        self._table = self._get_or_create_table()

    def _get_or_create_table(self) -> Any:
        if "knowledge" in self._db.table_names():
            return self._db.open_table("knowledge")
        empty = pa.table(
            {field.name: pa.array([], type=field.type) for field in SCHEMA},
            schema=SCHEMA,
        )
        return self._db.create_table("knowledge", data=empty)

    def _ensure_fts_index(self) -> None:
        try:
            self._table.create_fts_index("text", language="English", stem=True, replace=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str) -> list[str]:
        tokens = _ENC.encode(text)
        if len(tokens) <= CHUNK_SIZE:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(tokens):
            end = min(start + CHUNK_SIZE, len(tokens))
            chunks.append(_ENC.decode(tokens[start:end]))
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    # ------------------------------------------------------------------
    # File reading
    # ------------------------------------------------------------------

    def _read_file(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        if ext == ".pdf":
            import pymupdf
            doc = pymupdf.open(path)
            return "\n\n".join(page.get_text() for page in doc)
        elif ext in {".html", ".htm"}:
            import trafilatura
            html = Path(path).read_text(encoding="utf-8", errors="replace")
            return trafilatura.extract(html) or ""
        else:
            return Path(path).read_text(encoding="utf-8", errors="replace")

    def _file_hash(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                h.update(block)
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Metadata extraction via structured output
    # ------------------------------------------------------------------

    async def _extract_metadata(self, text_preview: str, source: str) -> DocumentMetadata:
        try:
            return await self._llm.chat_parse(
                messages=[{
                    "role": "user",
                    "content": f"Extract metadata from this document.\n\nSource: {source}\nExcerpt:\n{text_preview[:1000]}",
                }],
                response_model=DocumentMetadata,
                tier="fast",
            )
        except Exception:
            return DocumentMetadata(title=Path(source).stem, tags=[], content_type="notes")

    # ------------------------------------------------------------------
    # Build chunk record using KBChunkMetadata
    # ------------------------------------------------------------------

    def _build_record(
        self,
        text: str,
        embedding: list[float],
        chunk_index: int,
        meta: KBChunkMetadata,
    ) -> dict:
        """Build a LanceDB record from a KBChunkMetadata model."""
        return {
            "id": meta.id,
            "text": text,
            "vector": embedding,
            "chunk_index": meta.chunk_index,
            "source": meta.source,
            "source_type": meta.source_type,
            "doc_title": meta.doc_title,
            "ingested_by": meta.ingested_by,
            "created_at": meta.created_at,
            "source_date": meta.source_date,
            "tags": json.dumps(meta.tags),
            "content_type": meta.content_type,
            "language": meta.language,
            "file_hash": meta.file_hash,
            "token_count": meta.token_count,
        }

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    async def ingest_file(
        self,
        path: str,
        source_type: str = "local_file",
        ingested_by: str = "user_upload",
    ) -> int:
        """Ingest a single file. Returns number of chunks created."""
        fhash = self._file_hash(path)

        # Dedup
        try:
            existing = self._table.search().where(f"file_hash = '{fhash}'").limit(1).to_list()
            if existing:
                return 0
        except Exception:
            pass

        text = self._read_file(path)
        if not text.strip():
            return 0

        chunks = self._chunk_text(text)
        doc_meta = await self._extract_metadata(chunks[0], path)
        embeddings = await self._llm.embed(chunks)
        now = datetime.utcnow().isoformat()

        records = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            chunk_id = hashlib.md5(f"{path}:{i}".encode()).hexdigest()

            meta = KBChunkMetadata(
                id=chunk_id,
                chunk_index=i,
                source=path,
                source_type=source_type,
                doc_title=doc_meta.title,
                ingested_by=ingested_by,
                created_at=now,
                source_date="",
                tags=doc_meta.tags,
                content_type=doc_meta.content_type,
                language="en",
                file_hash=fhash,
                token_count=len(_ENC.encode(chunk)),
            )
            records.append(self._build_record(chunk, emb, i, meta))

        self._table.add(records)
        self._ensure_fts_index()
        return len(records)

    async def ingest_text(
        self,
        text: str,
        source: str,
        source_type: str = "web_page",
        ingested_by: str = "agent",
        title: str = "",
        tags: list[str] | None = None,
    ) -> int:
        """Ingest raw text. Returns chunk count."""
        if not text.strip():
            return 0

        fhash = hashlib.sha256(text.encode()).hexdigest()

        # Dedup
        try:
            existing = self._table.search().where(f"file_hash = '{fhash}'").limit(1).to_list()
            if existing:
                return 0
        except Exception:
            pass

        chunks = self._chunk_text(text)
        embeddings = await self._llm.embed(chunks)
        now = datetime.utcnow().isoformat()

        records = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            chunk_id = hashlib.md5(f"{source}:{i}".encode()).hexdigest()

            meta = KBChunkMetadata(
                id=chunk_id,
                chunk_index=i,
                source=source,
                source_type=source_type,
                doc_title=title or source[:50],
                ingested_by=ingested_by,
                created_at=now,
                source_date="",
                tags=tags or [],
                content_type="article" if source_type == "web_page" else "synthesis",
                language="en",
                file_hash=fhash,
                token_count=len(_ENC.encode(chunk)),
            )
            records.append(self._build_record(chunk, emb, i, meta))

        self._table.add(records)
        self._ensure_fts_index()
        return len(records)

    async def ingest_directory(
        self,
        dir_path: str,
        ingested_by: str = "user_upload",
    ) -> tuple[int, int]:
        total_files = 0
        total_chunks = 0
        for p in sorted(Path(dir_path).rglob("*")):
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                count = await self.ingest_file(str(p), source_type="local_file", ingested_by=ingested_by)
                if count > 0:
                    total_files += 1
                    total_chunks += count
        return total_files, total_chunks

    # ------------------------------------------------------------------
    # Search (simplified — plain vector search, no RAG Fusion)
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        top_k: int = 10,
        source_type: str | None = None,
        **kwargs,
    ) -> list[dict]:
        """Search knowledge base. Simple vector search."""
        try:
            count = self._table.count_rows()
            if count == 0:
                return []
        except Exception:
            return []

        query_embedding = (await self._llm.embed([query]))[0]

        filters = []
        if source_type:
            filters.append(f"source_type = '{source_type}'")
        where_clause = " AND ".join(filters) if filters else None

        try:
            search = self._table.search(query_embedding).limit(top_k)
            if where_clause:
                search = search.where(where_clause)
            return search.to_list()
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        try:
            count = self._table.count_rows()
        except Exception:
            count = 0

        if count == 0:
            return {"documents": 0, "chunks": count, "sources": 0, "tags": []}

        try:
            all_data = self._table.to_arrow()
            sources = len(set(all_data.column("source").to_pylist()))
            source_types: dict[str, int] = defaultdict(int)
            for st in all_data.column("source_type").to_pylist():
                source_types[st] += 1

            tag_counts: dict[str, int] = defaultdict(int)
            for tags_json in all_data.column("tags").to_pylist():
                try:
                    for tag in json.loads(tags_json):
                        tag_counts[tag] += 1
                except Exception:
                    pass
            top_tags = sorted(tag_counts, key=tag_counts.get, reverse=True)[:10]
        except Exception:
            sources = 0
            source_types = {}
            top_tags = []

        return {
            "documents": sources,
            "chunks": count,
            "sources": sources,
            "source_types": dict(source_types),
            "tags": top_tags,
        }

    async def scan_sources_dir(self, sources_dir: str | None = None) -> tuple[int, int]:
        sdir = Path(sources_dir or (Path.home() / ".planex" / "sources"))
        if not sdir.exists():
            sdir.mkdir(parents=True, exist_ok=True)
            return 0, 0
        return await self.ingest_directory(str(sdir), ingested_by="auto_watch")
