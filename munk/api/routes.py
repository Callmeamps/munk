# munk/api/routes.py

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
from datetime import datetime, timezone

from munk.store import MunkStore
from munk.models import Source
from munk.ids import new_id
from munk.hashing import hash_content
from munk.chunker import chunkify
from munk.editor import edit_chunk, EditError
from munk.locker import lock_chunk, unlock_chunk, LockError
from munk.assembler import assemble, AssemblyError
from munk.validator import ValidationError

app = FastAPI(title="Munk API", version="0.1.0")
store = MunkStore(os.getenv("MUNK_DATA_ROOT", "munk_data"))

# ── Request/Response models ──────────────────────────────────────────────────

class CreateSourceRequest(BaseModel):
    path: str
    mime_type: str
    content: str
    origin: str = "local"

class ChunkifyRequest(BaseModel):
    author_agent: str = "user"

class EditChunkRequest(BaseModel):
    content: str
    description: str = ""
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    actor: str = "user"
    note: str = ""

class LockRequest(BaseModel):
    owner: str
    reason: str = ""

class UnlockRequest(BaseModel):
    owner: str

class ExportRequest(BaseModel):
    output_filename: str

# ── Routes ───────────────────────────────────────────────────────────────────

@app.post("/sources", status_code=201)
def create_source(req: CreateSourceRequest):
    source_id = new_id("src")
    source = Source(
        source_id  = source_id,
        path       = req.path,
        hash       = hash_content(req.content),
        size_bytes = len(req.content.encode("utf-8")),
        mime_type  = req.mime_type,
        created_at = datetime.now(timezone.utc).isoformat(),
        origin     = req.origin,
        status     = "locked",
    )
    store.save_source(source)
    # Save raw content for the chunker
    content_path = store.root / "sources" / f"{source_id}.content"
    content_path.write_text(req.content, encoding="utf-8")
    return {"source_id": source_id, "status": "locked"}

@app.post("/sources/{source_id}/chunkify", status_code=201)
def chunkify_source(source_id: str, req: ChunkifyRequest):
    if not store.source_exists(source_id):
        raise HTTPException(404, f"Source {source_id} not found.")
    
    source = store.load_source(source_id)
    content_path = store.root / "sources" / f"{source_id}.content"
    content = content_path.read_text(encoding="utf-8")
    
    manifest = chunkify(source, content, store, author_agent=req.author_agent)
    return {"manifest_id": manifest.manifest_id, "chunk_ids": manifest.order}

@app.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: str):
    if not store.chunk_exists(chunk_id):
        raise HTTPException(404, f"Chunk {chunk_id} not found.")
    return store.load_chunk(chunk_id).to_dict()

@app.patch("/chunks/{chunk_id}")
def patch_chunk(chunk_id: str, req: EditChunkRequest):
    try:
        updated = edit_chunk(
            chunk_id    = chunk_id,
            new_content = req.content,
            store       = store,
            actor       = req.actor,
            description = req.description,
            tags        = req.tags,
            status      = req.status,
            note        = req.note,
        )
        return updated.to_dict()
    except EditError as e:
        raise HTTPException(409, str(e))

@app.post("/chunks/{chunk_id}/lock")
def lock(chunk_id: str, req: LockRequest):
    try:
        lock_obj = lock_chunk(chunk_id, req.owner, store, req.reason)
        return lock_obj.to_dict()
    except LockError as e:
        raise HTTPException(409, str(e))

@app.post("/chunks/{chunk_id}/unlock")
def unlock(chunk_id: str, req: UnlockRequest):
    try:
        unlock_chunk(chunk_id, req.owner, store)
        return {"status": "unlocked"}
    except LockError as e:
        raise HTTPException(409, str(e))

@app.post("/manifests/{manifest_id}/export")
def export(manifest_id: str, req: ExportRequest):
    try:
        path = assemble(manifest_id, req.output_filename, store)
        return {"output_path": str(path)}
    except (AssemblyError, ValidationError) as e:
        raise HTTPException(422, str(e))

# ── Static Files ─────────────────────────────────────────────────────────────

@app.get("/")
def read_index():
    return FileResponse("web/index.html")

app.mount("/static", StaticFiles(directory="web/static"), name="static")
