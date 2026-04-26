# munk/adapters/chunk_history_adapter.py
"""
ChunkHistory Adapter - a seam with behavior-focused methods for audit logging.

Exposes log_edit(), log_split(), log_merge().
Hides ChunkHistory construction details from callers.
"""
from typing import Optional
from munk.models import ChunkHistory
from munk.store import MunkStore
from munk.ids import new_id
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChunkHistoryAdapter:
    """Adapter for ChunkHistory operations with behavior-focused methods."""

    def __init__(self, store: MunkStore):
        self._store = store

    def log_edit(
        self,
        chunk_id: str,
        version: int,
        actor: str,
        note: str = "",
        diff_ref: Optional[str] = None,
    ) -> ChunkHistory:
        """
        Log an edit action to a chunk's history.
        Returns the created ChunkHistory entry.
        """
        entry = ChunkHistory(
            history_id=new_id("hist"),
            chunk_id=chunk_id,
            version=version,
            action="edit",
            timestamp=_now(),
            actor=actor,
            diff_ref=diff_ref,
            note=note,
        )
        self._store.append_history(entry)
        return entry

    def log_split(
        self,
        parent_chunk_id: str,
        new_chunk_ids: list[str],
        actor: str,
        note: str = "",
    ) -> list[ChunkHistory]:
        """
        Log a split action. Creates history entries for parent and new chunks.
        Returns list of created ChunkHistory entries.
        """
        entries = []
        now = _now()

        # Log split on parent
        parent_entry = ChunkHistory(
            history_id=new_id("hist"),
            chunk_id=parent_chunk_id,
            version=0,  # Version not incremented for split
            action="split",
            timestamp=now,
            actor=actor,
            note=note,
        )
        self._store.append_history(parent_entry)
        entries.append(parent_entry)

        # Log create for each new chunk
        for new_id_str in new_chunk_ids:
            create_entry = ChunkHistory(
                history_id=new_id("hist"),
                chunk_id=new_id_str,
                version=1,
                action="create",
                timestamp=now,
                actor=actor,
                note=f"Created via split of {parent_chunk_id}",
            )
            self._store.append_history(create_entry)
            entries.append(create_entry)

        return entries

    def log_merge(
        self,
        source_chunk_ids: list[str],
        merged_chunk_id: str,
        actor: str,
        note: str = "",
    ) -> list[ChunkHistory]:
        """
        Log a merge action. Creates history entries for source chunks and merged chunk.
        Returns list of created ChunkHistory entries.
        """
        entries = []
        now = _now()

        # Log merge on source chunks
        for src_id in source_chunk_ids:
            src_entry = ChunkHistory(
                history_id=new_id("hist"),
                chunk_id=src_id,
                version=0,
                action="merge",
                timestamp=now,
                actor=actor,
                note=note or f"Merged into {merged_chunk_id}",
            )
            self._store.append_history(src_entry)
            entries.append(src_entry)

        # Log create for merged chunk
        merged_entry = ChunkHistory(
            history_id=new_id("hist"),
            chunk_id=merged_chunk_id,
            version=1,
            action="create",
            timestamp=now,
            actor=actor,
            note=note or f"Created by merging {', '.join(source_chunk_ids)}",
        )
        self._store.append_history(merged_entry)
        entries.append(merged_entry)

        return entries

    def log_lock(
        self,
        chunk_id: str,
        actor: str,
        note: str = "",
    ) -> ChunkHistory:
        """Log a lock action."""
        entry = ChunkHistory(
            history_id=new_id("hist"),
            chunk_id=chunk_id,
            version=0,
            action="lock",
            timestamp=_now(),
            actor=actor,
            note=note,
        )
        self._store.append_history(entry)
        return entry

    def log_unlock(
        self,
        chunk_id: str,
        actor: str,
        note: str = "",
    ) -> ChunkHistory:
        """Log an unlock action."""
        entry = ChunkHistory(
            history_id=new_id("hist"),
            chunk_id=chunk_id,
            version=0,
            action="unlock",
            timestamp=_now(),
            actor=actor,
            note=note,
        )
        self._store.append_history(entry)
        return entry

    def get_history(self, chunk_id: str) -> list[ChunkHistory]:
        """Get all history entries for a chunk."""
        return self._store.load_history(chunk_id)
