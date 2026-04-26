# tests/test_chunk_history_adapter.py
"""Tests for ChunkHistoryAdapter - verify audit behavior, not internals."""
import pytest
import tempfile
from datetime import datetime, timezone
from munk.store import MunkStore
from munk.adapters.chunk_history_adapter import ChunkHistoryAdapter
from munk.models import ChunkHistory


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        yield MunkStore(tmp)


@pytest.fixture
def adapter(store):
    return ChunkHistoryAdapter(store)


def test_log_edit_creates_history_entry(adapter, store):
    """log_edit() should create a history entry with action='edit'."""
    entry = adapter.log_edit(
        chunk_id="chk_1",
        version=2,
        actor="user_1",
        note="Updated content",
    )
    
    assert entry.chunk_id == "chk_1"
    assert entry.version == 2
    assert entry.action == "edit"
    assert entry.actor == "user_1"
    assert entry.note == "Updated content"
    
    # Verify persistence
    history = store.load_history("chk_1")
    assert len(history) == 1
    assert history[0].action == "edit"


def test_log_split_creates_multiple_entries(adapter):
    """log_split() should create entries for parent and new chunks."""
    entries = adapter.log_split(
        parent_chunk_id="chk_1",
        new_chunk_ids=["chk_2", "chk_3"],
        actor="user_1",
        note="Split into two",
    )
    
    assert len(entries) == 3  # parent + 2 new chunks
    assert entries[0].action == "split"
    assert entries[1].action == "create"
    assert entries[2].action == "create"


def test_log_merge_creates_multiple_entries(adapter):
    """log_merge() should create entries for source chunks and merged chunk."""
    entries = adapter.log_merge(
        source_chunk_ids=["chk_1", "chk_2"],
        merged_chunk_id="chk_3",
        actor="user_1",
    )
    
    assert len(entries) == 3  # 2 source + 1 merged
    assert entries[0].action == "merge"
    assert entries[1].action == "merge"
    assert entries[2].action == "create"


def test_log_lock_creates_entry(adapter):
    """log_lock() should create a history entry with action='lock'."""
    entry = adapter.log_lock("chk_1", actor="user_1", note="Locked for editing")
    assert entry.action == "lock"
    assert entry.chunk_id == "chk_1"


def test_log_unlock_creates_entry(adapter):
    """log_unlock() should create a history entry with action='unlock'."""
    entry = adapter.log_unlock("chk_1", actor="user_1")
    assert entry.action == "unlock"
    assert entry.chunk_id == "chk_1"


def test_get_history_returns_all_entries(adapter):
    """get_history() should return all entries for a chunk."""
    adapter.log_edit("chk_1", version=1, actor="user_1")
    adapter.log_edit("chk_1", version=2, actor="user_1")
    
    history = adapter.get_history("chk_1")
    assert len(history) == 2


def test_get_history_returns_empty_list_for_no_history(adapter):
    """get_history() should return empty list if no history exists."""
    history = adapter.get_history("nonexistent")
    assert history == []
