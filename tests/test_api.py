# tests/test_api.py

from fastapi.testclient import TestClient
from munk.api.routes import app
from munk.store import MunkStore
import shutil
import os

client = TestClient(app)

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
