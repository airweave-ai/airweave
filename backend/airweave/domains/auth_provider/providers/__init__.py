"""Auth provider implementations."""

from .composio import ComposioAuthProvider
from .custom import CustomAuthProvider
from .pipedream import PipedreamAuthProvider

ALL_AUTH_PROVIDERS: list[type] = [
    ComposioAuthProvider,
    CustomAuthProvider,
    PipedreamAuthProvider,
]
