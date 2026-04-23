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
    """
    if not store.manifest_exists(manifest_id):
        raise AssemblyError(f"Manifest {manifest_id!r} not found.")

    manifest = store.load_manifest(manifest_id)

    # Validate everything before writing
    try:
        chunks = validate_manifest(manifest, store)
    except Exception as e:
        raise AssemblyError(f"Validation failed: {e}")

    content = separator.join(chunk.content for chunk in chunks)
    output_path = store.write_export(output_filename, content)

    return output_path
