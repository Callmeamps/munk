# Munk v0.1 — Implementation Guide

This document covers the full implementation of Munk v0.1 in Python. It follows the phase order from the spec: data model first, then chunker, editor, assembler, TUI, API, and web app. Each phase is independently testable before the next begins.

**Stack**

- Python 3.11+
- `textual` for TUI (Phase 5)
- `fastapi` + `uvicorn` for API (Phase 6)
- No ORM, no database — flat JSON files on disk

---

## Project Structure

```
munk/
├── munk/
│   ├── __init__.py
│   ├── models.py          # Phase 1 — dataclasses
│   ├── store.py           # Phase 1 — JSON read/write
│   ├── ids.py             # Phase 1 — ID generation
│   ├── hashing.py         # Phase 1 — content hashing
│   ├── chunker.py         # Phase 2 — line-scanning chunker
│   ├── chunker_config.py  # Phase 2 — format boundary config
│   ├── editor.py          # Phase 3 — edit_chunk and versioning
│   ├── assembler.py       # Phase 4 — manifest reconstruction
│   ├── validator.py       # Phase 4 — validation rules
│   ├── locker.py          # Phase 3 — lock/unlock
│   └── api/
│       ├── __init__.py
│       └── routes.py      # Phase 6 — FastAPI routes
├── tui/
│   └── app.py             # Phase 5 — Textual TUI
├── munk_data/             # Runtime data root (gitignored)
│   ├── sources/
│   ├── chunks/
│   ├── manifests/
│   ├── history/
│   ├── locks/
│   ├── exports/
│   ├── diffs/
│   └── policies/
├── tests/
│   ├── test_models.py
│   ├── test_chunker.py
│   ├── test_editor.py
│   └── test_assembler.py
├── examples/
│   ├── sample.gd
│   ├── sample.md
│   └── sample.txt
├── pyproject.toml
└── README.md
```

---

## Phase 1 — Core Data Model

**Goal:** Define all data objects as Python dataclasses. Implement JSON serialization, ID generation, and content hashing. No business logic yet.

---

### 1.1 `ids.py` — ID Generation

IDs are prefixed strings with a UUID4 short suffix. Prefixes make log output and filenames immediately readable.

```python
# munk/ids.py

import uuid


def new_id(prefix: str) -> str:
    """
    Generate a prefixed unique ID.

    Examples:
        new_id("src")  -> "src_3f2a1b"
        new_id("chk")  -> "chk_9e4c7d"
        new_id("man")  -> "man_0a1b2c"
        new_id("hist") -> "hist_5d6e7f"
    """
    short = uuid.uuid4().hex[:6]
    return f"{prefix}_{short}"
```

Usage example:

```python
from munk.ids import new_id

source_id = new_id("src")   # "src_3f2a1b"
chunk_id  = new_id("chk")   # "chk_9e4c7d"
man_id    = new_id("man")   # "man_0a1b2c"
hist_id   = new_id("hist")  # "hist_5d6e7f"
diff_id   = new_id("diff")  # "diff_1a2b3c"
lock_id   = new_id("lock")  # "lock_4d5e6f"
```

---

### 1.2 `hashing.py` — Content Hashing

All content hashes use SHA-256. The hash is stored as a prefixed hex string for clarity.

```python
# munk/hashing.py

import hashlib


def hash_content(content: str) -> str:
    """
    Return a sha256 hex digest of the given string content.

    Format: "sha256:<hexdigest>"

    Examples:
        hash_content("hello world") -> "sha256:b94d27b9..."
        hash_content("")            -> "sha256:e3b0c442..."
    """
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def hash_file(path: str) -> str:
    """
    Return a sha256 hex digest of a file on disk.

    Reads in binary mode to avoid encoding issues.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def verify_content(content: str, expected_hash: str) -> bool:
    """
    Return True if content matches the expected hash.

    Examples:
        verify_content("hello", hash_content("hello")) -> True
        verify_content("hello", hash_content("world")) -> False
    """
    return hash_content(content) == expected_hash
```

---

### 1.3 `models.py` — Dataclasses

Every data object from the spec is represented here as a frozen or partially frozen dataclass. History is always created from an existing chunk — never standalone.

