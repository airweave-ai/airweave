"""SharePoint Online source connector.

Uses Microsoft Graph API for content sync and Entra ID for access control.
"""

from airweave.platform.sources.sharepoint_online.source import SharePointOnlineSource

__all__ = ["SharePointOnlineSource"]
