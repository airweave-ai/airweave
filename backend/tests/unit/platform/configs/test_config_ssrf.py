"""Tests for SSRF validators on config models."""

import pytest
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def _pin_ssrf_private_networks(monkeypatch):
    monkeypatch.setattr(
        "airweave.platform.utils.ssrf._get_allow_private_default",
        lambda: False,
    )

from airweave.platform.configs.auth import (
    BaseDatabaseAuthConfig,
    ElasticsearchAuthConfig,
    Neo4jAuthConfig,
    ODBCAuthConfig,
    ServiceNowAuthConfig,
    URLAndAPIKeyAuthConfig,
    WeaviateAuthConfig,
)
from airweave.platform.configs.config import (
    CalComConfig,
    Document360Config,
    SalesforceConfig,
    SharePoint2019V2Config,
    SharePointOnlineConfig,
    ShopifyConfig,
    SlabConfig,
)

# ---------------------------------------------------------------------------
# Auth config models
# ---------------------------------------------------------------------------


class TestURLAndAPIKeyAuthConfig:
    def test_rejects_loopback(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            URLAndAPIKeyAuthConfig(url="http://127.0.0.1/api", api_key="key123")

    def test_accepts_public_url(self):
        cfg = URLAndAPIKeyAuthConfig(url="https://api.example.com", api_key="key123")
        assert cfg.url == "https://api.example.com"


class TestODBCAuthConfig:
    def test_rejects_metadata_ip(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            ODBCAuthConfig(
                host="169.254.169.254",
                port=1433,
                database="db",
                username="user",
                password="pass",
                schema="dbo",
                tables="t1",
            )

    def test_accepts_public_host(self):
        cfg = ODBCAuthConfig(
            host="db.example.com",
            port=1433,
            database="db",
            username="user",
            password="pass",
            schema="dbo",
            tables="t1",
        )
        assert cfg.host == "db.example.com"


class TestBaseDatabaseAuthConfig:
    def test_rejects_loopback(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            BaseDatabaseAuthConfig(
                host="127.0.0.1",
                port=5432,
                database="db",
                user="postgres",
                password="secret",
            )

    def test_accepts_public_host(self):
        cfg = BaseDatabaseAuthConfig(
            host="db.example.com",
            port=5432,
            database="db",
            user="postgres",
            password="secret",
        )
        assert cfg.host == "db.example.com"


class TestElasticsearchAuthConfig:
    def test_rejects_loopback_url(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            ElasticsearchAuthConfig(
                host="http://127.0.0.1",
                port=9200,
            )

    def test_accepts_public_url(self):
        cfg = ElasticsearchAuthConfig(
            host="https://es.example.com",
            port=9200,
        )
        assert cfg.host == "https://es.example.com"


class TestWeaviateAuthConfig:
    def test_rejects_metadata(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            WeaviateAuthConfig(
                cluster_url="http://169.254.169.254",
                api_key="key123",
            )

    def test_accepts_public_url(self):
        cfg = WeaviateAuthConfig(
            cluster_url="https://my-cluster.weaviate.network",
            api_key="key123",
        )
        assert cfg.cluster_url == "https://my-cluster.weaviate.network"


class TestNeo4jAuthConfig:
    def test_rejects_loopback_uri(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            Neo4jAuthConfig(
                uri="bolt://127.0.0.1:7687",
                username="neo4j",
                password="secret",
            )

    def test_accepts_public_uri(self):
        cfg = Neo4jAuthConfig(
            uri="bolt://neo4j.example.com:7687",
            username="neo4j",
            password="secret",
        )
        assert cfg.uri == "bolt://neo4j.example.com:7687"


class TestServiceNowAuthConfig:
    def test_rejects_loopback_url(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            ServiceNowAuthConfig(
                url="http://127.0.0.1",
                username="admin",
                password="secret",
            )

    def test_accepts_public_url(self):
        cfg = ServiceNowAuthConfig(
            url="https://myinstance.service-now.com",
            username="admin",
            password="secret",
        )
        assert cfg.url == "https://myinstance.service-now.com"

    def test_none_url_with_subdomain(self):
        cfg = ServiceNowAuthConfig(
            subdomain="myinstance",
            username="admin",
            password="secret",
        )
        assert "myinstance" in cfg.url


# ---------------------------------------------------------------------------
# Source / destination config models
# ---------------------------------------------------------------------------


class TestDocument360Config:
    def test_rejects_loopback_base_url(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            Document360Config(base_url="http://127.0.0.1/api")

    def test_none_base_url_passes(self):
        cfg = Document360Config(base_url=None)
        assert cfg.base_url is None

    def test_accepts_public_base_url(self):
        cfg = Document360Config(base_url="https://apihub.document360.io")
        assert cfg.base_url == "https://apihub.document360.io"


class TestCalComConfig:
    def test_rejects_metadata_host(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            CalComConfig(host="http://169.254.169.254")

    def test_accepts_public_host(self):
        cfg = CalComConfig(host="https://cal.example.com")
        assert cfg.host == "https://cal.example.com"


class TestSharePoint2019V2Config:
    def test_rejects_loopback(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            SharePoint2019V2Config(
                site_url="http://127.0.0.1/sites/test",
                ad_server="dc.contoso.local",
                ad_search_base="DC=contoso,DC=local",
            )

    def test_accepts_public_site(self):
        cfg = SharePoint2019V2Config(
            site_url="https://sharepoint.contoso.com/sites/Marketing",
            ad_server="dc.contoso.local",
            ad_search_base="DC=contoso,DC=local",
        )
        assert cfg.site_url == "https://sharepoint.contoso.com/sites/Marketing"


class TestSharePointOnlineConfig:
    def test_rejects_loopback(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            SharePointOnlineConfig(site_url="http://127.0.0.1")

    def test_empty_site_url_rejected(self):
        with pytest.raises(ValidationError):
            SharePointOnlineConfig(site_url="")

    def test_missing_site_url_rejected(self):
        with pytest.raises(ValidationError):
            SharePointOnlineConfig()

    def test_accepts_valid_site_url(self):
        cfg = SharePointOnlineConfig(
            site_url="https://contoso.sharepoint.com/sites/Marketing"
        )
        assert cfg.site_url == "https://contoso.sharepoint.com/sites/Marketing"


class TestSalesforceConfig:
    def test_rejects_metadata_instance(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            SalesforceConfig(instance_url="https://169.254.169.254")

    def test_none_instance_passes(self):
        cfg = SalesforceConfig(instance_url=None)
        assert cfg.instance_url is None

    def test_accepts_public_instance(self):
        cfg = SalesforceConfig(instance_url="https://myorg.my.salesforce.com")
        assert cfg.instance_url == "myorg.my.salesforce.com"


class TestSlabConfig:
    def test_rejects_localhost(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            SlabConfig(host="localhost")

    def test_accepts_public_host(self):
        cfg = SlabConfig(host="myteam.slab.com")
        assert cfg.host == "myteam.slab.com"


class TestShopifyConfig:
    def test_rejects_metadata(self):
        with pytest.raises(ValidationError, match="SSRF|blocked"):
            ShopifyConfig(shop_domain="169.254.169.254")

    def test_accepts_valid_domain(self):
        cfg = ShopifyConfig(shop_domain="my-store.myshopify.com")
        assert cfg.shop_domain == "my-store.myshopify.com"