```python
# munk/models.py

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timezone
import json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------

@dataclass
class Source:
    """
    Immutable snapshot of an original file.

    Once created, the source content and hash must never change.
    The status field should always be "locked" after registration.

    Fields:
        source_id:   Unique identifier, e.g. "src_3f2a1b"
        path:        Original file path or logical path
        hash:        sha256 content hash, e.g. "sha256:abcd..."
        size_bytes:  Byte size of the snapshot
        mime_type:   MIME type, e.g. "text/plain", "text/x-gdscript"
        created_at:  ISO 8601 UTC timestamp
        origin:      "local" | "remote" | "import"
        status:      Always "locked" for a registered source
    """
    source_id:  str
    path:       str
    hash:       str
    size_bytes: int
    mime_type:  str
    created_at: str
    origin:     str = "local"
    status:     str = "locked"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "Source":
        return cls(**d)


# ---------------------------------------------------------------------------
# Chunk
# ---------------------------------------------------------------------------

CHUNK_STATUSES = {"draft", "reviewed", "approved", "locked", "archived"}

@dataclass
class Chunk:
    """
    Mutable working unit derived from a source.

    A chunk represents one structural unit of a file: a function, a section,
    a paragraph, etc. Agents edit chunks, never sources.

    Fields:
        chunk_id:        Unique identifier, e.g. "chk_9e4c7d"
        source_id:       The source this chunk was derived from
        parent_chunk_id: Parent chunk ID if this is a derived/split chunk
        start:           Start byte offset in the source (None if not applicable)
        end:             End byte offset in the source (None if not applicable)
        content:         Current mutable text body of this chunk
        content_hash:    sha256 hash of content, recomputed on every edit
        version:         Integer, starts at 1, increments on every edit
        status:          "draft" | "reviewed" | "approved" | "locked" | "archived"
        title:           Short human-readable label, e.g. "func move_and_slide"
        description:     Longer summary, agent or human authored
        tags:            List of classification labels, e.g. ["physics", "movement"]
        author_agent:    ID or name of the agent/user who last edited this chunk
        created_at:      ISO 8601 UTC timestamp of creation
        updated_at:      ISO 8601 UTC timestamp of last edit
    """
    chunk_id:        str
    source_id:       str
    content:         str
    content_hash:    str
    version:         int
    status:          str
    created_at:      str
    updated_at:      str
    parent_chunk_id: Optional[str]      = None
    start:           Optional[int]      = None
    end:             Optional[int]      = None
    title:           str                = ""
    description:     str                = ""
    tags:            list[str]          = field(default_factory=list)
    author_agent:    str                = "user"

    def __post_init__(self):
        if self.status not in CHUNK_STATUSES:
            raise ValueError(f"Invalid chunk status: {self.status!r}. Must be one of {CHUNK_STATUSES}")

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        return cls(**d)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

EXPORT_MODES = {"rebuild"}

@dataclass
class Manifest:
    """
    Reconstruction plan for a file.

    A manifest defines which chunks are included in the output and in what order.
    The `order` field is the authoritative sequence for export.

    Fields:
        manifest_id:  Unique identifier, e.g. "man_0a1b2c"
        source_id:    The source this manifest was built from
        chunks:       Unordered set of chunk IDs belonging to this manifest
        order:        Ordered list of chunk IDs for reconstruction
        export_mode:  "rebuild" — concatenate chunks in order
        created_at:   ISO 8601 UTC timestamp
    """
    manifest_id: str
    source_id:   str
    chunks:      list[str]
    order:       list[str]
    created_at:  str
    export_mode: str = "rebuild"

    def __post_init__(self):
        if self.export_mode not in EXPORT_MODES:
            raise ValueError(f"Invalid export_mode: {self.export_mode!r}")
        if set(self.chunks) != set(self.order):
            raise ValueError("Manifest `chunks` and `order` must contain the same chunk IDs")

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "Manifest":
        return cls(**d)


# ---------------------------------------------------------------------------
# ChunkHistory
# ---------------------------------------------------------------------------

HISTORY_ACTIONS = {"create", "edit", "split", "merge", "clone", "lock", "unlock", "archive"}

@dataclass
class ChunkHistory:
    """
    Append-only record of a single action on a chunk.

    History entries are never edited or deleted. They accumulate per chunk
    and are used for audit, rollback, and lineage tracing.

    Fields:
        history_id:  Unique identifier, e.g. "hist_5d6e7f"
        chunk_id:    The chunk this record belongs to
        version:     The chunk version after this action
        action:      "create" | "edit" | "split" | "merge" | "clone" | "lock" | "unlock" | "archive"
        diff_ref:    Optional reference to a diff record in diffs/
        timestamp:   ISO 8601 UTC timestamp
        actor:       Agent ID or username who performed the action
        note:        Optional human-readable note about this change
    """
    history_id: str
    chunk_id:   str
    version:    int
    action:     str
    timestamp:  str
    actor:      str
    diff_ref:   Optional[str] = None
    note:       str           = ""

    def __post_init__(self):
        if self.action not in HISTORY_ACTIONS:
            raise ValueError(f"Invalid history action: {self.action!r}")

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "ChunkHistory":
        return cls(**d)


# ---------------------------------------------------------------------------
# Lock
# ---------------------------------------------------------------------------

@dataclass
class Lock:
    """
    Lock record preventing concurrent writes to a chunk.

    A lock is created when a chunk enters review or is claimed by an agent.
    The lock file lives in locks/ and is removed on unlock.

    Fields:
        lock_id:    Unique identifier, e.g. "lock_4d5e6f"
        chunk_id:   The chunk being locked
        owner:      Agent ID or username that holds the lock
        created_at: ISO 8601 UTC timestamp
        reason:     Optional description of why the lock was acquired
    """
    lock_id:    str
    chunk_id:   str
    owner:      str
    created_at: str
    reason:     str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "Lock":
        return cls(**d)
```

---

### 1.4 `store.py` — JSON Read/Write

The store handles all disk I/O. It knows the layout from the spec and enforces the naming convention for each object type.

```python
# munk/store.py

import json
import os
from pathlib import Path
from typing import Optional

from munk.models import Source, Chunk, Manifest, ChunkHistory, Lock


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
        return json.loads(path.read_text(encoding="utf-8"))

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
```

Example: bootstrapping the store and saving a source.

```python
from munk.store import MunkStore
from munk.models import Source
from munk.ids import new_id
from munk.hashing import hash_file
import os

store = MunkStore("munk_data")

content = open("examples/sample.gd").read()
src = Source(
    source_id  = new_id("src"),
    path       = "examples/sample.gd",
    hash       = hash_file("examples/sample.gd"),
    size_bytes = os.path.getsize("examples/sample.gd"),
    mime_type  = "text/x-gdscript",
    created_at = "2026-04-21T00:00:00Z",
    origin     = "local",
    status     = "locked",
)

store.save_source(src)
# -> munk_data/sources/src_3f2a1b.json written

# Trying to save again raises:
# store.save_source(src)  -> FileExistsError
```

