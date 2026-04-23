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
            ["# Player.gd\n", "extends Node\n", "\n",
             "func _ready():\n", "    pass\n",
             "func _process(delta):\n", "    pass\n"]

        Output groups:
            [["# Player.gd\n", "extends Node\n", "\n"],
             ["func _ready():\n", "    pass\n"],
             ["func _process(delta):\n", "    pass\n"]]
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
