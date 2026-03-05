"""Base config class."""

from typing import Optional, get_args, get_origin

from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticUndefined


def RequiredTemplateConfig(*args, **kwargs):
    """Create a Field marked as required for OAuth URL templates.

    This helper marks config fields that must be provided BEFORE OAuth flow starts.
    These fields are used for template rendering in OAuth URLs (e.g., {instance_url}).

    Args:
        *args: Positional arguments passed to Field()
        **kwargs: Keyword arguments passed to Field()

    Returns:
        Field with required_for_auth=True in json_schema_extra

    Example:
        ```python
        class SalesforceConfig(BaseConfig):
            instance_url: str = RequiredTemplateConfig(
                title="Instance URL",
                description="Your Salesforce instance (e.g., mycompany.salesforce.com)",
            )
        ```
    """
    if "json_schema_extra" not in kwargs:
        kwargs["json_schema_extra"] = {}
    kwargs["json_schema_extra"]["required_for_auth"] = True
    return Field(*args, **kwargs)


class BaseConfig(BaseModel):
    """Base config class with template config field support."""

    @classmethod
    def get_template_config_fields(cls) -> list[str]:
        """Get list of field names required for OAuth URL templates.

        Returns:
            List of field names marked with required_for_auth=True

        Example:
            ```python
            >>> SalesforceConfig.get_template_config_fields()
            ['instance_url']
            ```
        """
        template_fields = []
        for field_name, field_info in cls.model_fields.items():
            json_schema_extra = field_info.json_schema_extra or {}
            if json_schema_extra.get("required_for_auth"):
                template_fields.append(field_name)
        return template_fields

    @classmethod
    def extract_template_configs(cls, config_dict: dict) -> dict:
        """Extract only template config fields from config dict.

        Useful for OAuth URL template rendering.

        Args:
            config_dict: Full config dictionary

        Returns:
            Dictionary with only template config fields

        Example:
            ```python
            >>> config = {"instance_url": "mycompany.sf.com", "api_version": "v58.0"}
            >>> SalesforceConfig.extract_template_configs(config)
            {'instance_url': 'mycompany.sf.com'}
            ```
        """
        template_fields = cls.get_template_config_fields()
        return {k: v for k, v in config_dict.items() if k in template_fields}

    @classmethod
    def validate_template_configs(cls, config_dict: dict) -> None:
        """Validate that all template config fields are present and not empty.

        Should be called BEFORE starting OAuth flow to fail fast.

        Args:
            config_dict: Config dictionary to validate

        Raises:
            ValueError: If any template config fields are missing, None, or empty strings

        Example:
            ```python
            >>> SalesforceConfig.validate_template_configs({"api_version": "v58.0"})
            ValueError: Template config fields missing: instance_url.
            ```
        """
        template_fields = cls.get_template_config_fields()
        missing = []

        for field in template_fields:
            if field not in config_dict or config_dict[field] is None:
                missing.append(field)
            elif isinstance(config_dict[field], str) and not config_dict[field].strip():
                # Reject empty strings or strings with only whitespace
                missing.append(field)

        if missing:
            raise ValueError(
                f"Template config fields missing or empty: {', '.join(missing)}. "
                f"These must be provided before OAuth authentication."
            )


class ConfigField(BaseModel):
    """Config field model."""

    name: str
    title: str
    description: Optional[str] = None
    type: str
    required: bool = True  # Default to True for backward compatibility
    items_type: Optional[str] = None  # For array types, the type of items
    feature_flag: Optional[str] = None  # Feature flag required to show this field
    is_secret: bool = False  # Whether this field should be treated as a secret


_type_map = {str: "string", int: "number", float: "number", bool: "boolean"}


class Fields(BaseModel):
    """Fields model."""

    fields: list[ConfigField]

    @classmethod
    def from_config_class(cls, config_class: type[BaseConfig]) -> "Fields":
        """Create fields from config class."""
        fields = []
        for field_name, field_info in config_class.model_fields.items():
            # Skip fields marked as excluded from UI
            json_schema_extra = field_info.json_schema_extra or {}
            if json_schema_extra.get("exclude_from_ui"):
                continue

            # Get the actual type, handling Optional types
            annotation = field_info.annotation
            is_optional = False
            if get_origin(annotation) is Optional:
                annotation = get_args(annotation)[0]
                is_optional = True

            # Check if it's a list type
            items_type = None
            origin = get_origin(annotation)
            if origin is list:
                # Get the type of list items
                list_args = get_args(annotation)
                if list_args:
                    items_type = _type_map.get(list_args[0], "string")
                type_str = "array"
            else:
                # Map the type to string representation
                type_str = _type_map.get(
                    annotation, "string"
                )  # Default to string if type not found

            # Determine if field is required
            # A field is required if it has no default and is not Optional
            has_default = field_info.default is not PydanticUndefined
            is_required = not has_default and not is_optional

            # Extract feature_flag and is_secret from json_schema_extra
            json_schema_extra = field_info.json_schema_extra or {}
            feature_flag = json_schema_extra.get("feature_flag")
            is_secret = json_schema_extra.get("is_secret", False)

            fields.append(
                ConfigField(
                    name=field_name,
                    title=field_info.title or field_name,
                    description=field_info.description,
                    type=type_str,
                    required=is_required,
                    items_type=items_type,
                    feature_flag=feature_flag,
                    is_secret=is_secret,
                )
            )
        return Fields(fields=fields)

    def filter_by_features(self, enabled_features: list[str]) -> "Fields":
        """Filter fields to only include those whose feature flags are enabled.

        Fields without a feature_flag are always included.
        Fields with a feature_flag are only included if the flag is in enabled_features.

        Args:
            enabled_features: List of feature flag names that are enabled

        Returns:
            New Fields instance with filtered fields
        """
        filtered = []
        for field in self.fields:
            # Include field if no feature_flag, or if the flag is enabled
            if field.feature_flag is None or field.feature_flag in enabled_features:
                filtered.append(field)
        return Fields(fields=filtered)


class ConfigValues(BaseModel):
    """Config values model.

    Implements "flat dictionary" semantics, where no values are dictionaries.
    """

    # Allow arbitrary fields
    model_config = {
        "extra": "allow",
    }

    @model_validator(mode="after")
    def validate_config_values(self):
        """Validate that no values are dictionaries (depth 0)."""
        for key, value in self.__dict__.items():
            if isinstance(value, dict):
                raise ValueError(f"Value for '{key}' must not be a dictionary (depth 0 only)")
        return self
