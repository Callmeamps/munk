# munk/chunker_config.py
import re
from dataclasses import dataclass

# Each entry maps a file extension to a list of compiled boundary patterns.
# A line matching any pattern starts a new chunk.
# The matching line is included at the top of the new chunk (it is not discarded).
CHUNKER_CONFIG: dict[str, list[re.Pattern]] = {
    "gd": [re.compile(r"^func "), re.compile(r"^class ")],
    "md": [re.compile(r"^#")],
    "txt": [re.compile(r"^\s*$")],
}

# JSON is handled separately via a dedicated strategy (see chunker.py).
JSON_STRATEGY = "top-level-keys"

@dataclass
class ChunkingConfig:
    """Configuration for chunking strategies."""
    chunk_size: int = 1000  # Target characters per chunk
    chunk_overlap: int = 200  # Character overlap between chunks
    max_chunk_size: int = 2000  # Maximum chunk size
    min_chunk_size: int = 100  # Minimum chunk size
    semantic_similarity_threshold: float = 0.8  # Threshold for semantic chunking
    preserve_structure: bool = True  # Preserve document structure (e.g., headings)

SUPPORTED_EXTENSIONS = set(CHUNKER_CONFIG.keys()) | {"json"}

def get_boundaries(ext: str) -> list[re.Pattern]:
    """Return boundary patterns for a file extension, or empty list if unsupported."""
    return CHUNKER_CONFIG.get(ext.lower(), [])