# tests/test_assembler.py

import pytest
import tempfile
import os
from datetime import datetime, timezone
from munk.store import MunkStore
from munk.models import Source
from munk.ids import new_id
from munk.hashing import hash_content
from munk.chunker import chunkify
from munk.editor import edit_chunk
from munk.assembler import assemble

def test_full_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        store = MunkStore(tmp)
        
        # 1. Setup Source
        original_content = "line1\n\nline2\n"
        src_id = new_id("src")
        src = Source(
            source_id=src_id, path="test.txt", hash=hash_content(original_content),
            size_bytes=len(original_content), mime_type="text/plain",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        store.save_source(src)
        
        # 2. Chunkify
        manifest = chunkify(src, original_content, store)
        assert len(manifest.order) == 2
        
        # 3. Edit one chunk
        first_chunk_id = manifest.order[0]
        edit_chunk(first_chunk_id, "modified line1\n\n", store, actor="agent_007")
        
        # 4. Assemble
        export_path = assemble(manifest.manifest_id, "exported.txt", store)
        
        # 5. Verify
        exported_content = export_path.read_text()
        assert exported_content == "modified line1\n\n\nline2\n"
