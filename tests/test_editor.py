# tests/test_editor.py

import pytest
import tempfile
from munk.store import MunkStore
from munk.models import Chunk, _now
from munk.hashing import hash_content
from munk.editor import edit_chunk, EditError

def test_edit_chunk_success():
    with tempfile.TemporaryDirectory() as tmp:
        store = MunkStore(tmp)
        content = "original"
        cid = "chk_1"
        chunk = Chunk(
            chunk_id=cid, source_id="src_1", content=content,
            content_hash=hash_content(content), version=1,
            status="draft", created_at=_now(), updated_at=_now()
        )
        store.save_chunk(chunk)
        
        updated = edit_chunk(cid, "new content", store, actor="agent_x")
        
        assert updated.version == 2
        assert updated.content == "new content"
        assert updated.author_agent == "agent_x"
        
        history = store.load_history(cid)
        assert len(history) == 1
        assert history[0].version == 2

def test_edit_locked_chunk_fails():
    with tempfile.TemporaryDirectory() as tmp:
        store = MunkStore(tmp)
        content = "original"
        cid = "chk_1"
        chunk = Chunk(
            chunk_id=cid, source_id="src_1", content=content,
            content_hash=hash_content(content), version=1,
            status="draft", created_at=_now(), updated_at=_now()
        )
        store.save_chunk(chunk)
        
        store.lock_adapter.acquire(cid, owner="user_1")
        
        with pytest.raises(EditError, match="active lock"):
            edit_chunk(cid, "new content", store)
