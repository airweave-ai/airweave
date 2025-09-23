"""
Test module for environment validation.

This module validates that all required environment variables are set
and have valid values before running the test suite.
"""

import os
import sys
from typing import Dict, List, Tuple, Optional


def validate_required_env_vars() -> Tuple[bool, List[str]]:
    """
    Validate that all required environment variables are set.

    Returns:
        Tuple[bool, List[str]]: (success, list of missing variables)
    """
    required_vars = {
        "STRIPE_API_KEY": "Stripe API key for testing source connections",
    }

    missing_vars = []
    for var_name, description in required_vars.items():
        if not os.environ.get(var_name):
            missing_vars.append(f"{var_name}: {description}")

    return len(missing_vars) == 0, missing_vars


def validate_optional_env_vars() -> Dict[str, bool]:
    """
    Check which optional environment variables are set.

    Returns:
        Dict[str, bool]: Map of variable name to whether it's set
    """
    optional_vars = [
        "OPENAI_API_KEY",
        "TEST_GITHUB_TOKEN",
        "TEST_GOOGLE_ACCESS_TOKEN",
        "TEST_GOOGLE_REFRESH_TOKEN",
        "TEST_AUTH_PROVIDER_NAME",
        "TEST_AUTH_PROVIDER_CONFIG",
    ]

    return {var: bool(os.environ.get(var)) for var in optional_vars}


def validate_env_var_formats() -> Tuple[bool, List[str]]:
    """
    Validate that environment variables have the correct format.

    Returns:
        Tuple[bool, List[str]]: (success, list of validation errors)
    """
    errors = []

    # Validate Stripe API key format
    stripe_key = os.environ.get("STRIPE_API_KEY", "")
    if stripe_key and not stripe_key.startswith("sk_"):
        errors.append("STRIPE_API_KEY must start with 'sk_' (e.g., sk_test_... or sk_live_...)")

    # Validate OpenAI API key format if provided
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key and not openai_key.startswith("sk-"):
        errors.append("OPENAI_API_KEY must start with 'sk-' (e.g., sk-...)")

    # Validate TEST_AUTH_PROVIDER_CONFIG is valid JSON if provided
    auth_config = os.environ.get("TEST_AUTH_PROVIDER_CONFIG", "")
    if auth_config:
        try:
            import json

            json.loads(auth_config)
        except json.JSONDecodeError as e:
            errors.append(f"TEST_AUTH_PROVIDER_CONFIG must be valid JSON: {e}")

    return len(errors) == 0, errors


def validate_environment(env: str, require_all_optional: bool = False) -> bool:
    """
    Validate the test environment.

    Args:
        env: The environment to test against (local, dev, prod)
        require_all_optional: If True, fail if any optional vars are missing

    Returns:
        bool: True if environment is valid, False otherwise
    """
    print("\n🔍 Validating test environment...")

    # Check required variables
    success, missing_required = validate_required_env_vars()
    if not success:
        print("\n❌ Required environment variables missing:")
        for var in missing_required:
            print(f"   - {var}")
        print("\nSet these variables before running tests.")
        return False

    # Check environment-specific requirements
    if env in ["dev", "prod"]:
        if not os.environ.get("AIRWEAVE_API_KEY"):
            print(f"\n❌ AIRWEAVE_API_KEY is required for {env} environment")
            return False

    # Validate formats
    success, format_errors = validate_env_var_formats()
    if not success:
        print("\n❌ Environment variable format errors:")
        for error in format_errors:
            print(f"   - {error}")
        return False

    # Check optional variables
    optional_status = validate_optional_env_vars()
    missing_optional = [var for var, is_set in optional_status.items() if not is_set]

    if missing_optional:
        if require_all_optional:
            print("\n❌ Optional environment variables missing (required for full test coverage):")
            for var in missing_optional:
                print(f"   - {var}")
            return False
        else:
            print("\n⚠️  Optional environment variables not set (some tests will be skipped):")
            for var in missing_optional:
                print(f"   - {var}")

    # Report what's configured
    print("\n✅ Environment validation passed")
    print("\n📋 Test configuration:")
    print(f"   Environment: {env}")
    print(f"   Stripe API Key: {'✓ Set' if os.environ.get('STRIPE_API_KEY') else '✗ Missing'}")
    print(
        f"   OpenAI API Key: {'✓ Set' if optional_status.get('OPENAI_API_KEY') else '✗ Missing (optional)'}"
    )

    if optional_status.get("TEST_GITHUB_TOKEN"):
        print(f"   GitHub Token: ✓ Set")
    if optional_status.get("TEST_GOOGLE_ACCESS_TOKEN"):
        print(f"   Google OAuth: ✓ Set")
    if optional_status.get("TEST_AUTH_PROVIDER_NAME"):
        print(f"   Auth Provider: ✓ Set ({os.environ.get('TEST_AUTH_PROVIDER_NAME')})")

    return True


def require_env_var(var_name: str, test_name: str) -> str:
    """
    Require an environment variable for a specific test.
    Raises AssertionError if not set.

    Args:
        var_name: Name of the environment variable
        test_name: Name of the test requiring this variable

    Returns:
        str: The value of the environment variable

    Raises:
        AssertionError: If the variable is not set
    """
    value = os.environ.get(var_name)
    if not value:
        raise AssertionError(
            f"{test_name} requires {var_name} to be set. "
            f"Set it with: export {var_name}=your_value"
        )
    return value


def get_optional_env_var(var_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get an optional environment variable with a default value.

    Args:
        var_name: Name of the environment variable
        default: Default value if not set

    Returns:
        Optional[str]: The value or default
    """
    return os.environ.get(var_name, default)
