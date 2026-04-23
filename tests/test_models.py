# tests/test_models.py

import pytest
from munk.models import Source, Chunk, Manifest, ChunkHistory, Lock, _now
from munk.ids import new_id
from munk.hashing import hash_content

def test_source_model():
    s = Source(
        source_id=new_id("src"),
        path="test.gd",
        hash=hash_content("content"),
        size_bytes=7,
        mime_type="text/x-gdscript",
        created_at=_now()
    )
    d = s.to_dict()
    assert d["source_id"].startswith("src_")
    assert Source.from_dict(d) == s

def test_chunk_model():
    c = Chunk(
        chunk_id=new_id("chk"),
        source_id=new_id("src"),
        content="func _ready():\n    pass",
        content_hash=hash_content("func _ready():\n    pass"),
        version=1,
        status="draft",
        created_at=_now(),
        updated_at=_now()
    )
    assert c.status == "draft"
    with pytest.raises(ValueError):
        Chunk(
            chunk_id="chk_1", source_id="src_1", content="", content_hash="",
            version=1, status="invalid", created_at=_now(), updated_at=_now()
        )

def test_manifest_model():
    cid = new_id("chk")
    m = Manifest(
        manifest_id=new_id("man"),
        source_id=new_id("src"),
        chunks=[cid],
        order=[cid],
        created_at=_now()
    )
    assert m.order == [cid]
    with pytest.raises(ValueError):
        Manifest(
            manifest_id="man_1", source_id="src_1",
            chunks=[cid], order=[], created_at=_now()
        )

def test_history_model():
    h = ChunkHistory(
        history_id=new_id("hist"),
        chunk_id=new_id("chk"),
        version=2,
        action="edit",
        timestamp=_now(),
        actor="agent_007"
    )
    assert h.action == "edit"

def test_lock_model():
    l = Lock(
        lock_id=new_id("lock"),
        chunk_id=new_id("chk"),
        owner="agent_007",
        created_at=_now()
    )
    assert l.owner == "agent_007"
