"""Content hashing utility."""

import hashlib


def hash_content(content: str) -> str:
    """Return the SHA-256 hex digest of the given content string.

    Args:
        content: The text content to hash.

    Returns:
        A lowercase hex string of the SHA-256 digest.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
