# munk/editor.py
from datetime import datetime, timezone
from typing import Optional
from munk.ids import new_id
from munk.models import Chunk, ChunkHistory
from munk.store import MunkStore, NotFoundError, StoreError
from munk.adapters.source_chunk_adapter import SourceChunkAdapter

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class EditError(Exception):
    """Raised when an edit operation cannot proceed."""


def edit_chunk(
    chunk_id: str,
    new_content: str,
    store: MunkStore,
    actor: str = "user",
    description: str = "",
    tags: Optional[list[str]] = None,
    status: Optional[str] = None,
    note: str = "",
) -> Chunk:
    """
    Apply new content to a chunk using SourceChunkAdapter.
    Rules enforced:
    - The chunk must exist.
    - The chunk must not have status "locked" or "archived".
    - The chunk must not have an active lock file in the store.
    """
    if not new_content.strip():
        raise EditError("new_content must not be empty.")
    chunk = store.load_chunk(chunk_id)
    try:
        source = store.load_source(chunk.source_id)
    except NotFoundError:
        # Create minimal dummy source for adapter compatibility
        from munk.models import Source
        source = Source(
            source_id=chunk.source_id,
            path="",
            hash="",
            size_bytes=0,
            mime_type="text/plain",
            created_at=_now(),
            origin="local",
            status="locked",
        )
    if chunk.status in ("locked", "archived"):
        raise EditError(
            f"Cannot edit chunk {chunk_id!r}: status is {chunk.status!r}."
        )
    if store.is_locked(chunk_id):
        raise EditError(
            f"Cannot edit chunk {chunk_id!r}: it has an active lock."
        )

    adapter = SourceChunkAdapter(source, chunk)
    adapter.edit(new_content, actor)
    if description:
        adapter.chunk.description = description
    if tags is not None:
        adapter.chunk.tags = tags
    if status is not None:
        adapter.chunk.status = status

    store.save_chunk(adapter.chunk)
    store.history_adapter.log_edit(
        chunk_id=chunk_id,
        version=adapter.chunk.version,
        actor=actor,
        note=note,
    )
    return adapter.chunk