---

## Phase 2 — Chunker

**Goal:** Given a file path, produce a list of Chunk objects that together cover the entire file. Write them to the store and return a Manifest.

---

### 2.1 `chunker_config.py` — Format Boundary Table

```python
# munk/chunker_config.py

import re

# Each entry maps a file extension to a list of compiled boundary patterns.
# A line matching any pattern starts a new chunk.
# The matching line is included at the top of the new chunk (it is not discarded).

CHUNKER_CONFIG: dict[str, list[re.Pattern]] = {
    "gd":  [re.compile(r"^func "), re.compile(r"^class ")],
    "md":  [re.compile(r"^#")],
    "txt": [re.compile(r"^\s*$")],
}

# JSON is handled separately via a dedicated strategy (see chunker.py).
JSON_STRATEGY = "top-level-keys"

SUPPORTED_EXTENSIONS = set(CHUNKER_CONFIG.keys()) | {"json"}


def get_boundaries(ext: str) -> list[re.Pattern]:
    """Return boundary patterns for a file extension, or empty list if unsupported."""
    return CHUNKER_CONFIG.get(ext.lower(), [])
```

---

### 2.2 `chunker.py` — Line-Scanning Chunker

The chunker reads the file line by line. When a line matches a boundary pattern, it closes the current chunk and starts a new one. Every line belongs to exactly one chunk.

```python
# munk/chunker.py

import json as json_lib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from munk.chunker_config import get_boundaries, JSON_STRATEGY, SUPPORTED_EXTENSIONS
from munk.hashing import hash_content, hash_file
from munk.ids import new_id
from munk.models import Chunk, Manifest, Source
from munk.store import MunkStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ext(path: str) -> str:
    return Path(path).suffix.lstrip(".").lower()


# ---------------------------------------------------------------------------
# Line-scanning chunker (gd, md, txt)
# ---------------------------------------------------------------------------

def _scan_lines(lines: list[str], boundaries) -> list[list[str]]:
    """
    Split lines into groups by boundary pattern.

    The line that triggers a boundary starts the new group.
    Lines before the first boundary form an implicit preamble group
    (may be empty for files that start immediately with a boundary).

    Example (GDScript):
        Input lines:
            ["# Player.gd\\n", "extends Node\\n", "\\n",
             "func _ready():\\n", "    pass\\n",
             "func _process(delta):\\n", "    pass\\n"]

        Output groups:
            [["# Player.gd\\n", "extends Node\\n", "\\n"],
             ["func _ready():\\n", "    pass\\n"],
             ["func _process(delta):\\n", "    pass\\n"]]
    """
    groups: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        is_boundary = any(p.match(line) for p in boundaries)
        if is_boundary and current:
            groups.append(current)
            current = []
        current.append(line)

    if current:
        groups.append(current)

    return groups


# ---------------------------------------------------------------------------
# JSON chunker (top-level keys)
# ---------------------------------------------------------------------------

def _chunk_json(content: str) -> list[str]:
    """
    Split a JSON object into per-key string chunks.

    Each chunk is a valid JSON object containing one top-level key.
    If the input is not an object, the entire content is one chunk.

    Example:
        Input:  {"name": "Munk", "version": 1, "tags": ["a", "b"]}
        Output: ['{"name": "Munk"}', '{"version": 1}', '{"tags": ["a", "b"]}']
    """
    try:
        parsed = json_lib.loads(content)
    except json_lib.JSONDecodeError:
        return [content]

    if not isinstance(parsed, dict):
        return [content]

    return [json_lib.dumps({k: v}, indent=2) for k, v in parsed.items()]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunkify(
    source: Source,
    file_content: str,
    store: MunkStore,
    author_agent: str = "user",
) -> Manifest:
    """
    Split a source file into Chunk objects and save them to the store.

    Returns a Manifest describing the chunks and their order.

    Raises:
        ValueError: If the file extension is not supported.

    Example usage:
        content = open("examples/sample.gd").read()
        manifest = chunkify(source, content, store)
        # -> chunks written to munk_data/chunks/
        # -> manifest written to munk_data/manifests/
    """
    ext = _ext(source.path)

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension: .{ext!r}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Produce raw text groups
    if ext == "json":
        groups = _chunk_json(file_content)
        raw_chunks = groups  # already strings
    else:
        lines = file_content.splitlines(keepends=True)
        boundaries = get_boundaries(ext)
        line_groups = _scan_lines(lines, boundaries)
        raw_chunks = ["".join(g) for g in line_groups]

    # Remove empty groups
    raw_chunks = [c for c in raw_chunks if c.strip()]

    now = _now()
    chunk_ids: list[str] = []
    chunks: list[Chunk] = []

    for i, text in enumerate(raw_chunks):
        chunk_id = new_id("chk")
        title = _infer_title(text, ext, i)
        chunk = Chunk(
            chunk_id        = chunk_id,
            source_id       = source.source_id,
            content         = text,
            content_hash    = hash_content(text),
            version         = 1,
            status          = "draft",
            created_at      = now,
            updated_at      = now,
            parent_chunk_id = None,
            title           = title,
            description     = "",
            tags            = [],
            author_agent    = author_agent,
        )
        chunks.append(chunk)
        chunk_ids.append(chunk_id)

    for chunk in chunks:
        store.save_chunk(chunk)

    manifest = Manifest(
        manifest_id = new_id("man"),
        source_id   = source.source_id,
        chunks      = chunk_ids,
        order       = chunk_ids,
        export_mode = "rebuild",
        created_at  = now,
    )
    store.save_manifest(manifest)

    return manifest


def _infer_title(text: str, ext: str, index: int) -> str:
    """
    Infer a short title for a chunk from its content.

    For GDScript: use the first line (e.g. "func _ready():")
    For Markdown:  use the heading line (e.g. "## Installation")
    For others:    use the first non-empty line, truncated to 60 chars
    Fallback:      "chunk_{index}"
    """
    first = next((l.strip() for l in text.splitlines() if l.strip()), "")
    if not first:
        return f"chunk_{index}"
    if ext in ("gd",):
        return first[:80]
    if ext == "md":
        return first.lstrip("#").strip()[:80]
    return first[:60]
```

