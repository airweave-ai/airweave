"""Unit tests for the health-service factory wiring.

These tests verify that ``_create_health_service`` correctly partitions
probes into critical / informational based on ``Settings`` and that the
timeout is forwarded to ``HealthService``.
"""

from unittest.mock import MagicMock, patch

from airweave.core.container.factory import _create_health_service


def _make_settings(**overrides) -> MagicMock:
    """Build a minimal mock ``Settings`` with health-related defaults."""
    defaults = {
        "HEALTH_CHECK_TIMEOUT": 5.0,
        "HEALTH_CRITICAL_PROBES": "postgres",
    }
    defaults.update(overrides)

    settings = MagicMock()
    for key, value in defaults.items():
        setattr(settings, key, value)

    # The property returns a frozenset parsed from the raw string.
    raw = defaults["HEALTH_CRITICAL_PROBES"]
    settings.health_critical_probes = frozenset(
        name.strip() for name in raw.split(",") if name.strip()
    )
    return settings


def _patches():
    """Context-manager stack that stubs out infra singletons."""
    engine = MagicMock(name="engine")
    redis_mod = MagicMock(name="redis_client_module")
    temporal_cls = MagicMock(name="TemporalClient")
    return (
        patch("airweave.db.session.health_check_engine", engine),
        patch("airweave.core.redis_client.redis_client", redis_mod),
        patch(
            "airweave.platform.temporal.client.TemporalClient",
            temporal_cls,
        ),
        engine,
        redis_mod,
        temporal_cls,
    )


class TestDefaultSettings:
    """Default settings: postgres critical, redis+temporal informational."""

    def test_probe_partitioning(self):
        """Postgres is critical; redis and temporal are informational."""
        p_engine, p_redis, p_temporal, engine, redis_mod, temporal_cls = _patches()
        with p_engine, p_redis, p_temporal:
            settings = _make_settings()
            svc = _create_health_service(settings)

        critical_names = {p.name for p in svc._critical}
        info_names = {p.name for p in svc._informational}

        assert critical_names == {"postgres"}
        assert info_names == {"redis", "temporal"}


class TestCriticalOverride:
    """Overriding ``HEALTH_CRITICAL_PROBES``."""

    def test_postgres_and_redis_critical(self):
        """Both postgres and redis become critical when listed."""
        p_engine, p_redis, p_temporal, engine, redis_mod, temporal_cls = _patches()
        with p_engine, p_redis, p_temporal:
            settings = _make_settings(
                HEALTH_CRITICAL_PROBES="postgres,redis",
            )
            svc = _create_health_service(settings)

        critical_names = {p.name for p in svc._critical}
        assert critical_names == {"postgres", "redis"}
        assert {p.name for p in svc._informational} == {"temporal"}


class TestUnknownCriticalProbe:
    """Unknown names in the critical set log a warning but don't crash."""

    def test_logs_warning(self):
        """A warning is emitted for probe names not in the registry."""
        p_engine, p_redis, p_temporal, engine, redis_mod, temporal_cls = _patches()
        with (
            p_engine,
            p_redis,
            p_temporal,
            patch("airweave.core.container.factory.logger") as mock_logger,
        ):
            settings = _make_settings(
                HEALTH_CRITICAL_PROBES="postgres,nonexistent",
            )
            svc = _create_health_service(settings)

        mock_logger.warning.assert_called_once()
        msg = mock_logger.warning.call_args[0][0]
        assert "unknown probes" in msg.lower()
        # Still builds successfully.
        assert {p.name for p in svc._critical} == {"postgres"}


class TestCustomTimeout:
    """``HEALTH_CHECK_TIMEOUT`` is forwarded to ``HealthService``."""

    def test_timeout_passed_through(self):
        """Custom timeout value reaches the service instance."""
        p_engine, p_redis, p_temporal, engine, redis_mod, temporal_cls = _patches()
        with p_engine, p_redis, p_temporal:
            settings = _make_settings(HEALTH_CHECK_TIMEOUT=2.0)
            svc = _create_health_service(settings)

        assert svc._timeout == 2.0
