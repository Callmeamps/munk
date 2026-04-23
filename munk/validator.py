# munk/validator.py

from munk.hashing import verify_content
from munk.models import Chunk, Manifest
from munk.store import MunkStore


class ValidationError(Exception):
    """Raised when a chunk or manifest fails validation."""


def validate_chunk(chunk: Chunk, store: MunkStore) -> None:
    """
    Validate a single chunk before export.
    """
    if not store.source_exists(chunk.source_id):
        raise ValidationError(
            f"Chunk {chunk.chunk_id!r} references unknown source {chunk.source_id!r}."
        )

    if not verify_content(chunk.content, chunk.content_hash):
        raise ValidationError(
            f"Chunk {chunk.chunk_id!r} content hash mismatch."
        )

    if chunk.status == "archived":
        raise ValidationError(
            f"Chunk {chunk.chunk_id!r} is archived and cannot be exported."
        )


def validate_manifest(manifest: Manifest, store: MunkStore) -> list[Chunk]:
    """
    Validate a manifest and all its chunks. Returns the ordered Chunks.
    """
    if not store.source_exists(manifest.source_id):
        raise ValidationError(
            f"Manifest {manifest.manifest_id!r} references unknown source {manifest.source_id!r}."
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