Chunker example — GDScript file:

```
# examples/sample.gd

extends CharacterBody3D

const SPEED = 300.0
const JUMP_VELOCITY = -400.0

func _ready():
    print("Player ready")

func _physics_process(delta):
    if not is_on_floor():
        velocity += get_gravity() * delta
    if Input.is_action_just_pressed("ui_accept") and is_on_floor():
        velocity.y = JUMP_VELOCITY
    var direction = Input.get_axis("ui_left", "ui_right")
    if direction:
        velocity.x = direction * SPEED
    else:
        velocity.x = move_toward(velocity.x, 0, SPEED)
    move_and_slide()

func take_damage(amount: int):
    health -= amount
    if health <= 0:
        die()
```

Running the chunker on this file produces three chunks:

```
chk_aaa:  "extends CharacterBody3D\n\nconst SPEED = 300.0\n..."  (preamble)
chk_bbb:  "func _ready():\n    print(\"Player ready\")\n"
chk_ccc:  "func _physics_process(delta):\n    ..."
chk_ddd:  "func take_damage(amount: int):\n    ..."
```

And a manifest:

```json
{
  "manifest_id": "man_0a1b2c",
  "source_id": "src_3f2a1b",
  "chunks": ["chk_aaa", "chk_bbb", "chk_ccc", "chk_ddd"],
  "order":  ["chk_aaa", "chk_bbb", "chk_ccc", "chk_ddd"],
  "export_mode": "rebuild",
  "created_at": "2026-04-21T00:00:00Z"
}
```

---

## Phase 3 — Editor

**Goal:** Implement `edit_chunk`, `lock_chunk`, and `unlock_chunk`. Every mutation increments the version, updates the hash, and writes a history entry. Locked chunks cannot be edited.

---

### 3.1 `locker.py` — Lock and Unlock

```python
# munk/locker.py

from datetime import datetime, timezone
from munk.ids import new_id
from munk.models import Lock
from munk.store import MunkStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LockError(Exception):
    """Raised when a lock operation fails."""


def lock_chunk(chunk_id: str, owner: str, store: MunkStore, reason: str = "") -> Lock:
    """
    Acquire a lock on a chunk.

    Raises LockError if the chunk is already locked by someone else.

    Example:
        lock = lock_chunk("chk_9e4c7d", owner="agent_007", store=store)
        # -> munk_data/locks/chk_9e4c7d.lock.json written
    """
    existing = store.load_lock(chunk_id)
    if existing is not None:
        raise LockError(
            f"Chunk {chunk_id!r} is already locked by {existing.owner!r}. "
            f"Acquired at {existing.created_at}."
        )
    lock = Lock(
        lock_id    = new_id("lock"),
        chunk_id   = chunk_id,
        owner      = owner,
        created_at = _now(),
        reason     = reason,
    )
    store.save_lock(lock)
    return lock


def unlock_chunk(chunk_id: str, owner: str, store: MunkStore) -> bool:
    """
    Release a lock on a chunk.

    Raises LockError if the chunk is not locked or is locked by a different owner.

    Returns True on success.

    Example:
        unlock_chunk("chk_9e4c7d", owner="agent_007", store=store)
        # -> munk_data/locks/chk_9e4c7d.lock.json deleted
    """
    existing = store.load_lock(chunk_id)
    if existing is None:
        raise LockError(f"Chunk {chunk_id!r} is not locked.")
    if existing.owner != owner:
        raise LockError(
            f"Cannot unlock chunk {chunk_id!r}: locked by {existing.owner!r}, "
            f"not {owner!r}."
        )
    store.delete_lock(chunk_id)
    return True
```

---

### 3.2 `editor.py` — Edit Chunk

