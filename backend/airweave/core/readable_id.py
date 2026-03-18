"""Readable ID generation using a CSPRNG.

Provides a single ``generate_readable_id`` helper that converts a
human-readable name into a URL-safe slug with a random suffix, e.g.
``"finance-data-ab12x9"``.  The suffix is drawn from
:func:`secrets.choice` (CSPRNG) rather than :mod:`random` (Mersenne
Twister).
"""

import re
import secrets
import string

_ALPHABET = string.ascii_lowercase + string.digits


def generate_readable_id(name: str) -> str:
    """Generate a readable ID from a name.

    Converts the name to lowercase, replaces spaces with hyphens,
    removes special characters, and appends a cryptographically random
    6-character suffix to ensure uniqueness.

    Args:
        name: The human-readable name to convert.

    Returns:
        A URL-safe readable identifier (e.g. ``"finance-data-ab123x"``).
    """
    # Convert to lowercase and replace spaces with hyphens
    readable_id = name.lower().strip()

    # Replace any character that's not a letter, number, or space with nothing
    readable_id = re.sub(r"[^a-z0-9\s]", "", readable_id)
    # Replace spaces with hyphens
    readable_id = re.sub(r"\s+", "-", readable_id)
    # Ensure no consecutive hyphens
    readable_id = re.sub(r"-+", "-", readable_id)
    # Trim hyphens from start and end
    readable_id = readable_id.strip("-")

    # Add random alphanumeric suffix (CSPRNG)
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(6))
    readable_id = f"{(readable_id + '-') if readable_id else ''}{suffix}"

    return readable_id
