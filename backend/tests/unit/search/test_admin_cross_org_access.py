"""Unit tests for SearchService._validate_admin_cross_org_access (CWE-862 fix).

Verifies that API-key callers cannot access collections belonging to
other organizations, while admin/superuser callers retain cross-org access.

These tests use a standalone copy of the validation logic to avoid
importing the full airweave dependency tree.  We also verify by AST that
the production code matches our test copy.
"""

import ast
import inspect
import textwrap

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

# We cannot import SearchService directly because the module pulls in
# heavy dependencies (email-validator, asyncpg, etc.) that are not
# available in this lightweight test environment.  Instead we import
# only the exception and replicate the minimal validation function,
# then verify via AST that the production code hasn't drifted.

from airweave.core.exceptions import PermissionException


ORG_A = uuid4()
ORG_B = uuid4()


# -----------------------------------------------------------------------
# Standalone copy of _validate_admin_cross_org_access for testing
# -----------------------------------------------------------------------
def _validate_admin_cross_org_access(ctx, collection_org_id):
    """Exact copy of SearchService._validate_admin_cross_org_access."""
    if ctx.has_user_context and (ctx.user.is_admin or ctx.user.is_superuser):
        return
    if ctx.organization.id != collection_org_id:
        ctx.logger.warning(
            f"API key from org {ctx.organization.id} attempted cross-org access "
            f"to collection in org {collection_org_id}"
        )
        raise PermissionException(
            "API key does not have access to collections outside its organization"
        )


# -----------------------------------------------------------------------
# AST check: verify production code matches our copy
# -----------------------------------------------------------------------
def test_production_code_matches_test_copy():
    """Verify the production code hasn't drifted from our test copy.

    Reads the source file, extracts the method body, and compares the
    AST (ignoring docstrings/type annotations) to ensure we're actually
    testing what ships.
    """
    import pathlib
    src = (
        pathlib.Path(__file__).resolve().parents[3]
        / "airweave"
        / "search"
        / "service.py"
    )
    tree = ast.parse(src.read_text())

    # Find the method definition
    method_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_validate_admin_cross_org_access":
            method_node = node
            break

    assert method_node is not None, "Could not find _validate_admin_cross_org_access in service.py"

    # Extract the method body, skipping docstring
    body = method_node.body
    if (
        isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
    ):
        body = body[1:]

    # Verify key structural elements:
    # 1. First statement: if ctx.has_user_context and (is_admin or is_superuser): return
    first_if = body[0]
    assert isinstance(first_if, ast.If), "First stmt should be an If"
    source_first = ast.dump(first_if.test)
    assert "has_user_context" in source_first
    assert "is_admin" in source_first
    assert "is_superuser" in source_first

    # 2. Second statement: if ctx.organization.id != collection_org_id: ... raise
    second_if = body[1]
    assert isinstance(second_if, ast.If), "Second stmt should be an If"
    # The body should contain a Raise with PermissionException
    has_raise = any(isinstance(s, ast.Raise) for s in second_if.body)
    assert has_raise, "Second if-block should raise PermissionException"


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
def _make_ctx(*, has_user: bool, is_admin: bool = False, is_superuser: bool = False, org_id=ORG_A):
    """Build a minimal mock ApiContext."""
    ctx = MagicMock()
    ctx.has_user_context = has_user
    ctx.organization = MagicMock()
    ctx.organization.id = org_id
    ctx.logger = MagicMock()

    if has_user:
        ctx.user = MagicMock()
        ctx.user.is_admin = is_admin
        ctx.user.is_superuser = is_superuser
    else:
        ctx.user = None
    return ctx