```python
# munk/editor.py

from datetime import datetime, timezone
from typing import Optional

from munk.hashing import hash_content, verify_content
from munk.ids import new_id
from munk.models import Chunk, ChunkHistory
from munk.store import MunkStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EditError(Exception):
    """Raised when an edit operation cannot proceed."""


def edit_chunk(
    chunk_id:    str,
    new_content: str,
    store:       MunkStore,
    actor:       str          = "user",
    description: str          = "",
    tags:        Optional[list[str]] = None,
    status:      Optional[str] = None,
    note:        str          = "",
) -> Chunk:
    """
    Apply new content to a chunk.

    Rules enforced:
    - The chunk must exist.
    - The chunk must not be locked (unless the caller owns the lock — lock
      ownership is not checked here; use locker.py before calling edit_chunk
      if you want lock-gated edits).
    - The chunk must not have status "locked" or "archived".
    - The new content must not be empty.

    On success:
    - content and content_hash are updated
    - version is incremented
    - updated_at is refreshed
    - A ChunkHistory entry is appended

    Returns the updated Chunk.

    Example:
        updated = edit_chunk(
            chunk_id    = "chk_9e4c7d",
            new_content = "func _ready():\\n    print('hello')\\n",
            store       = store,
            actor       = "agent_007",
            note        = "Added hello print",
        )
        print(updated.version)  # 2
    """
    if not new_content.strip():
        raise EditError("new_content must not be empty.")

    chunk = store.load_chunk(chunk_id)

    if chunk.status in ("locked", "archived"):
        raise EditError(
            f"Cannot edit chunk {chunk_id!r}: status is {chunk.status!r}. "
            f"Unlock or unarchive first."
        )

    if store.is_locked(chunk_id):
        raise EditError(
            f"Cannot edit chunk {chunk_id!r}: it has an active lock. "
            f"Use unlock_chunk() or acquire the lock before editing."
        )

    now = _now()
    new_hash = hash_content(new_content)

    updated = Chunk(
        chunk_id        = chunk.chunk_id,
        source_id       = chunk.source_id,
        content         = new_content,
        content_hash    = new_hash,
        version         = chunk.version + 1,
        status          = status if status is not None else chunk.status,
        created_at      = chunk.created_at,
        updated_at      = now,
        parent_chunk_id = chunk.parent_chunk_id,
        title           = chunk.title,
        description     = description if description else chunk.description,
        tags            = tags if tags is not None else chunk.tags,
        author_agent    = actor,
    )

    store.save_chunk(updated)

    history = ChunkHistory(
        history_id = new_id("hist"),
        chunk_id   = chunk_id,
        version    = updated.version,
        action     = "edit",
        timestamp  = now,
        actor      = actor,
        diff_ref   = None,
        note       = note,
    )
    store.append_history(history)

    return updated
```

Editor example:

```python
from munk.editor import edit_chunk

# Original chunk content:
#   "func _ready():\n    pass\n"

updated = edit_chunk(
    chunk_id    = "chk_bbb",
    new_content = "func _ready():\n    print('Player ready')\n    set_physics_process(true)\n",
    store       = store,
    actor       = "agent_007",
    note        = "Added startup print and physics flag",
)

print(updated.version)       # 2
print(updated.author_agent)  # "agent_007"
print(updated.content_hash)  # "sha256:..."
```

History after the edit:

```json
{
  "history_id": "hist_5d6e7f",
  "chunk_id":   "chk_bbb",
  "version":    2,
  "action":     "edit",
  "timestamp":  "2026-04-21T00:01:00Z",
  "actor":      "agent_007",
  "diff_ref":   null,
  "note":       "Added startup print and physics flag"
}
```

---

## Phase 4 — Assembler

**Goal:** Read a manifest, load chunks in order, validate integrity, and reconstruct the file into `exports/`. The source is never touched.

---

### 4.1 `validator.py` — Validation

```python
# munk/validator.py

from munk.hashing import verify_content
from munk.models import Chunk, Manifest
from munk.store import MunkStore


class ValidationError(Exception):
    """Raised when a chunk or manifest fails validation."""


def validate_chunk(chunk: Chunk, store: MunkStore) -> None:
    """
    Validate a single chunk before export.

    Checks:
    - source_id refers to a registered source
    - content_hash matches the current content
    - status is not "archived"

    Raises ValidationError on any failure.
    """
    if not store.source_exists(chunk.source_id):
        raise ValidationError(
            f"Chunk {chunk.chunk_id!r} references unknown source {chunk.source_id!r}."
        )

    if not verify_content(chunk.content, chunk.content_hash):
        raise ValidationError(
            f"Chunk {chunk.chunk_id!r} content hash mismatch. "
            f"Expected {chunk.content_hash!r}. Content may have been tampered with."
        )

    if chunk.status == "archived":
        raise ValidationError(
            f"Chunk {chunk.chunk_id!r} is archived and cannot be exported."
        )


def validate_manifest(manifest: Manifest, store: MunkStore) -> list[Chunk]:
    """
    Validate a manifest and all its chunks.

    Checks:
    - source_id is registered
    - all chunk IDs in `order` exist in the store
    - chunks and order contain the same IDs
    - each chunk passes validate_chunk

    Returns the ordered list of loaded Chunk objects on success.
    Raises ValidationError on any failure.
    """
    if not store.source_exists(manifest.source_id):
        raise ValidationError(
            f"Manifest {manifest.manifest_id!r} references unknown source {manifest.source_id!r}."
        )

    if set(manifest.chunks) != set(manifest.order):
        raise ValidationError(
            f"Manifest {manifest.manifest_id!r}: `chunks` and `order` are inconsistent."
        )

    chunks = []
    for chunk_id in manifest.order:
        if not store.chunk_exists(chunk_id):
            raise ValidationError(
                f"Manifest {manifest.manifest_id!r} references missing chunk {chunk_id!r}."
            )
        chunk = store.load_chunk(chunk_id)
        validate_chunk(chunk, store)
        chunks.append(chunk)

    return chunks
```

---

### 4.2 `assembler.py` — Export

