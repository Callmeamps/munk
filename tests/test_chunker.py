# tests/test_chunker.py

import pytest
from munk.store import MunkStore
from munk.models import Source
from munk.ids import new_id
from munk.hashing import hash_content
from munk.chunker import chunkify
from datetime import datetime, timezone
import tempfile

def test_chunkify_gd():
    with tempfile.TemporaryDirectory() as tmp:
        store = MunkStore(tmp)
        content = "# Player.gd\nextends Node\n\nfunc _ready():\n    pass\n\nfunc _process(delta):\n    pass\n"
        src = Source(
            source_id=new_id("src"),
            path="player.gd",
            hash=hash_content(content),
            size_bytes=len(content),
            mime_type="text/x-gdscript",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        store.save_source(src)
        
        manifest = chunkify(src, content, store)
        assert len(manifest.order) == 3
        
        chunks = [store.load_chunk(cid) for cid in manifest.order]
        assert "extends Node" in chunks[0].content
        assert "func _ready()" in chunks[1].content
        assert "func _process" in chunks[2].content

def test_chunkify_json():
     with tempfile.TemporaryDirectory() as tmp:
        store = MunkStore(tmp)
        content = '{"name": "Munk", "version": 1}'
        src = Source(
            source_id=new_id("src"),
            path="config.json",
            hash=hash_content(content),
            size_bytes=len(content),
            mime_type="application/json",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        store.save_source(src)
        
        manifest = chunkify(src, content, store)
        assert len(manifest.order) == 2
