"""Tests for lock operations - now using LockAdapter.

These tests verify behavior through the adapter interface.
"""
import pytest
import tempfile
from munk.store import MunkStore
from munk.adapters.lock_adapter import LockAdapter, LockError
from munk.models import Chunk


def _make_chunk(store, chunk_id="chk_123"):
    chunk = Chunk(
        chunk_id=chunk_id,
        source_id="src_1",
        content="test",
        content_hash="hash",
        version=1,
        status="draft",
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
    )
    store.save_chunk(chunk)
    return chunk


def test_lock_chunk_success(tmp_path):
    """lock_chunk success - now uses LockAdapter.acquire()."""
    store = MunkStore(str(tmp_path))
    _make_chunk(store)
    adapter = LockAdapter(store)
    lock = adapter.acquire("chk_123", "alice", reason="editing")
    assert lock.chunk_id == "chk_123"
    assert lock.owner == "alice"
    assert store.is_locked("chk_123")


def test_lock_chunk_already_locked(tmp_path):
    """lock_chunk fails if already locked - now uses LockAdapter."""
    store = MunkStore(str(tmp_path))
    _make_chunk(store)
    adapter = LockAdapter(store)
    adapter.acquire("chk_123", "alice")
    with pytest.raises(LockError):
        adapter.acquire("chk_123", "bob")


def test_unlock_chunk_success(tmp_path):
    """unlock_chunk success - now uses LockAdapter.release()."""
    store = MunkStore(str(tmp_path))
    _make_chunk(store)
    adapter = LockAdapter(store)
    adapter.acquire("chk_123", "alice")
    adapter.release("chk_123", "alice")
    assert not store.is_locked("chk_123")


def test_unlock_chunk_wrong_owner(tmp_path):
    """unlock_chunk fails if wrong owner - now uses LockAdapter."""
    store = MunkStore(str(tmp_path))
    _make_chunk(store)
    adapter = LockAdapter(store)
    adapter.acquire("chk_123", "alice")
    with pytest.raises(LockError):
        adapter.release("chk_123", "bob")


def test_unlock_chunk_not_locked(tmp_path):
    """unlock_chunk fails if not locked - now uses LockAdapter."""
    store = MunkStore(str(tmp_path))
    _make_chunk(store)
    adapter = LockAdapter(store)
    with pytest.raises(LockError):
        adapter.release("chk_123", "alice")
