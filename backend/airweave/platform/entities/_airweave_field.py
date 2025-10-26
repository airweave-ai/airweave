"""AirweaveField - Extended Pydantic Field with metadata for entity processing."""

from typing import Any, Optional

from pydantic import Field as PydanticField
from pydantic.fields import FieldInfo


def AirweaveField(  # noqa: D417
    default: Any = ...,
    *,
    # Standard Pydantic Field parameters
    default_factory: Any = None,
    alias: Optional[str] = None,
    alias_priority: Optional[int] = None,
    validation_alias: Optional[str] = None,
    serialization_alias: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    gt: Optional[float] = None,
    ge: Optional[float] = None,
    lt: Optional[float] = None,
    le: Optional[float] = None,
    multiple_of: Optional[float] = None,
    allow_inf_nan: Optional[bool] = None,
    max_length: Optional[int] = None,
    min_length: Optional[int] = None,
    pattern: Optional[str] = None,
    discriminator: Optional[str] = None,
    strict: Optional[bool] = None,
    json_schema_extra: Optional[dict] = None,
    frozen: Optional[bool] = None,
    validate_default: Optional[bool] = None,
    repr: Optional[bool] = None,
    init: Optional[bool] = None,
    init_var: Optional[bool] = None,
    kw_only: Optional[bool] = None,
    # Airweave-specific metadata
    embeddable: bool = False,
    **extra: Any,
) -> FieldInfo:
    """Create a Pydantic Field with Airweave-specific metadata.

    This extends the standard Pydantic Field to include metadata for:
    - embeddable: Whether this field should be included in embeddable text generation

    Args:
        default: Default value for the field
        embeddable: Whether this field should be included in neural embedding
        **extra: Any additional metadata to be added to the field

    Returns:
        FieldInfo object with Airweave metadata in json_schema_extra

    Example:
        >>> class MyEntity(BaseEntity):
        ...     name: str = AirweaveField(..., description="Name", embeddable=True)
        ...     description: str = AirweaveField(..., description="Description", embeddable=True)
    """
    # Build json_schema_extra with Airweave metadata
    airweave_metadata = {}
    if embeddable:
        airweave_metadata["embeddable"] = True

    # Merge with existing json_schema_extra if provided
    if json_schema_extra:
        if isinstance(json_schema_extra, dict):
            json_schema_extra = {**json_schema_extra, **airweave_metadata}
        else:
            # If it's a callable, wrap it
            original_extra = json_schema_extra

            def combined_extra(schema, model_type):
                original_extra(schema, model_type)
                schema.update(airweave_metadata)

            json_schema_extra = combined_extra
    else:
        json_schema_extra = airweave_metadata if airweave_metadata else None

    # Create the standard Pydantic Field with our enhanced metadata
    return PydanticField(
        default=default,
        default_factory=default_factory,
        alias=alias,
        alias_priority=alias_priority,
        validation_alias=validation_alias,
        serialization_alias=serialization_alias,
        title=title,
        description=description,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        multiple_of=multiple_of,
        allow_inf_nan=allow_inf_nan,
        max_length=max_length,
        min_length=min_length,
        pattern=pattern,
        discriminator=discriminator,
        strict=strict,
        json_schema_extra=json_schema_extra,
        frozen=frozen,
        validate_default=validate_default,
        repr=repr,
        init=init,
        init_var=init_var,
        kw_only=kw_only,
        **extra,
    )