```python
# munk/assembler.py

from pathlib import Path
from munk.models import Manifest
from munk.store import MunkStore
from munk.validator import validate_manifest


class AssemblyError(Exception):
    """Raised when file reconstruction fails."""


def assemble(
    manifest_id: str,
    output_filename: str,
    store: MunkStore,
    separator: str = "",
) -> Path:
    """
    Reconstruct a file from the manifest's ordered chunks.

    The output is written to munk_data/exports/{output_filename}.
    The original source file is never modified.

    Args:
        manifest_id:     ID of the manifest to export
        output_filename: Filename for the reconstructed file, e.g. "player_v2.gd"
        store:           The MunkStore instance
        separator:       String inserted between chunks (default: empty string)
                         Use "\\n" if chunks don't already end with a newline.

    Returns the Path of the written export file.

    Raises AssemblyError if validation fails or the manifest is not found.

    Example:
        path = assemble("man_0a1b2c", "player_v2.gd", store)
        print(path)  # PosixPath("munk_data/exports/player_v2.gd")
    """
    if not store.manifest_exists(manifest_id):
        raise AssemblyError(f"Manifest {manifest_id!r} not found.")

    manifest = store.load_manifest(manifest_id)

    # Validate everything before writing any output
    chunks = validate_manifest(manifest, store)

    content = separator.join(chunk.content for chunk in chunks)
    output_path = store.write_export(output_filename, content)

    return output_path
```

Assembly example — full round-trip:

```python
from munk.assembler import assemble

# Manifest has 4 chunks: preamble + 3 funcs
path = assemble(
    manifest_id     = "man_0a1b2c",
    output_filename = "player_v2.gd",
    store           = store,
)
# -> munk_data/exports/player_v2.gd

# Verify the round-trip
original = open("examples/sample.gd").read()
exported = open(path).read()
assert original == exported, "Round-trip mismatch"
```

---

## Phase 5 — TUI

**Goal:** A `textual`-based terminal UI with three panels: file/chunk list, chunk viewer with diff, and action controls.

---

### 5.1 `tui/app.py` — Textual Application

```python
# tui/app.py

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, TextArea, Button, Static
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
import difflib

from munk.store import MunkStore
from munk.editor import edit_chunk
from munk.assembler import assemble


class MunkTUI(App):
    """
    Munk TUI — three-panel layout:

    ┌─────────────┬──────────────────────────┬───────────────┐
    │  Chunk List │  Diff View               │  Actions      │
    │             │  (original vs current)   │               │
    └─────────────┴──────────────────────────┴───────────────┘
    """

    CSS = """
    #chunk-list  { width: 25%; border: solid green; }
    #diff-view   { width: 55%; border: solid blue; }
    #actions     { width: 20%; border: solid yellow; }
    Button       { margin: 1 0; }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("a", "approve_chunk", "Approve"),
        ("r", "reject_chunk", "Reject"),
        ("e", "export", "Export"),
    ]

    selected_chunk_id: reactive[str | None] = reactive(None)

    def __init__(self, store: MunkStore, manifest_id: str):
        super().__init__()
        self.store = store
        self.manifest_id = manifest_id

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ListView(id="chunk-list")
            yield TextArea(id="diff-view", read_only=True)
            with Vertical(id="actions"):
                yield Button("Approve", id="btn-approve", variant="success")
                yield Button("Reject",  id="btn-reject",  variant="error")
                yield Button("Export",  id="btn-export",  variant="primary")
        yield Footer()

    def on_mount(self):
        self._refresh_chunk_list()

    def _refresh_chunk_list(self):
        manifest = self.store.load_manifest(self.manifest_id)
        list_view = self.query_one("#chunk-list", ListView)
        list_view.clear()
        for chunk_id in manifest.order:
            chunk = self.store.load_chunk(chunk_id)
            label = f"[{chunk.status[:1].upper()}] {chunk.title or chunk_id}"
            list_view.append(ListItem(Label(label), id=chunk_id))

    def on_list_view_selected(self, event: ListView.Selected):
        chunk_id = event.item.id
        self.selected_chunk_id = chunk_id
        self._show_diff(chunk_id)

    def _show_diff(self, chunk_id: str):
        """Show a unified diff of the chunk's original source vs current content."""
        chunk = self.store.load_chunk(chunk_id)
        source = self.store.load_source(chunk.source_id)

        history = self.store.load_history(chunk_id)
        # Version 1 content is always the original from the chunker
        # For simplicity in v0.1, show current content vs version 1 if history exists
        original_lines = []
        if history:
            # We don't store full content in history in v0.1 — show placeholder
            original_lines = [f"# version 1 content not stored inline\n"]
        current_lines = chunk.content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            current_lines,
            fromfile=f"{chunk_id} (v1)",
            tofile=f"{chunk_id} (v{chunk.version})",
        )
        self.query_one("#diff-view", TextArea).load_text("".join(diff) or chunk.content)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-approve":
            self.action_approve_chunk()
        elif event.button.id == "btn-reject":
            self.action_reject_chunk()
        elif event.button.id == "btn-export":
            self.action_export()

    def action_approve_chunk(self):
        if self.selected_chunk_id:
            chunk = self.store.load_chunk(self.selected_chunk_id)
            # Update status to approved via edit_chunk (content unchanged)
            edit_chunk(
                chunk_id    = self.selected_chunk_id,
                new_content = chunk.content,
                store       = self.store,
                actor       = "user",
                status      = "approved",
                note        = "Approved via TUI",
            )
            self._refresh_chunk_list()

    def action_reject_chunk(self):
        if self.selected_chunk_id:
            chunk = self.store.load_chunk(self.selected_chunk_id)
            edit_chunk(
                chunk_id    = self.selected_chunk_id,
                new_content = chunk.content,
                store       = self.store,
                actor       = "user",
                status      = "draft",
                note        = "Rejected via TUI — reset to draft",
            )
            self._refresh_chunk_list()

    def action_export(self):
        assemble(self.manifest_id, "export_output.gd", self.store)
        self.notify("Exported to munk_data/exports/export_output.gd")


if __name__ == "__main__":
    store = MunkStore("munk_data")
    # Replace with a real manifest_id from your store
    app = MunkTUI(store=store, manifest_id="man_0a1b2c")
    app.run()
```

