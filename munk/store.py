# munk/store.py

import json
import os
from pathlib import Path
from typing import Optional

from munk.models import Source, Chunk, Manifest, ChunkHistory, Lock


class StoreError(Exception):
    """Base exception for store errors."""
    pass

class NotFoundError(StoreError):
    """Raised when a requested object is not found."""
    pass

class CorruptedError(StoreError):
    """Raised when a stored object's JSON is corrupted."""
    pass


class MunkStore:
    """
    Flat-file JSON store for all Munk objects.

    Layout (relative to data_root):
        sources/    -> {source_id}.json
        chunks/     -> {chunk_id}.json
        manifests/  -> {manifest_id}.json
        history/    -> {chunk_id}/  -> {history_id}.json
        locks/      -> {chunk_id}.lock.json
        exports/    -> (reconstructed files written here)
        diffs/      -> {diff_id}.json
        policies/   -> (policy JSON files, not managed by store)

    All writes are atomic: write to a temp file then rename.
    Sources are write-once — save_source will raise if the file already exists.
    """

    def __init__(self, data_root: str = "munk_data"):
        self.root = Path(data_root)
        self._init_dirs()

    def _init_dirs(self):
        for d in ["sources", "chunks", "manifests", "history", "locks", "exports", "diffs", "policies"]:
            (self.root / d).mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Atomic write helper
    # -----------------------------------------------------------------------

    def _write_json(self, path: Path, data: dict, overwrite: bool = True):
        """Write JSON atomically via a temp file + rename."""
        if not overwrite and path.exists():
            raise FileExistsError(f"File already exists and overwrite=False: {path}")
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.rename(path)

    def _read_json(self, path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise NotFoundError(f"File not found: {path}")
        except json.JSONDecodeError as e:
            raise CorruptedError(f"Corrupted JSON in {path}: {e}")

    # -----------------------------------------------------------------------
    # Source (write-once)
    # -----------------------------------------------------------------------

    def save_source(self, source: Source):
        """Save a source. Raises FileExistsError if source_id already exists."""
        path = self.root / "sources" / f"{source.source_id}.json"
        self._write_json(path, source.to_dict(), overwrite=False)

    def load_source(self, source_id: str) -> Source:
        path = self.root / "sources" / f"{source_id}.json"
        return Source.from_dict(self._read_json(path))

    def source_exists(self, source_id: str) -> bool:
        return (self.root / "sources" / f"{source_id}.json").exists()

    # -----------------------------------------------------------------------
    # Chunk
    # -----------------------------------------------------------------------

    def save_chunk(self, chunk: Chunk):
        path = self.root / "chunks" / f"{chunk.chunk_id}.json"
        self._write_json(path, chunk.to_dict())

    def load_chunk(self, chunk_id: str) -> Chunk:
        path = self.root / "chunks" / f"{chunk_id}.json"
        return Chunk.from_dict(self._read_json(path))

    def chunk_exists(self, chunk_id: str) -> bool:
        return (self.root / "chunks" / f"{chunk_id}.json").exists()

    def list_chunks(self) -> list[str]:
        return [p.stem for p in (self.root / "chunks").glob("*.json")]
    
    def list_sources(self) -> list[str]:
        return [p.stem for p in (self.root / "sources").glob("*.json")]

    # -----------------------------------------------------------------------
    # Manifest
    # -----------------------------------------------------------------------

    def save_manifest(self, manifest: Manifest):
        path = self.root / "manifests" / f"{manifest.manifest_id}.json"
        self._write_json(path, manifest.to_dict())

    def load_manifest(self, manifest_id: str) -> Manifest:
        path = self.root / "manifests" / f"{manifest_id}.json"
        return Manifest.from_dict(self._read_json(path))

    def manifest_exists(self, manifest_id: str) -> bool:
        return (self.root / "manifests" / f"{manifest_id}.json").exists()

    # -----------------------------------------------------------------------
    # History (append-only per chunk)
    # -----------------------------------------------------------------------

    def append_history(self, entry: ChunkHistory):
        """Append a history entry. The directory per chunk is created if absent."""
        dir_ = self.root / "history" / entry.chunk_id
        dir_.mkdir(exist_ok=True)
        path = dir_ / f"{entry.history_id}.json"
        self._write_json(path, entry.to_dict(), overwrite=False)

    def load_history(self, chunk_id: str) -> list[ChunkHistory]:
        """Return all history entries for a chunk, sorted by timestamp."""
        dir_ = self.root / "history" / chunk_id
        if not dir_.exists():
            return []
        entries = [ChunkHistory.from_dict(self._read_json(p)) for p in dir_.glob("*.json")]
        return sorted(entries, key=lambda e: e.timestamp)

    # -----------------------------------------------------------------------
    # Locks
    # -----------------------------------------------------------------------

    def save_lock(self, lock: Lock):
        path = self.root / "locks" / f"{lock.chunk_id}.lock.json"
        self._write_json(path, lock.to_dict(), overwrite=False)

    def load_lock(self, chunk_id: str) -> Optional[Lock]:
        path = self.root / "locks" / f"{chunk_id}.lock.json"
        if not path.exists():
            return None
        return Lock.from_dict(self._read_json(path))

    def delete_lock(self, chunk_id: str):
        path = self.root / "locks" / f"{chunk_id}.lock.json"
        if path.exists():
            path.unlink()

    def is_locked(self, chunk_id: str) -> bool:
        return (self.root / "locks" / f"{chunk_id}.lock.json").exists()

    # -----------------------------------------------------------------------
    # Exports (write to exports/ directory)
    # -----------------------------------------------------------------------

    def write_export(self, filename: str, content: str) -> Path:
        """Write reconstructed file content to exports/. Returns the output path."""
        path = self.root / "exports" / filename
        path.write_text(content, encoding="utf-8")
        return path
