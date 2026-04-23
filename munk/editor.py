# munk/editor.py

from datetime import datetime, timezone
from typing import Optional

from munk.hashing import hash_content, verify_content
from munk.ids import new_id
from munk.models import Chunk, ChunkHistory
from munk.store import MunkStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EditError(Exception):
    """Raised when an edit operation cannot proceed."""


def edit_chunk(
    chunk_id:    str,
    new_content: str,
    store:       MunkStore,
    actor:       str          = "user",
    description: str          = "",
    tags:        Optional[list[str]] = None,
    status:      Optional[str] = None,
    note:        str          = "",
) -> Chunk:
    """
    Apply new content to a chunk.

    Rules enforced:
    - The chunk must exist.
    - The chunk must not have status "locked" or "archived".
    - The chunk must not have an active lock file in the store.
    - Version increments, hash is updated, and history is written.
    """
    if not new_content.strip():
        raise EditError("new_content must not be empty.")

    chunk = store.load_chunk(chunk_id)

    if chunk.status in ("locked", "archived"):
        raise EditError(
            f"Cannot edit chunk {chunk_id!r}: status is {chunk.status!r}."
        )

    if store.is_locked(chunk_id):
        raise EditError(
            f"Cannot edit chunk {chunk_id!r}: it has an active lock."
        )

    now = _now()
    new_hash = hash_content(new_content)

    updated = Chunk(
        chunk_id        = chunk.chunk_id,
        source_id       = chunk.source_id,
        content         = new_content,
        content_hash    = new_hash,
        version         = chunk.version + 1,
        status          = status if status is not None else chunk.status,
        created_at      = chunk.created_at,
        updated_at      = now,
        parent_chunk_id = chunk.parent_chunk_id,
        title           = chunk.title,
        description     = description if description else chunk.description,
        tags            = tags if tags is not None else chunk.tags,
        author_agent    = actor,
    )

    store.save_chunk(updated)

    history = ChunkHistory(
        history_id = new_id("hist"),
        chunk_id   = chunk_id,
        version    = updated.version,
        action     = "edit",
        timestamp  = now,
        actor      = actor,
        diff_ref   = None,
        note       = note,
    )
    store.append_history(history)

    return updated
