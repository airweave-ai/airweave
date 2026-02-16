"""All auth provider connectors."""

from .composio import ComposioAuthProvider
from .pipedream import PipedreamAuthProvider

ALL_AUTH_PROVIDERS: list[type] = [
    ComposioAuthProvider,
    PipedreamAuthProvider,
]
