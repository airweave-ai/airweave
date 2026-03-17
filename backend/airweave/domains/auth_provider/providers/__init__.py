"""Auth provider implementations."""

from .composio import ComposioAuthProvider
from .pipedream import PipedreamAuthProvider

ALL_AUTH_PROVIDERS: list[type] = [
    ComposioAuthProvider,
    PipedreamAuthProvider,
]