---

## Phase 6 — API

**Goal:** FastAPI wrapper over the Phase 1–4 engine. Every endpoint is stateless — the store is the only state.

---

### 6.1 `api/routes.py`

```python
# munk/api/routes.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os

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
    strategy: str = "line-scan"   # "line-scan" only in v0.1
    author_agent: str = "user"

class EditChunkRequest(BaseModel):
    content: str
    description: str = ""
    tags: Optional[list[str]] = None
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
    mode: str = "rebuild"


# ── Routes ───────────────────────────────────────────────────────────────────

@app.post("/sources", status_code=201)
def create_source(req: CreateSourceRequest):
    """
    Register a new immutable source snapshot.

    POST /sources
    {
      "path": "examples/sample.gd",
      "mime_type": "text/x-gdscript",
      "content": "extends CharacterBody3D\n..."
    }

    Response:
    {
      "source_id": "src_3f2a1b",
      "status": "locked"
    }
    """
    from datetime import datetime, timezone
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
    # Store content as a separate file for the chunker to use
    content_path = store.root / "sources" / f"{source_id}.content"
    content_path.write_text(req.content, encoding="utf-8")
    return {"source_id": source_id, "status": "locked"}


@app.post("/sources/{source_id}/chunkify", status_code=201)
def chunkify_source(source_id: str, req: ChunkifyRequest):
    """
    Split a source into chunks and create a manifest.

    POST /sources/src_3f2a1b/chunkify
    {"strategy": "line-scan", "author_agent": "user"}

    Response:
    {
      "manifest_id": "man_0a1b2c",
      "chunk_ids": ["chk_aaa", "chk_bbb", "chk_ccc"]
    }
    """
    if not store.source_exists(source_id):
        raise HTTPException(404, f"Source {source_id!r} not found.")
    source = store.load_source(source_id)
    content_path = store.root / "sources" / f"{source_id}.content"
    if not content_path.exists():
        raise HTTPException(500, f"Source content file missing for {source_id!r}.")
    content = content_path.read_text(encoding="utf-8")
    try:
        manifest = chunkify(source, content, store, author_agent=req.author_agent)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"manifest_id": manifest.manifest_id, "chunk_ids": manifest.order}


@app.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: str):
    if not store.chunk_exists(chunk_id):
        raise HTTPException(404, f"Chunk {chunk_id!r} not found.")
    return store.load_chunk(chunk_id).to_dict()


@app.patch("/chunks/{chunk_id}")
def patch_chunk(chunk_id: str, req: EditChunkRequest):
    """
    Edit a chunk's content.

    PATCH /chunks/chk_bbb
    {
      "content": "func _ready():\\n    print('hello')\\n",
      "actor": "agent_007",
      "note": "Added greeting"
    }
    """
    if not store.chunk_exists(chunk_id):
        raise HTTPException(404, f"Chunk {chunk_id!r} not found.")
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
    except EditError as e:
        raise HTTPException(409, str(e))
    return updated.to_dict()


@app.post("/chunks/{chunk_id}/lock", status_code=201)
def lock(chunk_id: str, req: LockRequest):
    if not store.chunk_exists(chunk_id):
        raise HTTPException(404, f"Chunk {chunk_id!r} not found.")
    try:
        lock_obj = lock_chunk(chunk_id, owner=req.owner, store=store, reason=req.reason)
    except LockError as e:
        raise HTTPException(409, str(e))
    return lock_obj.to_dict()


@app.post("/chunks/{chunk_id}/unlock")
def unlock(chunk_id: str, req: UnlockRequest):
    if not store.chunk_exists(chunk_id):
        raise HTTPException(404, f"Chunk {chunk_id!r} not found.")
    try:
        unlock_chunk(chunk_id, owner=req.owner, store=store)
    except LockError as e:
        raise HTTPException(409, str(e))
    return {"chunk_id": chunk_id, "status": "unlocked"}


@app.get("/manifests/{manifest_id}")
def get_manifest(manifest_id: str):
    if not store.manifest_exists(manifest_id):
        raise HTTPException(404, f"Manifest {manifest_id!r} not found.")
    return store.load_manifest(manifest_id).to_dict()


@app.post("/manifests/{manifest_id}/export", status_code=201)
def export_manifest(manifest_id: str, req: ExportRequest):
    """
    Reconstruct a file from the manifest and write it to exports/.

    POST /manifests/man_0a1b2c/export
    {"output_filename": "player_v2.gd", "mode": "rebuild"}

    Response:
    {
      "output_path": "munk_data/exports/player_v2.gd",
      "manifest_id": "man_0a1b2c"
    }
    """
    if not store.manifest_exists(manifest_id):
        raise HTTPException(404, f"Manifest {manifest_id!r} not found.")
    try:
        path = assemble(manifest_id, req.output_filename, store)
    except (AssemblyError, ValidationError) as e:
        raise HTTPException(422, str(e))
    return {"output_path": str(path), "manifest_id": manifest_id}
```

Starting the API:

```bash
uvicorn munk.api.routes:app --reload --port 8000
```

Interactive docs available at `http://localhost:8000/docs`.

---

## Phase 7 — Web App

**Goal:** A single-page frontend served by FastAPI. Live preview panel on the right, diff + approval queue on the left. No framework required for v0.1 — plain HTML + JS calling the Phase 6 API.

The web app is served as a static file from the API:

```python
# Add to munk/api/routes.py

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.mount("/static", StaticFiles(directory="web/static"), name="static")

@app.get("/")
def root():
    return FileResponse("web/index.html")
```

