"""Unit tests for health probe adapters."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from airweave.schemas.health import CheckStatus


# ---------------------------------------------------------------------------
# PostgresHealthProbe
# ---------------------------------------------------------------------------


class TestPostgresHealthProbe:
    """Tests for the Postgres adapter."""

    @pytest.mark.asyncio
    async def test_returns_up_with_latency(self):
        from airweave.adapters.health.postgres import PostgresHealthProbe

        engine = MagicMock()
        engine.connect.return_value = AsyncMock()
        probe = PostgresHealthProbe(engine)

        assert probe.name == "postgres"
        result = await probe.check()

        assert result.status == CheckStatus.up
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_propagates_connection_error(self):
        from airweave.adapters.health.postgres import PostgresHealthProbe

        engine = MagicMock()
        cm = AsyncMock()
        cm.__aenter__.side_effect = ConnectionRefusedError()
        engine.connect.return_value = cm
        probe = PostgresHealthProbe(engine)

        with pytest.raises(ConnectionRefusedError):
            await probe.check()


# ---------------------------------------------------------------------------
# RedisHealthProbe
# ---------------------------------------------------------------------------


class TestRedisHealthProbe:
    """Tests for the Redis adapter."""

    @pytest.mark.asyncio
    async def test_returns_up_with_latency(self):
        from airweave.adapters.health.redis import RedisHealthProbe

        client = AsyncMock()
        client.ping = AsyncMock(return_value=True)
        probe = RedisHealthProbe(client)

        assert probe.name == "redis"
        result = await probe.check()

        assert result.status == CheckStatus.up
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_propagates_connection_error(self):
        from airweave.adapters.health.redis import RedisHealthProbe

        client = AsyncMock()
        client.ping = AsyncMock(side_effect=ConnectionError("redis gone"))
        probe = RedisHealthProbe(client)

        with pytest.raises(ConnectionError):
            await probe.check()


# ---------------------------------------------------------------------------
# TemporalHealthProbe
# ---------------------------------------------------------------------------


class TestTemporalHealthProbe:
    """Tests for the Temporal adapter (lazy-client variant)."""

    @pytest.mark.asyncio
    async def test_client_none_returns_skipped(self):
        from airweave.adapters.health.temporal import TemporalHealthProbe

        probe = TemporalHealthProbe(lambda: None)

        assert probe.name == "temporal"
        result = await probe.check()

        assert result.status == CheckStatus.skipped
        assert result.latency_ms is None

    @pytest.mark.asyncio
    async def test_client_available_returns_up(self):
        from airweave.adapters.health.temporal import TemporalHealthProbe

        client = MagicMock()
        client.service_client.check_health = AsyncMock()
        probe = TemporalHealthProbe(lambda: client)

        result = await probe.check()

        assert result.status == CheckStatus.up
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        client.service_client.check_health.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_client_available_but_unhealthy(self):
        from airweave.adapters.health.temporal import TemporalHealthProbe

        client = MagicMock()
        client.service_client.check_health = AsyncMock(
            side_effect=RuntimeError("gRPC unavailable"),
        )
        probe = TemporalHealthProbe(lambda: client)

        with pytest.raises(RuntimeError, match="gRPC unavailable"):
            await probe.check()

    @pytest.mark.asyncio
    async def test_callable_invoked_each_check(self):
        """The get_client callable is called every time, not cached."""
        from airweave.adapters.health.temporal import TemporalHealthProbe

        calls = []
        client = MagicMock()
        client.service_client.check_health = AsyncMock()

        def get_client():
            calls.append(1)
            return client

        probe = TemporalHealthProbe(get_client)
        await probe.check()
        await probe.check()

        assert len(calls) == 2
