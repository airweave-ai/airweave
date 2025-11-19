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
    is_entity_id: bool = False,
    is_name: bool = False,
    is_created_at: bool = False,
    is_updated_at: bool = False,
    unhashable: bool = False,
    **extra: Any,
) -> FieldInfo:
    """Create a Pydantic Field with Airweave-specific metadata.

    This extends the standard Pydantic Field to include metadata for:
    - embeddable: Whether this field should be included in embeddable text generation
    - is_entity_id: Marks this field as the entity's unique identifier
    - is_name: Marks this field as the entity's display name
    - is_created_at: Marks this field as the creation timestamp
    - is_updated_at: Marks this field as the last update timestamp
    - unhashable: Marks this field as volatile (excluded from hash computation)

    Args:
        default: Default value for the field
        embeddable: Whether this field should be included in neural embedding
        is_entity_id: True if this field is the entity's unique identifier
        is_name: True if this field is the entity's display name
        is_created_at: True if this field is the creation timestamp
        is_updated_at: True if this field is the last update timestamp
        unhashable: True if this field should be excluded from hash computation
        **extra: Any additional metadata to be added to the field

    Returns:
        FieldInfo object with Airweave metadata in json_schema_extra

    Example:
        >>> class AsanaTaskEntity(BaseEntity):
        ...     gid: str = AirweaveField(..., description="Asana GID", is_entity_id=True)
        ...     title: str = AirweaveField(
        ...         ..., description="Task name", is_name=True, embeddable=True
        ...     )
        ...     created_at: Optional[datetime] = AirweaveField(None, is_created_at=True)
        ...     modified_at: Optional[datetime] = AirweaveField(None, is_updated_at=True)
        ...     permalink_url: Optional[str] = AirweaveField(None, unhashable=True)
    """
    # Build json_schema_extra with Airweave metadata
    airweave_metadata = {}
    if embeddable:
        airweave_metadata["embeddable"] = True
    if is_entity_id:
        airweave_metadata["is_entity_id"] = True
    if is_name:
        airweave_metadata["is_name"] = True
    if is_created_at:
        airweave_metadata["is_created_at"] = True
    if is_updated_at:
        airweave_metadata["is_updated_at"] = True
    if unhashable:
        airweave_metadata["unhashable"] = True

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
