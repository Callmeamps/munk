# munk/adapters/lock_adapter.py
"""
Lock Adapter - a seam with behavior-focused methods for lock management.

Exposes acquire(), release(), is_locked().
Centralizes lock lifecycle logic and hides persistence details.
"""
from munk.models import Lock
from munk.store import MunkStore
from munk.ids import new_id
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LockAdapter:
    """Adapter for lock management with behavior-focused methods."""

    def __init__(self, store: MunkStore):
        self._store = store

    def acquire(self, chunk_id: str, owner: str, reason: str = "") -> Lock:
        """
        Acquire a lock on a chunk.
        Raises LockError if already locked.
        Returns the created Lock.
        """
        existing = self._store.load_lock(chunk_id)
        if existing is not None:
            raise LockError(
                f"Chunk {chunk_id!r} is already locked by {existing.owner!r}. "
                f"Acquired at {existing.created_at}."
            )
        lock = Lock(
            lock_id=new_id("lock"),
            chunk_id=chunk_id,
            owner=owner,
            created_at=_now(),
            reason=reason,
        )
        self._store.save_lock(lock)
        return lock

    def release(self, chunk_id: str, owner: str) -> bool:
        """
        Release a lock on a chunk.
        Raises LockError if not locked or locked by different owner.
        Returns True on success.
        """
        existing = self._store.load_lock(chunk_id)
        if existing is None:
            raise LockError(f"Chunk {chunk_id!r} is not locked.")
        if existing.owner != owner:
            raise LockError(
                f"Cannot unlock chunk {chunk_id!r}: locked by {existing.owner!r}, "
                f"not {owner!r}."
            )
        self._store.delete_lock(chunk_id)
        return True

    def is_locked(self, chunk_id: str) -> bool:
        """Check if a chunk is locked."""
        return self._store.is_locked(chunk_id)

    def get_lock(self, chunk_id: str) -> Lock:
        """Get the lock for a chunk. Returns None if not locked."""
        return self._store.load_lock(chunk_id)


class LockError(Exception):
    """Raised when a lock operation fails."""
