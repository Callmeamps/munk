# munk/locker.py

from datetime import datetime, timezone
from munk.ids import new_id
from munk.models import Lock
from munk.store import MunkStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LockError(Exception):
    """Raised when a lock operation fails."""


def lock_chunk(chunk_id: str, owner: str, store: MunkStore, reason: str = "") -> Lock:
    """
    Acquire a lock on a chunk.

    Raises LockError if the chunk is already locked by someone else.
    """
    existing = store.load_lock(chunk_id)
    if existing is not None:
        raise LockError(
            f"Chunk {chunk_id!r} is already locked by {existing.owner!r}. "
            f"Acquired at {existing.created_at}."
        )
    lock = Lock(
        lock_id    = new_id("lock"),
        chunk_id   = chunk_id,
        owner      = owner,
        created_at = _now(),
        reason     = reason,
    )
    store.save_lock(lock)
    return lock


def unlock_chunk(chunk_id: str, owner: str, store: MunkStore) -> bool:
    """
    Release a lock on a chunk.

    Raises LockError if the chunk is not locked or is locked by a different owner.
    """
    existing = store.load_lock(chunk_id)
    if existing is None:
        raise LockError(f"Chunk {chunk_id!r} is not locked.")
    if existing.owner != owner:
        raise LockError(
            f"Cannot unlock chunk {chunk_id!r}: locked by {existing.owner!r}, "
            f"not {owner!r}."
        )
    store.delete_lock(chunk_id)
    return True
