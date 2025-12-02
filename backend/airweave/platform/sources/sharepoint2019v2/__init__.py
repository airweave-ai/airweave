"""SharePoint 2019 On-Premise V2 Source.

This package provides a connector for SharePoint 2019 On-Premise using the REST API.

Modules:
    source: Main source class implementing BaseSource
    client: SharePoint REST API client with NTLM auth
    builders: Entity builder functions
    acl: Access control helpers
"""

from airweave.platform.sources.sharepoint2019v2.source import SharePoint2019V2Source

__all__ = ["SharePoint2019V2Source"]
