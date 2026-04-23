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
