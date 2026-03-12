"""Tests for SSRF protection utilities."""

import pytest

from airweave.platform.utils.ssrf import SSRFViolation, validate_host, validate_url

# ---------------------------------------------------------------------------
# Scheme enforcement
# ---------------------------------------------------------------------------


class TestSchemeEnforcement:
    """Verify that non-HTTP(S) schemes are rejected."""

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://ftp.example.com/secret",
            "gopher://evil.com/1",
            "dict://evil.com:1337/info",
        ],
    )
    def test_blocked_schemes(self, url: str):
        with pytest.raises(SSRFViolation, match="blocked scheme"):
            validate_url(url)

    @pytest.mark.parametrize("url", ["http://example.com", "https://example.com"])
    def test_allowed_schemes(self, url: str):
        assert validate_url(url) == url


# ---------------------------------------------------------------------------
# Metadata IP addresses (always blocked, even with allow_private=True)
# ---------------------------------------------------------------------------


class TestMetadataBlocking:
    """Verify cloud metadata endpoints are always blocked."""

    @pytest.mark.parametrize(
        "target",
        [
            "http://169.254.169.254/latest/meta-data/",
            "http://[fd00:ec2::254]/latest/meta-data/",
            "http://100.100.100.200/latest/meta-data/",
        ],
    )
    def test_metadata_ips_blocked(self, target: str):
        with pytest.raises(SSRFViolation, match="blocked metadata IP"):
            validate_url(target)

    @pytest.mark.parametrize(
        "target",
        [
            "http://169.254.169.254/",
            "http://100.100.100.200/",
        ],
    )
    def test_metadata_ips_blocked_even_allow_private(self, target: str):
        with pytest.raises(SSRFViolation, match="blocked metadata"):
            validate_url(target, allow_private=True)

    @pytest.mark.parametrize(
        "hostname",
        [
            "metadata.google.internal",
            "metadata.goog",
        ],
    )
    def test_metadata_hostnames_blocked(self, hostname: str):
        with pytest.raises(SSRFViolation, match="blocked hostname"):
            validate_url(f"http://{hostname}/computeMetadata/v1/")

    def test_metadata_hostnames_blocked_allow_private(self):
        with pytest.raises(SSRFViolation, match="blocked hostname"):
            validate_url(
                "http://metadata.google.internal/computeMetadata/v1/",
                allow_private=True,
            )


# ---------------------------------------------------------------------------
# Loopback / private / link-local IP blocking
# ---------------------------------------------------------------------------


