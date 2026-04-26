import pytest
from munk.store import MunkStore
from munk.locker import lock_chunk, unlock_chunk, LockError
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
    store = MunkStore(str(tmp_path))
    _make_chunk(store)
    lock = lock_chunk("chk_123", "alice", store, "editing")
    assert lock.chunk_id == "chk_123"
    assert lock.owner == "alice"
    assert store.is_locked("chk_123")


def test_lock_chunk_already_locked(tmp_path):
    store = MunkStore(str(tmp_path))
    _make_chunk(store)
    lock_chunk("chk_123", "alice", store)
    with pytest.raises(LockError):
        lock_chunk("chk_123", "bob", store)


def test_unlock_chunk_success(tmp_path):
    store = MunkStore(str(tmp_path))
    _make_chunk(store)
    lock_chunk("chk_123", "alice", store)
    unlock_chunk("chk_123", "alice", store)
    assert not store.is_locked("chk_123")


def test_unlock_chunk_wrong_owner(tmp_path):
    store = MunkStore(str(tmp_path))
    _make_chunk(store)
    lock_chunk("chk_123", "alice", store)
    with pytest.raises(LockError):
        unlock_chunk("chk_123", "bob", store)


def test_unlock_chunk_not_locked(tmp_path):
    store = MunkStore(str(tmp_path))
    _make_chunk(store)
    with pytest.raises(LockError):
        unlock_chunk("chk_123", "alice", store)