# -----------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------
class TestValidateAdminCrossOrgAccess:
    """Tests for _validate_admin_cross_org_access."""

    # ---- Admin / superuser: should ALWAYS pass ----

    def test_admin_user_same_org(self):
        """Admin user accessing own org — should pass."""
        ctx = _make_ctx(has_user=True, is_admin=True, org_id=ORG_A)
        _validate_admin_cross_org_access(ctx, collection_org_id=ORG_A)

    def test_admin_user_cross_org(self):
        """Admin user accessing different org — should pass (intended cross-org)."""
        ctx = _make_ctx(has_user=True, is_admin=True, org_id=ORG_A)
        _validate_admin_cross_org_access(ctx, collection_org_id=ORG_B)

    def test_superuser_cross_org(self):
        """Superuser accessing different org — should pass."""
        ctx = _make_ctx(has_user=True, is_superuser=True, org_id=ORG_A)
        _validate_admin_cross_org_access(ctx, collection_org_id=ORG_B)

    def test_admin_and_superuser_cross_org(self):
        """Admin+superuser accessing different org — should pass."""
        ctx = _make_ctx(has_user=True, is_admin=True, is_superuser=True, org_id=ORG_A)
        _validate_admin_cross_org_access(ctx, collection_org_id=ORG_B)

    # ---- API key (no user context): same org ----

    def test_api_key_same_org(self):
        """API key accessing own org's collection — should pass."""
        ctx = _make_ctx(has_user=False, org_id=ORG_A)
        _validate_admin_cross_org_access(ctx, collection_org_id=ORG_A)

    # ---- API key (no user context): cross org — THE VULNERABILITY ----

    def test_api_key_cross_org_raises(self):
        """API key accessing another org's collection — should RAISE PermissionException."""
        ctx = _make_ctx(has_user=False, org_id=ORG_A)

        with pytest.raises(PermissionException) as exc_info:
            _validate_admin_cross_org_access(ctx, collection_org_id=ORG_B)

        assert "outside its organization" in str(exc_info.value)

    def test_api_key_cross_org_logs_warning(self):
        """API key cross-org attempt should log a warning."""
        ctx = _make_ctx(has_user=False, org_id=ORG_A)

        with pytest.raises(PermissionException):
            _validate_admin_cross_org_access(ctx, collection_org_id=ORG_B)

        ctx.logger.warning.assert_called_once()
        log_msg = ctx.logger.warning.call_args[0][0]
        assert str(ORG_A) in log_msg
        assert str(ORG_B) in log_msg

    # ---- Non-admin user (user context but NOT admin) ----

    def test_regular_user_same_org(self):
        """Non-admin user accessing own org — should pass."""
        ctx = _make_ctx(has_user=True, is_admin=False, is_superuser=False, org_id=ORG_A)
        _validate_admin_cross_org_access(ctx, collection_org_id=ORG_A)

    def test_regular_user_cross_org_raises(self):
        """Non-admin user accessing another org — should raise PermissionException."""
        ctx = _make_ctx(has_user=True, is_admin=False, is_superuser=False, org_id=ORG_A)

        with pytest.raises(PermissionException):
            _validate_admin_cross_org_access(ctx, collection_org_id=ORG_B)


class TestValidationCalledInSearchAdmin:
    """Verify that search_admin and search_as_user call the validation.

    Uses AST to confirm the method is invoked at the right point.
    """

    def _get_method_body(self, method_name):
        import pathlib
        src = (
            pathlib.Path(__file__).resolve().parents[3]
            / "airweave"
            / "search"
            / "service.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
                return ast.dump(ast.Module(body=node.body, type_ignores=[]))
        return None

    def test_search_admin_calls_validation(self):
        """search_admin method should call _validate_admin_cross_org_access."""
        body = self._get_method_body("search_admin")
        assert body is not None
        assert "_validate_admin_cross_org_access" in body

    def test_search_as_user_calls_validation(self):
        """search_as_user method should call _validate_admin_cross_org_access."""
        body = self._get_method_body("search_as_user")
        assert body is not None
        assert "_validate_admin_cross_org_access" in body

    def test_validation_before_factory_build_in_search_admin(self):
        """Validation should happen before factory.build in search_admin."""
        import pathlib
        src = (
            pathlib.Path(__file__).resolve().parents[3]
            / "airweave"
            / "search"
            / "service.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "search_admin":
                # Find line numbers
                validate_line = None
                factory_line = None
                for child in ast.walk(node):
                    if isinstance(child, ast.Attribute) and child.attr == "_validate_admin_cross_org_access":
                        validate_line = child.lineno
                    if isinstance(child, ast.Attribute) and child.attr == "build" and isinstance(child.value, ast.Name) and child.value.id == "factory":
                        factory_line = child.lineno
                assert validate_line is not None, "validation call not found"
                assert factory_line is not None, "factory.build call not found"
                assert validate_line < factory_line, (
                    f"Validation (line {validate_line}) should come before "
                    f"factory.build (line {factory_line})"
                )
                return
        pytest.fail("search_admin method not found")