class TestPrivateIPBlocking:
    """Verify private network IPs are blocked by default."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://127.0.0.2:8080/admin",
            "http://10.0.0.1/",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
            "http://[::1]/",
            "http://[fe80::1]/",
            "http://[fd00::1]/",
        ],
    )
    def test_private_ips_blocked_by_default(self, url: str):
        with pytest.raises(SSRFViolation):
            validate_url(url, allow_private=False)

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://192.168.1.1/",
            "http://[::1]/",
        ],
    )
    def test_private_ips_allowed_when_flag_set(self, url: str):
        assert validate_url(url, allow_private=True) == url


# ---------------------------------------------------------------------------
# Unspecified addresses
# ---------------------------------------------------------------------------


class TestUnspecifiedAddresses:
    """Verify 0.0.0.0 and :: are blocked."""

    @pytest.mark.parametrize("url", ["http://0.0.0.0/", "http://[::]/"])
    def test_unspecified_blocked(self, url: str):
        with pytest.raises(SSRFViolation, match="blocked unspecified"):
            validate_url(url, allow_private=False)


# ---------------------------------------------------------------------------
# Hostname blocking
# ---------------------------------------------------------------------------


class TestHostnameBlocking:
    """Verify dangerous hostnames are rejected."""

    @pytest.mark.parametrize(
        "hostname",
        [
            "localhost",
            "localhost.localdomain",
            "LOCALHOST",  # case-insensitive
        ],
    )
    def test_localhost_blocked(self, hostname: str):
        with pytest.raises(SSRFViolation, match="blocked hostname"):
            validate_url(f"http://{hostname}/admin")

    def test_localhost_host_blocked(self):
        with pytest.raises(SSRFViolation, match="blocked hostname"):
            validate_host("localhost")


# ---------------------------------------------------------------------------
# IP encoding tricks (octal, hex, shorthand)
# ---------------------------------------------------------------------------


class TestIPEncodingTricks:
    """Verify alternative IP notations are caught via socket.inet_aton."""

    @pytest.mark.parametrize(
        "ip",
        [
            "0177.0.0.1",  # octal loopback
            "0x7f000001",  # hex loopback (single integer)
            "127.1",  # shorthand loopback
        ],
    )
    def test_octal_hex_shorthand_blocked(self, ip: str):
        with pytest.raises(SSRFViolation):
            validate_url(f"http://{ip}/", allow_private=False)


# ---------------------------------------------------------------------------
# IPv6 edge cases
# ---------------------------------------------------------------------------


class TestIPv6:
    """Verify IPv6 blocking including mapped addresses."""

    def test_ipv6_loopback(self):
        with pytest.raises(SSRFViolation):
            validate_url("http://[::1]/", allow_private=False)

    def test_ipv4_mapped_ipv6_loopback(self):
        with pytest.raises(SSRFViolation):
            validate_host("::ffff:127.0.0.1", allow_private=False)

    def test_ipv4_mapped_ipv6_metadata(self):
        with pytest.raises(SSRFViolation, match="blocked metadata"):
            validate_host("::ffff:169.254.169.254")

    def test_ipv6_link_local(self):
        with pytest.raises(SSRFViolation):
            validate_url("http://[fe80::1]/", allow_private=False)


# ---------------------------------------------------------------------------
# Relative and protocol-relative URLs
# ---------------------------------------------------------------------------


class TestRelativeURLs:
    """Verify relative URLs pass and protocol-relative URLs are checked."""

    @pytest.mark.parametrize(
        "url",
        [
            "/api/v1/users",
            "api/v1/users",
            "",
        ],
    )
    def test_relative_urls_pass(self, url: str):
        assert validate_url(url) == url

    def test_protocol_relative_metadata_blocked(self):
        with pytest.raises(SSRFViolation, match="blocked metadata"):
            validate_url("//169.254.169.254/latest/meta-data/")

    def test_protocol_relative_localhost_blocked(self):
        with pytest.raises(SSRFViolation, match="blocked hostname"):
            validate_url("//localhost/admin")


# ---------------------------------------------------------------------------
# Public URLs (should always pass)
# ---------------------------------------------------------------------------


class TestPublicURLs:
    """Verify legitimate public URLs pass validation."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://api.github.com/repos",
            "https://google.com/search",
            "https://api.notion.com/v1/users/me",
            "http://example.com:8080/path",
        ],
    )
    def test_public_urls_pass(self, url: str):
        assert validate_url(url) == url


# ---------------------------------------------------------------------------
# validate_host edge cases
# ---------------------------------------------------------------------------


class TestValidateHost:
    """Tests for the bare hostname/IP validator."""

    def test_empty_host_passes(self):
        assert validate_host("") == ""

    def test_public_hostname_passes(self):
        assert validate_host("db.example.com") == "db.example.com"

    def test_loopback_ip_blocked(self):
        with pytest.raises(SSRFViolation):
            validate_host("127.0.0.1", allow_private=False)

    def test_private_ip_allowed_when_flag_set(self):
        assert validate_host("10.0.0.1", allow_private=True) == "10.0.0.1"

    def test_metadata_ip_blocked(self):
        with pytest.raises(SSRFViolation, match="blocked metadata"):
            validate_host("169.254.169.254")

    def test_host_whitespace_preserved_in_return_value(self):
        assert validate_host("  db.example.com  ") == "  db.example.com  "

    def test_url_with_port(self):
        assert validate_url("https://example.com:443/path") == "https://example.com:443/path"

    def test_mixed_case_hostname_blocked(self):
        with pytest.raises(SSRFViolation, match="blocked hostname"):
            validate_host("METADATA.GOOGLE.INTERNAL")
