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
