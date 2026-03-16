"""Utilities for sanitizing filenames into filesystem-safe strings."""

import os
import re
import unicodedata


def safe_filename(name: str, default_ext: str = ".html") -> str:
    """Return a Unicode-normalized, filesystem-safe filename with a valid extension.

    Falls back to 'untitled' if sanitization removes all characters.
    Preserves existing extensions and appends default_ext only if missing.
    """
    # Be defensive: some call sites may pass None or non-str objects.
    if name is None:
        name = ""
    else:
        name = str(name)

    name = unicodedata.normalize("NFKC", name).strip()
    name = re.sub(r"[\\/]+", "_", name)
    name = re.sub(r"\s+", " ", name)
    name = "".join(c for c in name if c.isalnum() or c in "._- ")
    name = name.rstrip(". ")

    # Fallback if name becomes empty
    if not name:
        name = "untitled"

    # Preserve existing extension; only append if none
    ext = os.path.splitext(name)[1]
    if not ext and default_ext:
        name += default_ext

    return name
