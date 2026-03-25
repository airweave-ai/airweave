"""Tests for the _require_env helper in manual_stripe_pro_flow.py.

Verifies the CWE-200 fix: hardcoded credentials replaced with
mandatory environment variable checks.
"""
import ast
import os
import types
from pathlib import Path
from unittest.mock import patch

import pytest


def _load_require_env():
    """Load just _require_env from the script without importing stripe/requests."""
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "manual_stripe_pro_flow.py"
    source = script_path.read_text()

    tree = ast.parse(source)
    func_source = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_require_env":
            func_source = ast.get_source_segment(source, node)
            break

    assert func_source is not None, "_require_env not found in script"

    code = f"import os\n\n{func_source}"
    mod = types.ModuleType("_test_mod")
    exec(compile(code, "<test>", "exec"), mod.__dict__)
    return mod._require_env


_require_env = _load_require_env()


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "manual_stripe_pro_flow.py"


class TestRequireEnv:
    """Tests for _require_env helper function."""

    def test_returns_value_when_set(self):
        """_require_env returns the value when the env var exists and is non-empty."""
        with patch.dict(os.environ, {"TEST_SECRET_VAR": "my-secret-value"}):
            result = _require_env("TEST_SECRET_VAR")
            assert result == "my-secret-value"

    def test_raises_when_not_set(self):
        """_require_env raises RuntimeError when the env var is missing."""
        env = os.environ.copy()
        env.pop("TOTALLY_MISSING_VAR_12345", None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="TOTALLY_MISSING_VAR_12345"):
                _require_env("TOTALLY_MISSING_VAR_12345")

    def test_raises_when_empty_string(self):
        """_require_env raises RuntimeError when the env var is set to empty string."""
        with patch.dict(os.environ, {"TEST_EMPTY_VAR": ""}):
            with pytest.raises(RuntimeError, match="TEST_EMPTY_VAR"):
                _require_env("TEST_EMPTY_VAR")

    def test_error_message_includes_var_name(self):
        """The error message should include the variable name for clarity."""
        env = os.environ.copy()
        env.pop("POSTGRES_PASSWORD", None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                _require_env("POSTGRES_PASSWORD")
            assert "POSTGRES_PASSWORD" in str(exc_info.value)

    def test_hardcoded_postgres_password_removed(self):
        """Verify the script no longer contains hardcoded POSTGRES_PASSWORD default."""
        content = SCRIPT_PATH.read_text()
        assert "airweave1234!" not in content, "Hardcoded POSTGRES_PASSWORD still present"

    def test_hardcoded_superuser_password_removed(self):
        """Verify the script no longer contains hardcoded FIRST_SUPERUSER_PASSWORD default."""
        content = SCRIPT_PATH.read_text()
        assert 'setdefault("FIRST_SUPERUSER_PASSWORD"' not in content, (
            "Hardcoded FIRST_SUPERUSER_PASSWORD still present"
        )

    def test_hardcoded_encryption_key_removed(self):
        """Verify the script no longer contains hardcoded ENCRYPTION_KEY default."""
        content = SCRIPT_PATH.read_text()
        assert "44OLJ/" not in content, "Hardcoded ENCRYPTION_KEY still present"
        assert 'setdefault("ENCRYPTION_KEY"' not in content, (
            "Hardcoded ENCRYPTION_KEY via setdefault still present"
        )

    def test_require_env_called_for_secrets(self):
        """Verify _require_env is used for all three secret variables."""
        content = SCRIPT_PATH.read_text()
        assert '_require_env("POSTGRES_PASSWORD")' in content
        assert '_require_env("FIRST_SUPERUSER_PASSWORD")' in content
        assert '_require_env("ENCRYPTION_KEY")' in content

    def test_non_secret_defaults_preserved(self):
        """Verify non-secret setdefault calls are still present (not over-removed)."""
        content = SCRIPT_PATH.read_text()
        assert 'setdefault("POSTGRES_HOST"' in content
        assert 'setdefault("POSTGRES_PORT"' in content
        assert 'setdefault("POSTGRES_USER"' in content
        assert 'setdefault("POSTGRES_DB"' in content
        assert 'setdefault("FIRST_SUPERUSER"' in content
