from typing import Protocol

from airweave.core.protocols.registry import RegistryProtocol
from airweave.domains.auth_provider.types import AuthProviderRegistryEntry


class AuthProviderRegistryProtocol(RegistryProtocol[AuthProviderRegistryEntry], Protocol):
    """Auth provider registry protocol."""

    pass
