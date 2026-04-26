# munk/adapters/source_chunk_adapter.py
"""
SourceChunkAdapter encapsulates the relationship between Source and Chunk.
It exposes a deep interface for working with Chunk content (e.g., edit(), split(), validate())
while hiding implementation details like content_hash, version, and status.
"""
from __future__ import annotations
from dataclasses import asdict
from typing import Optional
from ..models import Chunk, Source
from ..hashing import compute_content_hash

def _compute_content_hash(content: str) -> str:
    """Compute the content hash for a given string."""
    return compute_content_hash(content)

class SourceChunkAdapter:
    """Adapts Source and Chunk to provide a behavior-focused interface."""

    def __init__(self, source: Source, chunk: Optional[Chunk] = None):
        """
        Initialize the adapter with a Source and optional Chunk.
        If no Chunk is provided, a new one is created.
        """
        self.source = source
        self.chunk = chunk or Chunk(
            chunk_id=f"chk_{self._generate_id()}",
            source_id=source.source_id,
            content="",
            content_hash=_compute_content_hash(""),
            version=1,
            status="draft",
            created_at=self._now(),
            updated_at=self._now(),
        )

    @staticmethod
    def _generate_id() -> str:
        """Generate a unique ID for a Chunk."""
        import secrets
        return secrets.token_hex(3)

    @staticmethod
    def _now() -> str:
        """Return the current timestamp in ISO 8601 UTC."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def edit(self, new_content: str, actor: str = "user") -> None:
        """Edit the Chunk's content and update metadata."""
        self.chunk.content = new_content
        self.chunk.content_hash = _compute_content_hash(new_content)
        self.chunk.version += 1
        self.chunk.updated_at = self._now()
        self.chunk.author_agent = actor

    def split(self, split_points: list[int], actor: str = "user") -> list[SourceChunkAdapter]:
        """
        Split the Chunk into multiple Chunks at the given byte offsets.
        Returns a list of new SourceChunkAdapters for the split Chunks.
        """
        chunks = []
        content = self.chunk.content
        prev_point = 0

        for i, point in enumerate(split_points):
            chunk_content = content[prev_point:point]
            chunk = Chunk(
                chunk_id=f"chk_{self._generate_id()}",
                source_id=self.source.source_id,
                content=chunk_content,
                content_hash=_compute_content_hash(chunk_content),
                version=1,
                status="draft",
                created_at=self._now(),
                updated_at=self._now(),
                parent_chunk_id=self.chunk.chunk_id,
                start=prev_point,
                end=point,
                title=f"Split {i+1} from {self.chunk.title}" if self.chunk.title else "",
                author_agent=actor,
            )
            chunks.append(SourceChunkAdapter(self.source, chunk))
            prev_point = point

        # Add the remaining content
        chunk_content = content[prev_point:]
        chunk = Chunk(
            chunk_id=f"chk_{self._generate_id()}",
            source_id=self.source.source_id,
            content=chunk_content,
            content_hash=_compute_content_hash(chunk_content),
            version=1,
            status="draft",
            created_at=self._now(),
            updated_at=self._now(),
            parent_chunk_id=self.chunk.chunk_id,
            start=prev_point,
            end=len(content),
            title=f"Split {len(split_points)+1} from {self.chunk.title}" if self.chunk.title else "",
            author_agent=actor,
        )
        chunks.append(SourceChunkAdapter(self.source, chunk))

        # Archive the original chunk
        self.edit("", actor)
        self.chunk.status = "archived"
        self.chunk.updated_at = self._now()

        return chunks

    def validate(self) -> bool:
        """Validate the Chunk's content_hash matches its content."""
        return self.chunk.content_hash == _compute_content_hash(self.chunk.content)

    def to_dict(self) -> dict:
        """Return the Chunk as a dictionary."""
        return asdict(self.chunk)

    def to_json(self) -> str:
        """Return the Chunk as a JSON string."""
        import json
        return json.dumps(self.to_dict(), indent=2)