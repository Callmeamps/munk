# tests/test_lock_adapter.py
"""Tests for LockAdapter - verify behavior, not internals."""
import pytest
import tempfile
from munk.store import MunkStore
from munk.adapters.lock_adapter import LockAdapter, LockError
from munk.models import Lock


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        yield MunkStore(tmp)


@pytest.fixture
def lock_adapter(store):
    return LockAdapter(store)


def test_acquire_creates_lock(lock_adapter, store):
    """acquire() should create a lock for the chunk."""
    lock = lock_adapter.acquire("chk_1", "user_1", reason="editing")
    assert lock.chunk_id == "chk_1"
    assert lock.owner == "user_1"
    assert lock.reason == "editing"
    # Verify persistence
    assert store.is_locked("chk_1")


def test_acquire_fails_if_already_locked(lock_adapter):
    """acquire() should raise LockError if chunk already locked."""
    lock_adapter.acquire("chk_1", "user_1")
    with pytest.raises(LockError):
        lock_adapter.acquire("chk_1", "user_2")


def test_release_removes_lock(lock_adapter, store):
    """release() should remove the lock."""
    lock_adapter.acquire("chk_1", "user_1")
    assert store.is_locked("chk_1")
    
    result = lock_adapter.release("chk_1", "user_1")
    assert result is True
    assert not store.is_locked("chk_1")


def test_release_fails_if_not_locked(lock_adapter):
    """release() should raise LockError if chunk not locked."""
    with pytest.raises(LockError):
        lock_adapter.release("chk_1", "user_1")


def test_release_fails_if_wrong_owner(lock_adapter):
    """release() should raise LockError if released by different owner."""
    lock_adapter.acquire("chk_1", "user_1")
    with pytest.raises(LockError):
        lock_adapter.release("chk_1", "user_2")


def test_is_locked_returns_true_if_locked(lock_adapter):
    """is_locked() should return True if chunk is locked."""
    assert lock_adapter.is_locked("chk_1") is False
    lock_adapter.acquire("chk_1", "user_1")
    assert lock_adapter.is_locked("chk_1") is True


def test_is_locked_returns_false_if_not_locked(lock_adapter):
    """is_locked() should return False if chunk is not locked."""
    assert lock_adapter.is_locked("chk_1") is False


def test_get_lock_returns_lock_if_locked(lock_adapter):
    """get_lock() should return the Lock object if chunk is locked."""
    lock = lock_adapter.acquire("chk_1", "user_1", reason="test")
    retrieved = lock_adapter.get_lock("chk_1")
    assert retrieved is not None
    assert retrieved.owner == "user_1"
    assert retrieved.reason == "test"


def test_get_lock_returns_none_if_not_locked(lock_adapter):
    """get_lock() should return None if chunk is not locked."""
    assert lock_adapter.get_lock("chk_1") is None
