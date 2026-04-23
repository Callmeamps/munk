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
