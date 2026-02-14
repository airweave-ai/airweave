"""Credential domain exceptions."""

from airweave.core.exceptions import BadRequestError, PermissionException


class InvalidAuthFieldsError(BadRequestError):
    """Raised when auth fields fail schema validation."""

    def __init__(self, detail: str):
        super().__init__(f"Invalid auth fields: {detail}")


class InvalidConfigFieldsError(BadRequestError):
    """Raised when config fields fail schema validation."""

    def __init__(self, detail: str):
        super().__init__(f"Invalid config fields: {detail}")


class InvalidCredentialsError(BadRequestError):
    """Raised when credentials fail live validation against the source."""

    def __init__(self, detail: str = "Authentication credentials are invalid"):
        super().__init__(detail)


class SourceDoesNotSupportDirectAuthError(BadRequestError):
    """Raised when a source has no auth_config_ref (e.g. OAuth-only sources)."""

    def __init__(self, source_name: str):
        super().__init__(f"Source {source_name} does not support direct auth")


class FeatureFlagRequiredError(PermissionException):
    """Raised when a config field requires a feature flag the org doesn't have."""

    def __init__(self, field_title: str, feature_flag: str):
        super().__init__(
            f"The '{field_title}' feature requires the '{feature_flag}' "
            f"feature to be enabled for your organization."
        )
