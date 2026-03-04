"""Configuration enums for type-safe settings.

These enums provide type safety and IDE autocomplete for configuration values.
They inherit from str to maintain JSON serialization compatibility.
"""

from enum import Enum


class StorageBackendType(str, Enum):
    """Storage backend types.

    Determines which storage implementation is used for persistent data.
    """

    FILESYSTEM = "filesystem"
    AZURE = "azure"
    AWS = "aws"
    GCP = "gcp"


class Environment(str, Enum):
    """Deployment environments.

    Controls environment-specific behavior like logging, storage defaults,
    and URL construction.
    """

    LOCAL = "local"
    TEST = "test"
    DEV = "dev"
    PRD = "prd"
