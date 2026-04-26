# tests/test_chunk_store_adapter.py
"""Tests for ChunkStore adapter - verify behavior, not internals."""
import pytest
import tempfile
from datetime import datetime, timezone
from munk.store import MunkStore
from munk.adapters.chunk_store_adapter import ChunkStore
from munk.models import Chunk
from munk.hashing import hash_content


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        yield MunkStore(tmp)


@pytest.fixture
def chunk_store(store):
    return ChunkStore(store)


@pytest.fixture
def sample_chunk():
    return Chunk(
        chunk_id="chk_1",
        source_id="src_1",
        content="Hello world",
        content_hash=hash_content("Hello world"),
        version=1,
        status="draft",
        created_at=_now(),
        updated_at=_now(),
        title="Test",
        description="",
        tags=[],
        author_agent="user",
    )


def test_get_chunk_returns_chunk(chunk_store, store, sample_chunk):
    store.save_chunk(sample_chunk)
    chunk = chunk_store.get_chunk("chk_1")
    assert chunk.chunk_id == "chk_1"
    assert chunk.content == "Hello world"


def test_get_chunk_not_found_raises(chunk_store):
    with pytest.raises(Exception):  # NotFoundError
        chunk_store.get_chunk("nonexistent")


def test_save_chunk_stores_chunk(chunk_store, store, sample_chunk):
    chunk_store.save_chunk(sample_chunk)
    assert store.chunk_exists("chk_1")
    loaded = store.load_chunk("chk_1")
    assert loaded.content == "Hello world"


def test_chunk_exists_true(chunk_store, store, sample_chunk):
    store.save_chunk(sample_chunk)
    assert chunk_store.chunk_exists("chk_1")


def test_chunk_exists_false(chunk_store):
    assert not chunk_store.chunk_exists("nonexistent")


def test_clone_chunk_creates_new_chunk(chunk_store, store, sample_chunk):
    store.save_chunk(sample_chunk)
    new_chunk = chunk_store.clone_chunk("chk_1")
    assert new_chunk.chunk_id != "chk_1"
    assert new_chunk.source_id == sample_chunk.source_id
    assert new_chunk.content == sample_chunk.content
    assert new_chunk.version == 1
    assert new_chunk.status == "draft"
    assert new_chunk.parent_chunk_id == "chk_1"


def test_clone_chunk_with_new_content(chunk_store, store, sample_chunk):
    store.save_chunk(sample_chunk)
    new_chunk = chunk_store.clone_chunk("chk_1", new_content="Modified content")
    assert new_chunk.content == "Modified content"
    assert new_chunk.content_hash == hash_content("Modified content")


def test_archive_chunk_sets_status(chunk_store, store, sample_chunk):
    store.save_chunk(sample_chunk)
    archived = chunk_store.archive_chunk("chk_1")
    assert archived.status == "archived"
    # Verify persistence
    reloaded = store.load_chunk("chk_1")
    assert reloaded.status == "archived"


def test_list_chunks(chunk_store, store, sample_chunk):
    assert chunk_store.list_chunks() == []
    store.save_chunk(sample_chunk)
    assert chunk_store.list_chunks() == ["chk_1"]
