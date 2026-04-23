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
