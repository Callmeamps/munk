import json
import pytest
from pathlib import Path
from munk.store import MunkStore, NotFoundError, CorruptedError
from munk.models import Source


def test_load_source_not_found(tmp_path):
    store = MunkStore(str(tmp_path))
    with pytest.raises(NotFoundError):
        store.load_source("nonexistent_id")


def test_load_source_corrupted(tmp_path):
    store = MunkStore(str(tmp_path))
    corrupted_file = tmp_path / "sources" / "src_123.json"
    corrupted_file.write_text("{invalid json}")
    with pytest.raises(CorruptedError):
        store.load_source("src_123")


def test_load_chunk_not_found(tmp_path):
    store = MunkStore(str(tmp_path))
    with pytest.raises(NotFoundError):
        store.load_chunk("nonexistent_id")


def test_load_manifest_not_found(tmp_path):
    store = MunkStore(str(tmp_path))
    with pytest.raises(NotFoundError):
        store.load_manifest("nonexistent_id")


def test_load_valid_source(tmp_path):
    store = MunkStore(str(tmp_path))
    source = Source(
        source_id="src_123",
        path="test.txt",
        hash="test_hash",
        size_bytes=100,
        mime_type="text/plain",
        created_at="2024-01-01T00:00:00+00:00",
        origin="local",
        status="locked"
    )
    store.save_source(source)
    loaded = store.load_source("src_123")
    assert loaded.source_id == "src_123"
