"""Tests for settings field validators added by CASA-22."""

import pytest
from pydantic import ValidationError

# Minimal required env for Settings construction.  Every field without a
# default must be present; values are deliberately valid so that the test
# can override *only* the field under test and trigger the expected error.
_BASE_ENV: dict[str, str] = {
    "ENVIRONMENT": "local",
    "FIRST_SUPERUSER": "test@example.com",
    "FIRST_SUPERUSER_PASSWORD": "testpassword123",
    "ENCRYPTION_KEY": "SpgLrrEEgJ/7QdhSMSvagL1juEY5eoyCG0tZN7OSQV0=",
    "STATE_SECRET": "test-state-secret-key-minimum-32-characters-long",
    "SVIX_JWT_SECRET": "test-svix-jwt-secret-minimum-32-characters-long",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_USER": "airweave",
    "POSTGRES_PASSWORD": "some-test-password",
}


def _build_settings(monkeypatch, overrides: dict[str, str]):
    """Set env vars from _BASE_ENV + overrides, then construct Settings."""
    for key, value in {**_BASE_ENV, **overrides}.items():
        monkeypatch.setenv(key, value)

    # Remove any override key whose value is the sentinel _UNSET so that
    # the env var is truly absent.
    for key, value in overrides.items():
        if value is _UNSET:
            monkeypatch.delenv(key, raising=False)

    from airweave.core.config.settings import Settings

    return Settings()


_UNSET = object()


# ── INSTANT_SEARCH_MIN_SCORE ────────────────────────────────────────


class TestValidateInstantSearchMinScore:
    def test_defaults_to_sane_threshold(self, monkeypatch):
        s = _build_settings(monkeypatch, {})
        assert s.INSTANT_SEARCH_MIN_SCORE == 1.2

    def test_rejects_negative(self, monkeypatch):
        with pytest.raises(ValidationError, match="INSTANT_SEARCH_MIN_SCORE"):
            _build_settings(monkeypatch, {"INSTANT_SEARCH_MIN_SCORE": "-0.1"})

    def test_accepts_zero_to_disable_filtering(self, monkeypatch):
        s = _build_settings(monkeypatch, {"INSTANT_SEARCH_MIN_SCORE": "0"})
        assert s.INSTANT_SEARCH_MIN_SCORE == 0.0


# ── SVIX_JWT_SECRET ─────────────────────────────────────────────────


class TestValidateSvixJwtSecret:
    def test_rejects_empty(self, monkeypatch):
        with pytest.raises(ValidationError, match="SVIX_JWT_SECRET"):
            _build_settings(monkeypatch, {"SVIX_JWT_SECRET": ""})

    def test_rejects_short(self, monkeypatch):
        with pytest.raises(ValidationError, match="at least 32 characters"):
            _build_settings(monkeypatch, {"SVIX_JWT_SECRET": "too-short"})

    def test_accepts_valid(self, monkeypatch):
        secret = "a" * 32
        s = _build_settings(monkeypatch, {"SVIX_JWT_SECRET": secret})
        assert s.SVIX_JWT_SECRET == secret


# ── FIRST_SUPERUSER_PASSWORD ────────────────────────────────────────


class TestValidateFirstSuperuserPassword:
    def test_rejects_short_in_prd(self, monkeypatch):
        with pytest.raises(ValidationError, match="at least 12 characters"):
            _build_settings(
                monkeypatch,
                {"ENVIRONMENT": "prd", "FIRST_SUPERUSER_PASSWORD": "short"},
            )

    def test_rejects_banned_in_dev(self, monkeypatch):
        with pytest.raises(ValidationError, match="well-known default"):
            _build_settings(
                monkeypatch,
                {"ENVIRONMENT": "dev", "FIRST_SUPERUSER_PASSWORD": "airweave1234!"},
            )

    def test_error_does_not_leak_password(self, monkeypatch):
        password = "airweave1234!"
        with pytest.raises(ValidationError) as exc_info:
            _build_settings(
                monkeypatch,
                {"ENVIRONMENT": "prd", "FIRST_SUPERUSER_PASSWORD": password},
            )
        # Check that our custom error *message* doesn't echo the password.
        # (Pydantic's ValidationError repr includes input_value metadata
        # which is framework-level, not our error text.)
        messages = [e["msg"] for e in exc_info.value.errors()]
        for msg in messages:
            assert password not in msg

    def test_accepts_weak_in_local(self, monkeypatch):
        s = _build_settings(
            monkeypatch,
            {"ENVIRONMENT": "local", "FIRST_SUPERUSER_PASSWORD": "admin"},
        )
        assert s.FIRST_SUPERUSER_PASSWORD == "admin"

    def test_accepts_weak_in_test(self, monkeypatch):
        s = _build_settings(
            monkeypatch,
            {"ENVIRONMENT": "test", "FIRST_SUPERUSER_PASSWORD": "admin"},
        )
        assert s.FIRST_SUPERUSER_PASSWORD == "admin"

    def test_accepts_strong_in_prd(self, monkeypatch):
        strong = "4v3ry-$tr0ng-pa$$w0rd!"
        s = _build_settings(
            monkeypatch,
            {"ENVIRONMENT": "prd", "FIRST_SUPERUSER_PASSWORD": strong},
        )
        assert s.FIRST_SUPERUSER_PASSWORD == strong


# ── FIRST_SUPERUSER (email) ─────────────────────────────────────────


class TestValidateFirstSuperuserEmail:
    def test_rejects_banned_in_prd(self, monkeypatch):
        with pytest.raises(ValidationError, match="placeholder email"):
            _build_settings(
                monkeypatch,
                {"ENVIRONMENT": "prd", "FIRST_SUPERUSER": "admin@example.com"},
            )

    def test_rejects_banned_in_dev(self, monkeypatch):
        with pytest.raises(ValidationError, match="placeholder email"):
            _build_settings(
                monkeypatch,
                {"ENVIRONMENT": "dev", "FIRST_SUPERUSER": "root@example.com"},
            )

    def test_case_insensitive_rejection(self, monkeypatch):
        with pytest.raises(ValidationError, match="placeholder email"):
            _build_settings(
                monkeypatch,
                {"ENVIRONMENT": "prd", "FIRST_SUPERUSER": "Admin@Example.COM"},
            )

    def test_accepts_banned_in_local(self, monkeypatch):
        s = _build_settings(
            monkeypatch,
            {"ENVIRONMENT": "local", "FIRST_SUPERUSER": "admin@example.com"},
        )
        assert s.FIRST_SUPERUSER == "admin@example.com"

    def test_accepts_banned_in_test(self, monkeypatch):
        s = _build_settings(
            monkeypatch,
            {"ENVIRONMENT": "test", "FIRST_SUPERUSER": "admin@example.com"},
        )
        assert s.FIRST_SUPERUSER == "admin@example.com"

    def test_accepts_custom_email_in_prd(self, monkeypatch):
        email = "ops@mycompany.com"
        s = _build_settings(
            monkeypatch,
            {"ENVIRONMENT": "prd", "FIRST_SUPERUSER": email},
        )
        assert s.FIRST_SUPERUSER == email