The frontend makes fetch calls to the API:

```javascript
// web/static/app.js — example: load manifest and render chunk list

async function loadManifest(manifestId) {
    const res = await fetch(`/manifests/${manifestId}`);
    const manifest = await res.json();

    const list = document.getElementById("chunk-list");
    list.innerHTML = "";

    for (const chunkId of manifest.order) {
        const chunkRes = await fetch(`/chunks/${chunkId}`);
        const chunk = await chunkRes.json();

        const item = document.createElement("li");
        item.textContent = `[${chunk.status}] ${chunk.title || chunkId}`;
        item.dataset.chunkId = chunkId;
        item.onclick = () => loadChunk(chunkId);
        list.appendChild(item);
    }
}

async function approveChunk(chunkId) {
    const chunkRes = await fetch(`/chunks/${chunkId}`);
    const chunk = await chunkRes.json();

    await fetch(`/chunks/${chunkId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            content: chunk.content,
            status: "approved",
            actor: "user",
            note: "Approved via web UI",
        }),
    });
    await loadManifest(currentManifestId);
}

async function exportManifest(manifestId, outputFilename) {
    const res = await fetch(`/manifests/${manifestId}/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output_filename: outputFilename, mode: "rebuild" }),
    });
    const result = await res.json();
    console.log("Exported to:", result.output_path);
}
```

---

## Testing

Each phase is tested before the next begins.

```python
# tests/test_models.py

from munk.models import Source, Chunk, Manifest, ChunkHistory
from munk.ids import new_id
from munk.hashing import hash_content
from datetime import datetime, timezone

def _now():
    return datetime.now(timezone.utc).isoformat()

def test_source_roundtrip():
    src = Source(
        source_id="src_test", path="/test.gd", hash="sha256:abc",
        size_bytes=100, mime_type="text/plain", created_at=_now()
    )
    assert Source.from_dict(src.to_dict()).source_id == "src_test"

def test_chunk_invalid_status():
    import pytest
    with pytest.raises(ValueError):
        Chunk(
            chunk_id="chk_x", source_id="src_x", content="x",
            content_hash=hash_content("x"), version=1, status="bogus",
            created_at=_now(), updated_at=_now()
        )

def test_manifest_order_mismatch():
    import pytest
    with pytest.raises(ValueError):
        Manifest(
            manifest_id="man_x", source_id="src_x",
            chunks=["chk_a", "chk_b"], order=["chk_a"],
            created_at=_now()
        )
```

```python
# tests/test_chunker.py

from munk.chunker import _scan_lines, _chunk_json
from munk.chunker_config import get_boundaries

def test_gdscript_chunks():
    lines = [
        "extends Node\n",
        "\n",
        "func _ready():\n",
        "    pass\n",
        "func _process(delta):\n",
        "    pass\n",
    ]
    boundaries = get_boundaries("gd")
    groups = _scan_lines(lines, boundaries)
    assert len(groups) == 3
    assert groups[0] == ["extends Node\n", "\n"]
    assert groups[1][0] == "func _ready():\n"
    assert groups[2][0] == "func _process(delta):\n"

def test_json_chunker():
    content = '{"name": "Munk", "version": 1}'
    chunks = _chunk_json(content)
    assert len(chunks) == 2
    assert '"name"' in chunks[0]
    assert '"version"' in chunks[1]
```

```python
# tests/test_assembler.py

import tempfile, os
from munk.store import MunkStore
from munk.models import Source, Chunk, Manifest
from munk.hashing import hash_content
from munk.assembler import assemble
from munk.ids import new_id
from datetime import datetime, timezone

def _now():
    return datetime.now(timezone.utc).isoformat()

def test_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        store = MunkStore(tmp)
        content = "extends Node\n\nfunc _ready():\n    pass\n"

        src = Source(
            source_id=new_id("src"), path="/test.gd",
            hash=hash_content(content), size_bytes=len(content),
            mime_type="text/plain", created_at=_now()
        )
        store.save_source(src)

        chk = Chunk(
            chunk_id=new_id("chk"), source_id=src.source_id,
            content=content, content_hash=hash_content(content),
            version=1, status="draft", created_at=_now(), updated_at=_now()
        )
        store.save_chunk(chk)

        man = Manifest(
            manifest_id=new_id("man"), source_id=src.source_id,
            chunks=[chk.chunk_id], order=[chk.chunk_id], created_at=_now()
        )
        store.save_manifest(man)

        path = assemble(man.manifest_id, "out.gd", store)
        assert open(path).read() == content
```

---

## pyproject.toml

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "munk"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
    "textual>=0.55.0",
]

[project.optional-dependencies]
dev = ["pytest", "httpx"]

[project.scripts]
munk-api = "munk.api.routes:app"
munk-tui = "tui.app:main"
```

---

## What Is Not In v0.1

These are deferred and should not be built until the base is stable:

- **Diff storage**: `diff_ref` fields exist in history but diffs are not written yet. Add in v0.2.
- **Rebase**: `rebase_chunk` is defined in the spec but not implemented. Requires a clear definition of source-revision handling first.
- **Split and merge operations**: The API routes are stubs. Implement after the edit loop is proven stable.
- **Clone**: Useful for parallel agent work but not needed for single-agent v0.1.
- **Policy engine**: The `policies/` directory exists but no validator reads from it yet.
- **Conflict detection**: Single-agent v0.1 does not produce conflicts. Implement when multi-agent is introduced.
- **Binary files**: Out of scope for v0.1.
