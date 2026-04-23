# Munk v0.1 Technical Spec

## 1. Overview

Munk is a sandboxed, chunk-based editing system for files and documents. It is designed for agentic file editing where the source file is never written to directly. Instead, Munk creates and mutates chunk objects derived from immutable source snapshots.

Munk's primary safety property is simple:

- Source files are immutable
- Chunks are mutable
- Exports are explicit
- Overwrites of source are not allowed

This makes Munk suitable for autonomous or semi-autonomous editing systems where accidental destructive writes must be prevented.

---

## 2. Goals

Munk is intended to provide:

- Safe editing over immutable source content
- Chunk-level isolation for agents
- Rich metadata per chunk
- Chunk versioning and lineage tracking
- Explicit reconstruction/export of a file from chunk state
- Conflict control for concurrent or multi-agent editing
- A JSON-native control plane for document structure and behavior

---

## 3. Non-Goals

Munk v0.1 does not attempt to be:

- A full version control system
- A filesystem replacement
- A collaborative real-time editor
- A binary file editor for arbitrary low-level formats
- A merge engine that silently resolves every conflict

---

## 4. Core Concepts

### 4.1 Source

A source is the immutable snapshot of the original file. A source may be a local file, a remote file copy, or an imported document snapshot. Once registered, a source must not be modified in place.

### 4.2 Chunk

A chunk is a mutable working unit derived from a source or another chunk. A chunk can represent a paragraph, a section, a region of code, a semantic fragment, or a fixed byte range for binary content. Chunks are the unit of agent editing.

### 4.3 Manifest

A manifest is the reconstruction plan for a file. It defines which chunks belong to the current editable view or exportable output. A manifest may reference source snapshot IDs, chunk IDs, chunk order, chunk version selections, and export settings.

### 4.4 Projection

A projection is the chunked editable view of a source. It is a derived working set, not the source itself.

### 4.5 Export

An export is an explicit action that reconstructs a file from the current manifest and selected chunk state.

---

## 5. System Model

```
immutable source snapshot
        ↓
chunk projection layer
        ↓
mutable chunks
        ↓
manifest assembly
        ↓
explicit export
```

The original file is treated as read-only truth. The agent operates only on chunk-space.

---

## 6. Data Objects

### 6.1 Source Object

```json
{
  "source_id": "src_001",
  "path": "/docs/spec.txt",
  "hash": "sha256:...",
  "size_bytes": 128993,
  "mime_type": "text/plain",
  "created_at": "2026-04-21T00:00:00Z",
  "origin": "local",
  "status": "locked"
}
```

| Field | Description |
|---|---|
| source_id | Unique source identifier |
| path | Original path or logical path |
| hash | Immutable integrity hash |
| size_bytes | Byte size of the snapshot |
| mime_type | Content type |
| created_at | Creation time |
| origin | Where the source came from |
| status | Should normally be `locked` |

### 6.2 Chunk Object

```json
{
  "chunk_id": "chk_001",
  "source_id": "src_001",
  "parent_chunk_id": null,
  "start": 0,
  "end": 1200,
  "content": "text...",
  "content_hash": "sha256:...",
  "version": 3,
  "status": "draft",
  "title": "Introduction",
  "description": "Opening section",
  "tags": ["overview", "safe"],
  "author_agent": "agent_007",
  "created_at": "2026-04-21T00:00:00Z",
  "updated_at": "2026-04-21T00:00:00Z"
}
```

| Field | Description |
|---|---|
| chunk_id | Unique chunk identifier |
| source_id | Linked immutable source snapshot |
| parent_chunk_id | Parent chunk, if derived from another chunk |
| start / end | Source range or logical range, when applicable |
| content | Current mutable chunk body |
| content_hash | Integrity hash for chunk body |
| version | Integer version number |
| status | Lifecycle state |
| title | Short label |
| description | Human or agent-readable summary |
| tags | Classification or routing labels |
| author_agent | The agent or user responsible for the edit |
| created_at / updated_at | Timestamps |

### 6.3 Manifest Object

```json
{
  "manifest_id": "man_001",
  "source_id": "src_001",
  "chunks": ["chk_001", "chk_002", "chk_003"],
  "order": ["chk_001", "chk_002", "chk_003"],
  "export_mode": "rebuild",
  "created_at": "2026-04-21T00:00:00Z"
}
```

| Field | Description |
|---|---|
| manifest_id | Unique manifest identifier |
| source_id | Source snapshot reference |
| chunks | Chunk membership list |
| order | Explicit reconstruction order |
| export_mode | Export behavior, usually `rebuild` |
| created_at | Creation timestamp |

### 6.4 Chunk History Object

```json
{
  "history_id": "hist_001",
  "chunk_id": "chk_001",
  "version": 3,
  "action": "edit",
  "diff_ref": "diff_045",
  "timestamp": "2026-04-21T00:00:00Z",
  "actor": "agent_007"
}
```

