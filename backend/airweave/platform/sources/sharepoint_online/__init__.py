"""SharePoint Online source connector.

Uses Microsoft Graph API for content sync and Entra ID for access control.
Two variants: OAuth (delegated) and App (client credentials).
"""

from airweave.platform.sources.sharepoint_online.source import (
    SharePointOnlineAppSource,
    SharePointOnlineSource,
)

__all__ = ["SharePointOnlineSource", "SharePointOnlineAppSource"]
