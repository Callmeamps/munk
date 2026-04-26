# munk/chunker.py
import json as json_lib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Protocol, runtime_checkable
from munk.chunker_config import get_boundaries, JSON_STRATEGY, SUPPORTED_EXTENSIONS, ChunkingConfig
from munk.hashing import hash_content, hash_file
from munk.ids import new_id
from munk.models import Chunk, Manifest, Source
from munk.store import MunkStore

# Initialize default config
DEFAULT_CONFIG = ChunkingConfig()

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _ext(path: str) -> str:
    return Path(path).suffix.lstrip(".").lower()

# ---------------------------------------------------------------------------
# Strategy Interface
# ---------------------------------------------------------------------------

@runtime_checkable
class ChunkStrategy(Protocol):
    """Interface for chunking strategies."""
    def chunkify(self, source: Source, file_content: str, store: MunkStore, config: ChunkingConfig) -> Manifest:
        """Chunk a source file and return a Manifest."""
        ...

# ---------------------------------------------------------------------------
# Simple Chunker (Baseline)
# ---------------------------------------------------------------------------

class SimpleChunker:
    """Default rule-based chunker."""

    def _scan_lines(self, lines: list[str], boundaries) -> list[list[str]]:
        """Split lines into groups by boundary pattern."""
        groups: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            is_boundary = any(p.match(line) for p in boundaries)
            if is_boundary and current:
                groups.append(current)
                current = []
            current.append(line)
        if current:
            groups.append(current)
        return groups

    def _chunk_json(self, content: str) -> list[str]:
        """Split a JSON object into per-key string chunks."""
        try:
            parsed = json_lib.loads(content)
        except json_lib.JSONDecodeError:
            return [content]
        if not isinstance(parsed, dict):
            return [content]
        return [json_lib.dumps({k: v}, indent=2) for k, v in parsed.items()]

    def _infer_title(self, text: str, ext: str, index: int) -> str:
        """Infer a short title for a chunk from its content."""
        first = next((l.strip() for l in text.splitlines() if l.strip()), "")
        if not first:
            return f"chunk_{index}"
        if ext in ("gd",):
            return first[:80]
        if ext == "md":
            return first.lstrip("#").strip()[:80]
        return first[:60]

    def chunkify(
        self, source: Source, file_content: str, store: MunkStore, config: ChunkingConfig = DEFAULT_CONFIG, author_agent: str = "user"
    ) -> Manifest:
        """Split a source file into Chunk objects and save them to the store."""
        ext = _ext(source.path)
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension: .{ext!r}. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        # Produce raw text groups
        if ext == "json":
            groups = self._chunk_json(file_content)
            raw_chunks = groups  # already strings
        else:
            lines = file_content.splitlines(keepends=True)
            boundaries = get_boundaries(ext)
            line_groups = self._scan_lines(lines, boundaries)
            raw_chunks = ["".join(g) for g in line_groups]

        # Remove empty groups
        raw_chunks = [c for c in raw_chunks if c.strip()]
        now = _now()
        chunk_ids: list[str] = []
        chunks: list[Chunk] = []
        for i, text in enumerate(raw_chunks):
            chunk_id = new_id("chk")
            title = self._infer_title(text, ext, i)
            chunk = Chunk(
                chunk_id=chunk_id,
                source_id=source.source_id,
                content=text,
                content_hash=hash_content(text),
                version=1,
                status="draft",
                created_at=now,
                updated_at=now,
                parent_chunk_id=None,
                title=title,
                description="",
                tags=["simple"],
                author_agent=author_agent,
            )
            chunks.append(chunk)
            chunk_ids.append(chunk_id)

        for chunk in chunks:
            store.save_chunk(chunk)

        manifest = Manifest(
            manifest_id=new_id("man"),
            source_id=source.source_id,
            chunks=chunk_ids,
            order=chunk_ids,
            export_mode="rebuild",
            created_at=now,
        )
        store.save_manifest(manifest)
        return manifest

# ---------------------------------------------------------------------------
# Semantic Chunker
# ---------------------------------------------------------------------------

try:
    from munk.chunkers.semantic_chunker import SemanticChunker
    SEMANTIC_CHUNKER_AVAILABLE = True
except ImportError:
    SEMANTIC_CHUNKER_AVAILABLE = False
    SemanticChunker = None  # type: ignore

# ---------------------------------------------------------------------------
# Factory Function
# ---------------------------------------------------------------------------

def create_chunker(strategy: str = "simple", config: ChunkingConfig = DEFAULT_CONFIG) -> ChunkStrategy:
    """
    Create a chunker instance based on the requested strategy.
    Args:
        strategy: Chunking strategy ("simple", "semantic").
        config: Chunking configuration.
    Returns:
        ChunkStrategy instance.
    """
    if strategy == "semantic" and SEMANTIC_CHUNKER_AVAILABLE:
        return SemanticChunker(config)
    return SimpleChunker()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunkify(
    source: Source,
    file_content: str,
    store: MunkStore,
    strategy: str = "simple",
    config: ChunkingConfig = DEFAULT_CONFIG,
    author_agent: str = "user",
) -> Manifest:
    """
    Split a source file into Chunk objects and save them to the store.
    Args:
        source: Source document.
        file_content: Document content.
        store: MunkStore instance.
        strategy: Chunking strategy ("simple", "semantic").
        config: Chunking configuration.
    Returns:
        Manifest describing the chunks and their order.
    """
    chunker = create_chunker(strategy, config)
    return chunker.chunkify(source, file_content, store, config, author_agent)