This history object is append-only and used for audit, rollback, and lineage.

---

## 7. Metadata Model

Chunks may carry arbitrary metadata. In v0.1, the recommended fields are: `title`, `description`, `version`, `status`, `tags`, `author_agent`, `parent_chunk_id`, `source_range`, `content_hash`, `confidence`, `notes`, `locks`, `review_state`.

Recommended `status` values: `draft`, `reviewed`, `approved`, `locked`, `archived`.

Metadata is not cosmetic. It is part of the system control plane.

---

## 8. Chunk Lifecycle

1. Create from source or parent chunk
2. Edit in chunk space
3. Version on save
4. Split if needed
5. Merge if needed
6. Lock when stable or under review
7. Export through a manifest

A chunk should never be silently replaced without a history record.

---

## 9. Editing Model

### 9.1 Allowed mutation scope

Agents may only mutate chunk objects. Agents may not write directly to source snapshots, bypass chunk validation, export without a valid manifest, or overwrite locked chunks.

### 9.2 Edit semantics

Edits can be represented as full-content replacement, line-level patch, token-level patch, AST-aware patch, or semantic rewrite. The chosen edit form depends on the file type and chunk policy.

### 9.3 Internal diffs

A chunk may maintain its own diff history. The system has two layers: an outer layer (chunk and manifest structure) and an inner layer (chunk content diffs).

---

## 10. Safety Model

**Safety rules**

- Source snapshots are immutable
- Chunk mutation must be tracked
- Writes to source are forbidden
- Exports require manifest validation
- Conflicts must not be silently merged
- History should be append-only
- Chunk content should always be hash-verified

The goal is to keep the source as a frozen truth layer while allowing agents to operate on editable projections.

---

## 11. Conflict Handling

When multiple agents edit the same region or same chunk, the system resolves conflicts in this order:

1. Exact lock ownership
2. Latest approved chunk version
3. Semantic merge attempt
4. Manual review requirement
5. Rejection

Silent overwrite is not allowed.

---

## 12. Chunk Operations

| Operation | Description |
|---|---|
| split_chunk | Break one chunk into two or more. Use when a region grows too large or semantic boundaries appear. |
| merge_chunks | Combine two or more chunks into one. Use when adjacent chunks should be treated as one region. |
| edit_chunk | Apply a patch or replacement to a chunk. |
| clone_chunk | Create a branch copy for experimentation or parallel agent work. |
| rebase_chunk | Update a chunk against a new parent or source revision. |
| lock_chunk | Prevent concurrent writes. |
| export_manifest | Rebuild the file from current chunk state. |

---

## 13. API Specification

### 13.1 Create source
`POST /sources`

### 13.2 Chunkify source
`POST /sources/{source_id}/chunkify`

### 13.3 Get chunk
`GET /chunks/{chunk_id}`

### 13.4 Edit chunk
`PATCH /chunks/{chunk_id}`

### 13.5 Split chunk
`POST /chunks/{chunk_id}/split`

### 13.6 Merge chunks
`POST /chunks/merge`

### 13.7 Lock chunk
`POST /chunks/{chunk_id}/lock`

### 13.8 Unlock chunk
`POST /chunks/{chunk_id}/unlock`

### 13.9 Get manifest
`GET /manifests/{manifest_id}`

### 13.10 Export manifest
`POST /manifests/{manifest_id}/export`

---

## 14. Storage Layout

```
munk/
  sources/      # Immutable source snapshots
  chunks/       # Mutable chunk JSON and content files
  manifests/    # Reconstruction plans
  history/      # Append-only change records
  locks/        # Lock records for concurrency control
  exports/      # Reconstructed output files
  diffs/        # Chunk-level patch records
  policies/     # Validation and safety policy definitions
```

---

## 15. Chunking Strategy

Munk uses a single line-scanning chunker with a format config table. No per-format parser is required for supported types.

### 15.1 Supported formats (v0.1)

| Format | Chunk boundary |
|---|---|
| GDScript (`.gd`) | `^func `, `^class ` |
| Markdown (`.md`) | `^#` headings |
| JSON (`.json`) | Top-level keys |
| Plain text (`.txt`) | Blank lines |

### 15.2 Chunking config

```json
{
  "gd":   { "boundaries": ["^func ", "^class "] },
  "md":   { "boundaries": ["^#"] },
  "json": { "strategy": "top-level-keys" },
  "txt":  { "boundaries": ["^\\s*$"] }
}
```

One chunker reads the config at runtime. New formats are added by extending the config table, not by writing new parsers.

### 15.3 Out of scope for v0.1

Deeply nested formats, binary files, XML, and any format requiring a full AST parser are deferred to a later version.

---

## 16. Validation Rules

