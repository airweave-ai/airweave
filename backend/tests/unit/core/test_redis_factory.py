"""Tests for ``airweave.core.redis_factory``."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from airweave.core import redis_factory


class TestIsSentinelMode:
    def test_returns_false_when_neither_is_set(self):
        with patch.object(redis_factory.settings, "REDIS_NODES", None), \
             patch.object(redis_factory.settings, "REDIS_SERVICE_NAME", None):
            assert redis_factory.is_sentinel_mode() is False

    def test_returns_false_when_only_nodes_set(self):
        with patch.object(redis_factory.settings, "REDIS_NODES", '[["h", 26379]]'), \
             patch.object(redis_factory.settings, "REDIS_SERVICE_NAME", None):
            assert redis_factory.is_sentinel_mode() is False

    def test_returns_false_when_only_service_name_set(self):
        with patch.object(redis_factory.settings, "REDIS_NODES", None), \
             patch.object(redis_factory.settings, "REDIS_SERVICE_NAME", "mymaster"):
            assert redis_factory.is_sentinel_mode() is False

    def test_returns_true_when_both_set(self):
        with patch.object(redis_factory.settings, "REDIS_NODES", '[["h", 26379]]'), \
             patch.object(redis_factory.settings, "REDIS_SERVICE_NAME", "mymaster"):
            assert redis_factory.is_sentinel_mode() is True


class TestParseSentinelNodes:
    def test_parses_valid_list(self):
        raw = '[["host-0", 26379], ["host-1", 26379]]'
        assert redis_factory._parse_sentinel_nodes(raw) == [
            ("host-0", 26379),
            ("host-1", 26379),
        ]

    def test_coerces_string_port_to_int(self):
        raw = '[["host-0", "26379"]]'
        assert redis_factory._parse_sentinel_nodes(raw) == [("host-0", 26379)]

    @pytest.mark.parametrize(
        "raw",
        [
            "not json",
            "[]",
            '[["host-0"]]',
            '[["host-0", 26379, "extra"]]',
            "[[123, 26379]]",
            '"a string"',
        ],
    )
    def test_rejects_invalid_payloads(self, raw):
        with pytest.raises(ValueError):
            redis_factory._parse_sentinel_nodes(raw)


class TestMakeRedisClient:
    def test_single_host_mode_builds_connection_pool(self):
        fake_pool = MagicMock(name="ConnectionPool")
        fake_redis_cls = MagicMock(name="Redis")
        with patch.object(redis_factory.settings, "REDIS_NODES", None), \
             patch.object(redis_factory.settings, "REDIS_SERVICE_NAME", None), \
             patch.object(redis_factory.settings, "REDIS_HOST", "localhost"), \
             patch.object(redis_factory.settings, "REDIS_PORT", 6379), \
             patch.object(redis_factory.settings, "REDIS_PASSWORD", "secret"), \
             patch.object(redis_factory.settings, "REDIS_DB", 3), \
             patch.object(redis_factory.redis, "ConnectionPool", return_value=fake_pool), \
             patch.object(redis_factory.redis, "Redis", fake_redis_cls), \
             patch.object(redis_factory, "Sentinel") as fake_sentinel_cls:
            redis_factory.make_redis_client(max_connections=42)

            fake_sentinel_cls.assert_not_called()
            redis_factory.redis.ConnectionPool.assert_called_once_with(
                host="localhost",
                port=6379,
                db=3,
                password="secret",
                decode_responses=True,
                max_connections=42,
            )
            fake_redis_cls.assert_called_once_with(connection_pool=fake_pool)

    def test_single_host_mode_forwards_extra_kwargs(self):
        with patch.object(redis_factory.settings, "REDIS_NODES", None), \
             patch.object(redis_factory.settings, "REDIS_SERVICE_NAME", None), \
             patch.object(redis_factory.settings, "REDIS_HOST", "localhost"), \
             patch.object(redis_factory.settings, "REDIS_PORT", 6379), \
             patch.object(redis_factory.settings, "REDIS_PASSWORD", None), \
             patch.object(redis_factory.settings, "REDIS_DB", 0), \
             patch.object(redis_factory.redis, "ConnectionPool") as pool_cls, \
             patch.object(redis_factory.redis, "Redis"):
            redis_factory.make_redis_client(
                socket_timeout=7,
                retry_on_timeout=True,
            )
            kwargs = pool_cls.call_args.kwargs
            assert kwargs["socket_timeout"] == 7
            assert kwargs["retry_on_timeout"] is True
            assert kwargs["password"] is None

    def test_sentinel_mode_uses_sentinel_master_for(self):
        fake_master = MagicMock(name="MasterClient")
        sentinel_instance = MagicMock(name="SentinelInstance")
        sentinel_instance.master_for.return_value = fake_master
        with patch.object(
            redis_factory.settings, "REDIS_NODES",
            '[["sentinel-0", 26379], ["sentinel-1", 26379]]',
        ), patch.object(redis_factory.settings, "REDIS_SERVICE_NAME", "mymaster"), \
             patch.object(redis_factory.settings, "REDIS_PASSWORD", "secret"), \
             patch.object(redis_factory.settings, "REDIS_DB", 5), \
             patch.object(redis_factory, "Sentinel", return_value=sentinel_instance) as sentinel_cls, \
             patch.object(redis_factory.redis, "ConnectionPool") as pool_cls:
            result = redis_factory.make_redis_client(
                max_connections=10, socket_timeout=8
            )

            pool_cls.assert_not_called()
            sentinel_cls.assert_called_once_with(
                [("sentinel-0", 26379), ("sentinel-1", 26379)],
                password="secret",
                socket_connect_timeout=5,
                socket_timeout=8,
            )
            sentinel_instance.master_for.assert_called_once_with(
                "mymaster",
                db=5,
                password="secret",
                decode_responses=True,
                max_connections=10,
                socket_timeout=8,
            )
            assert result is fake_master

    def test_db_override_takes_precedence_over_settings(self):
        with patch.object(redis_factory.settings, "REDIS_NODES", None), \
             patch.object(redis_factory.settings, "REDIS_SERVICE_NAME", None), \
             patch.object(redis_factory.settings, "REDIS_HOST", "localhost"), \
             patch.object(redis_factory.settings, "REDIS_PORT", 6379), \
             patch.object(redis_factory.settings, "REDIS_PASSWORD", None), \
             patch.object(redis_factory.settings, "REDIS_DB", 0), \
             patch.object(redis_factory.redis, "ConnectionPool") as pool_cls, \
             patch.object(redis_factory.redis, "Redis"):
            redis_factory.make_redis_client(db=11)
            assert pool_cls.call_args.kwargs["db"] == 11
