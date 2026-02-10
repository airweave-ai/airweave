"""Utilities for search functionality."""

from typing import Any, Dict, Optional


def validate_filter_dict(filter_dict: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Validate a filter dictionary has the correct structure.

    Args:
        filter_dict: Dictionary representation of a filter with must/should/must_not keys

    Returns:
        The validated filter dict, or None if input is None

    Raises:
        ValueError: If the filter format is invalid
    """
    if not filter_dict:
        return None

    valid_top_level_keys = {"must", "must_not", "should", "minimum_should_match"}
    unknown_keys = set(filter_dict.keys()) - valid_top_level_keys
    if unknown_keys:
        raise ValueError(
            f"Invalid filter format: unknown top-level keys {unknown_keys}. "
            f"Allowed keys: {valid_top_level_keys}"
        )

    for group_key in ("must", "must_not", "should"):
        if group_key in filter_dict and not isinstance(filter_dict[group_key], list):
            raise ValueError(f"Invalid filter format: '{group_key}' must be a list of conditions")

    return filter_dict


def validate_filter_keys(filter_dict: Dict[str, Any], allowed_keys: set[str]) -> bool:
    """Validate that filter only uses allowed field keys.

    Args:
        filter_dict: Filter dict to validate
        allowed_keys: Set of allowed field keys

    Returns:
        True if valid, raises ValueError if invalid
    """
    # TODO: Implement recursive validation of field keys in filter conditions
    # For now, return True to allow all filters
    return True