Before any chunk or manifest is accepted, the system validates: JSON schema compliance, hash integrity, source reference validity, range sanity, lock state correctness, manifest ordering consistency, and export completeness.

Optional validators may include semantic consistency checks, policy checks, formatting checks, and content-specific linting.

---

## 17. Agent Workflow

1. Import immutable source snapshot
2. Chunk the source into editable units
3. Assign chunks to an agent or agent set
4. Agent edits chunk content and metadata
5. Validate updated chunks
6. Record version history
7. Update manifest if chunk membership changed
8. Export only when requested or approved

The agent may reason over the source, but it only mutates chunk state.

---

## 18. Diff Relationship

Munk is not just diffs, but diffs are still useful inside it.

**Outer layer:** structure, chunk membership, ordering, lineage.

**Inner layer:** text diffs, semantic patches, AST diffs, token diffs.

This creates a hierarchical edit model.

---

## 19. JSON Schema Sketches

### 19.1 Source schema

```json
{
  "type": "object",
  "required": ["source_id", "path", "hash", "size_bytes", "created_at"],
  "properties": {
    "source_id": { "type": "string" },
    "path": { "type": "string" },
    "hash": { "type": "string" },
    "size_bytes": { "type": "integer" },
    "mime_type": { "type": "string" },
    "created_at": { "type": "string" },
    "origin": { "type": "string" },
    "status": { "type": "string" }
  }
}
```

### 19.2 Chunk schema

```json
{
  "type": "object",
  "required": ["chunk_id", "source_id", "content", "content_hash", "version", "status"],
  "properties": {
    "chunk_id": { "type": "string" },
    "source_id": { "type": "string" },
    "parent_chunk_id": { "type": ["string", "null"] },
    "start": { "type": ["integer", "null"] },
    "end": { "type": ["integer", "null"] },
    "content": { "type": "string" },
    "content_hash": { "type": "string" },
    "version": { "type": "integer" },
    "status": { "type": "string" },
    "title": { "type": "string" },
    "description": { "type": "string" },
    "tags": { "type": "array", "items": { "type": "string" } },
    "author_agent": { "type": "string" },
    "created_at": { "type": "string" },
    "updated_at": { "type": "string" }
  }
}
```

### 19.3 Manifest schema

```json
{
  "type": "object",
  "required": ["manifest_id", "source_id", "chunks", "order", "created_at"],
  "properties": {
    "manifest_id": { "type": "string" },
    "source_id": { "type": "string" },
    "chunks": { "type": "array", "items": { "type": "string" } },
    "order": { "type": "array", "items": { "type": "string" } },
    "export_mode": { "type": "string" },
    "created_at": { "type": "string" }
  }
}
```

---

## 20. Implementation Plan

### Phase 1 — Core data model
Source, Chunk, Manifest, and History as Python dataclasses with JSON serialization. No logic yet, just the objects and the storage layout from Section 14.

### Phase 2 — Chunker
Line-scanning chunker with the format config table from Section 15. GDScript and Markdown first. Input is a file path, output is a list of Chunk objects written to the chunk store.

### Phase 3 — Editor
Single `edit_chunk` operation. Takes a chunk ID and new content, validates, increments version, writes history entry.

### Phase 4 — Assembler
Reads a manifest, pulls chunks in order, reconstructs the file into `exports/`. No writing to source.

### Phase 5 — TUI
File tree, chunk list, diff view per chunk, approve/reject controls. Built on `textual`.

### Phase 6 — API
FastAPI wrapper around the Phase 1–4 core. Stateless, JSON in and out. Implements the endpoints from Section 13.

### Phase 7 — Web app
Frontend talking to the Phase 6 API. Live preview panel, diff view, approval queue.

**Stretch goals:** Desktop and mobile clients.

Phases 1–4 are the engine. They have no UI dependencies and are independently testable. Phases 5–7 are interfaces over the same core.

---

## 21. Naming

Munk refers to: chunk-based editing, muted direct source editing, sandboxed mutation boundaries, and agent-safe projections over immutable truth.

**One-line definition:** Munk is a chunk-addressable, metadata-rich, agent-safe editing layer over immutable source files.

---

## 22. Next Steps

1. Lock the JSON schemas
2. Implement Phase 1 data model in Python
3. Implement Phase 2 chunker (GDScript + Markdown first)
4. Implement Phase 4 assembler and validate round-trip on a real file
5. Define lock and conflict rules before Phase 3 editor is built
6. Define rebase behavior before it is implemented

---

## 23. Appendix: Example Workflow

1. Import `spec.txt` as `src_001`
2. Chunk into `chk_001`, `chk_002`, `chk_003`
3. Agent edits `chk_002`
4. System increments chunk version to `v4`
5. History entry is written
6. Manifest is updated if needed
7. Export produces `spec_v2.txt`

At no point is `spec.txt` overwritten.
