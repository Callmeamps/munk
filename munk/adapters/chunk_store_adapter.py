# munk/adapters/chunk_store_adapter.py
"""
ChunkStore adapter provides a behavior-focused interface for chunk persistence.

Hides persistence details (file paths, JSON serialization) from callers.
Exposes domain-focused methods like clone_chunk() and archive_chunk().
"""
from typing import Optional
from munk.models import Chunk
from munk.store import MunkStore


class ChunkStore:
    """Adapter for chunk persistence with behavior-focused methods."""

    def __init__(self, store: MunkStore):
        self._store = store

    def get_chunk(self, chunk_id: str) -> Chunk:
        """Load a chunk by ID. Raises NotFoundError if not found."""
        return self._store.load_chunk(chunk_id)

    def save_chunk(self, chunk: Chunk) -> None:
        """Save or update a chunk."""
        self._store.save_chunk(chunk)

    def chunk_exists(self, chunk_id: str) -> bool:
        """Check if a chunk exists."""
        return self._store.chunk_exists(chunk_id)

    def clone_chunk(self, chunk_id: str, new_content: Optional[str] = None) -> Chunk:
        """
        Clone a chunk with a new ID. Optionally override content.
        Returns the new chunk with version=1 and status="draft".
        """
        from munk.ids import new_id
        from munk.hashing import hash_content
        from datetime import datetime, timezone

        original = self._store.load_chunk(chunk_id)
        now = datetime.now(timezone.utc).isoformat()

        new_chunk = Chunk(
            chunk_id=new_id("chk"),
            source_id=original.source_id,
            content=new_content if new_content is not None else original.content,
            content_hash=hash_content(new_content if new_content is not None else original.content),
            version=1,
            status="draft",
            created_at=now,
            updated_at=now,
            parent_chunk_id=original.chunk_id,
            title=original.title,
            description=original.description,
            tags=original.tags.copy() if original.tags else [],
            author_agent=original.author_agent,
        )
        self._store.save_chunk(new_chunk)
        return new_chunk

    def archive_chunk(self, chunk_id: str) -> Chunk:
        """
        Archive a chunk by setting its status to 'archived'.
        Returns the updated chunk.
        """
        chunk = self._store.load_chunk(chunk_id)
        chunk.status = "archived"
        from datetime import datetime, timezone
        chunk.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.save_chunk(chunk)
        return chunk

    def list_chunks(self) -> list[str]:
        """List all chunk IDs."""
        return self._store.list_chunks()
