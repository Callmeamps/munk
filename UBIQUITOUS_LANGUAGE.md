# Ubiquitous Language

## Core Entities

| Term             | Definition                                      | Aliases to avoid          |
| ---------------- | ----------------------------------------------- | ------------------------- |
| **Source**       | Immutable, locked snapshot of an original file. |                           |
| **Chunk**        | Mutable working unit derived from a Source.     |                           |
| **Manifest**     | Reconstruction plan for a Source via Chunks.    |                           |
| **ChunkHistory** | Append-only record of actions on a Chunk.       | History entry             |
| **Lock**         | Exclusive write lock on a Chunk.                 |                           |

## Lifecycle States

| Term             | Definition                                      | Aliases to avoid |
| ---------------- | ----------------------------------------------- | ---------------- |
| **Chunk Status** | State of a Chunk: draft, reviewed, approved, locked, archived. |                  |
| **Source Status** | Always "locked" after registration, immutable.  |                  |
| **Export Mode**   | Method to rebuild files from Manifests, currently only "rebuild". |                  |

## Actions

| Term         | Definition                                      | Aliases to avoid |
| ------------ | ----------------------------------------------- | ---------------- |
| **Chunkify** | Split a Source into Chunks.                     |                  |
| **Edit**     | Modify a Chunk's content, increment version.    | Update           |
| **Lock**     | Acquire exclusive write access to a Chunk.      |                  |
| **Unlock**   | Release a Chunk's write lock.                    |                  |
| **Assemble** | Rebuild a file from a Manifest's ordered Chunks. | Export, rebuild  |
| **Validate** | Check assembled output integrity.                |                  |

## Actors

| Term         | Definition                                      | Aliases to avoid |
| ------------ | ----------------------------------------------- | ---------------- |
| **Actor**    | Identity performing actions on Chunks/Sources.   | Author Agent     |

## Relationships

- A **Source** is split into N **Chunks** via Chunkify.
- A **Chunk** belongs to exactly one **Source**.
- A **Manifest** references 1 **Source** and N **Chunks**.
- A **Chunk** has 0+ **ChunkHistory** entries.
- A **Lock** is held by 1 **Actor** on 1 **Chunk**.

## Example dialogue

> **Dev:** "When I **Chunkify** a **Source**, do all **Chunks** start as draft?"
> **Domain expert:** "Yes — every new **Chunk** from Chunkify has status draft. Only after review can you set it to reviewed or approved."
> **Dev:** "Can an **Actor** edit a locked **Chunk**?"
> **Domain expert:** "No — you must **Unlock** it first, or acquire a **Lock** if it's not already held."
> **Dev:** "Does **Assemble** use the **Manifest**'s order field?"
> **Domain expert:** "Exactly — the **Manifest**'s order is the authoritative sequence for concatenating **Chunks** during export."

## Flagged ambiguities

- "author_agent" (Chunk field) and "actor" (ChunkHistory field) refer to the same concept (entity performing an action on a Chunk). Canonical term: **Actor**, avoid "Author Agent".
- "content" is used for both original **Source** file content and derived **Chunk** text. Qualify as "Source Content" or "Chunk Content" where ambiguous.
- "rebuild" is used as both an **Export Mode** and a synonym for **Assemble**. Canonical term for the action: **Assemble**, avoid "rebuild" for the action.
