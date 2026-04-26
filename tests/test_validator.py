import pytest
from munk.validator import validate_manifest, validate_chunk, ValidationError
from munk.models import Chunk, Manifest, Source
from munk.hashing import hash_content


def _make_chunk(store, chunk_id="chk_1", source_id="src_1"):
    content = "test content"
    chunk = Chunk(
        chunk_id=chunk_id,
        source_id=source_id,
        content=content,
        content_hash=hash_content(content),
        version=1,
        status="draft",
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
    )
    store.save_chunk(chunk)
    return chunk


def _make_manifest_with_chunks(store, chunk_ids, source_id="src_1"):
    manifest = Manifest(
        manifest_id="man_1",
        source_id=source_id,
        chunks=chunk_ids,
        order=chunk_ids,
        created_at="2024-01-01T00:00:00+00:00",
    )
    store.save_manifest(manifest)
    return manifest


def test_validate_success(tmp_path):
    from munk.store import MunkStore
    from munk.models import Source
    store = MunkStore(str(tmp_path))
    # Create source first
    source = Source(
        source_id="src_1",
        path="test.txt",
        hash="hash",
        size_bytes=100,
        mime_type="text/plain",
        created_at="2024-01-01T00:00:00+00:00",
        origin="local",
        status="locked"
    )
    store.save_source(source)
    _make_chunk(store)
    manifest = _make_manifest_with_chunks(store, ["chk_1"])
    result = validate_manifest(manifest, store)
    assert len(result) == 1


def test_validate_missing_chunk(tmp_path):
    from munk.store import MunkStore
    from munk.models import Source
    store = MunkStore(str(tmp_path))
    source = Source(
        source_id="src_1",
        path="test.txt",
        hash="hash",
        size_bytes=100,
        mime_type="text/plain",
        created_at="2024-01-01T00:00:00+00:00",
        origin="local",
        status="locked"
    )
    store.save_source(source)
    _make_manifest_with_chunks(store, ["nonexistent_chk"])
    with pytest.raises(ValidationError):
        manifest = store.load_manifest("man_1")
        validate_manifest(manifest, store)


def test_validate_chunk_hash_mismatch(tmp_path):
    from munk.store import MunkStore
    from munk.models import Source
    store = MunkStore(str(tmp_path))
    source = Source(
        source_id="src_1",
        path="test.txt",
        hash="hash",
        size_bytes=100,
        mime_type="text/plain",
        created_at="2024-01-01T00:00:00+00:00",
        origin="local",
        status="locked"
    )
    store.save_source(source)
    chunk = Chunk(
        chunk_id="chk_1",
        source_id="src_1",
        content="test content",
        content_hash="wrong_hash",
        version=1,
        status="draft",
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
    )
    store.save_chunk(chunk)
    with pytest.raises(ValidationError):
        validate_chunk(chunk, store)


def test_validate_chunk_archived(tmp_path):
    from munk.store import MunkStore
    from munk.models import Source
    store = MunkStore(str(tmp_path))
    source = Source(
        source_id="src_1",
        path="test.txt",
        hash="hash",
        size_bytes=100,
        mime_type="text/plain",
        created_at="2024-01-01T00:00:00+00:00",
        origin="local",
        status="locked"
    )
    store.save_source(source)
    chunk = Chunk(
        chunk_id="chk_1",
        source_id="src_1",
        content="test content",
        content_hash=hash_content("test content"),
        version=1,
        status="archived",
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
    )
    store.save_chunk(chunk)
    with pytest.raises(ValidationError):
        validate_chunk(chunk, store)


# The test_validate_missing_manifest was removed as it's not applicable with the new API
# validate_manifest takes a Manifest object, not a string ID
