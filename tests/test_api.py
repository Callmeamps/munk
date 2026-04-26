# tests/test_api.py

from fastapi.testclient import TestClient
from munk.api.routes import app
from munk.store import MunkStore
import shutil
import os

client = TestClient(app)

def test_chunkify_content_hash_mismatch_warns():
    import os
    # Create source
    res = client.post("/sources", json={
        "path": "hash_test.txt",
        "mime_type": "text/plain",
        "content": "original content"
    })
    assert res.status_code == 201
    source_id = res.json()["source_id"]
    # Modify content file
    content_path = os.path.join("munk_data", "sources", f"{source_id}.content")
    with open(content_path, "w") as f:
        f.write("modified content")
    # Chunkify should still work (warning logged)
    res = client.post(f"/sources/{source_id}/chunkify", json={})
    assert res.status_code == 201


def test_get_nonexistent_chunk_returns_404():
    res = client.get("/chunks/nonexistent_id")
    assert res.status_code == 404


def test_chunkify_nonexistent_source_returns_404():
    res = client.post("/sources/nonexistent_id/chunkify", json={})
    assert res.status_code == 404


def test_edit_nonexistent_chunk_returns_404():
    res = client.patch("/chunks/nonexistent_id", json={"content": "test"})
    assert res.status_code == 404


def test_export_nonexistent_manifest_returns_422():
    res = client.post("/manifests/nonexistent_id/export", json={"output_filename": "test.txt"})
    assert res.status_code == 422


def test_chunkify_missing_content_returns_404():
    # Create a source first
    res = client.post("/sources", json={
        "path": "missing_content.txt",
        "mime_type": "text/plain",
        "content": "test"
    })
    assert res.status_code == 201
    source_id = res.json()["source_id"]
    # Delete the content file
    import os
    content_path = os.path.join("munk_data", "sources", f"{source_id}.content")
    if os.path.exists(content_path):
        os.remove(content_path)
    # Try to chunkify
    res = client.post(f"/sources/{source_id}/chunkify", json={})
    assert res.status_code == 404


def test_api_workflow():
    # Use default munk_data for API test to match module initialization
    # but ensure it exists
    if not os.path.exists("munk_data"):
        os.makedirs("munk_data")
    
    # 1. Create Source
    res = client.post("/sources", json={
        "path": "api_test.txt",
        "mime_type": "text/plain",
        "content": "line1\n\nline2"
    })
    assert res.status_code == 201
    source_id = res.json()["source_id"]
    
    # 2. Chunkify
    res = client.post(f"/sources/{source_id}/chunkify", json={})
    assert res.status_code == 201
    manifest_id = res.json()["manifest_id"]
    chunk_ids = res.json()["chunk_ids"]
    assert len(chunk_ids) == 2
    
    # 3. Edit Chunk
    res = client.patch(f"/chunks/{chunk_ids[0]}", json={
        "content": "modified line1\n\n"
    })
    assert res.status_code == 200
    assert res.json()["version"] == 2
    
    # 4. Export
    res = client.post(f"/manifests/{manifest_id}/export", json={
        "output_filename": "api_export.txt"
    })
    assert res.status_code == 200
    assert "api_export.txt" in res.json()["output_path"]
