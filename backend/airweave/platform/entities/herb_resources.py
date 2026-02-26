"""HERB Resources entity schemas."""

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class HerbResourceEntity(BaseEntity):
    """Shared URL/bookmark from the HERB benchmark dataset."""

    resource_id: str = AirweaveField(
        ...,
        description="HERB resource ID",
        is_entity_id=True,
    )
    description: str = AirweaveField(
        ...,
        description="URL description",
        is_name=True,
        embeddable=True,
    )
    link: str = AirweaveField(
        ...,
        description="URL (ground truth for URL-type questions)",
        embeddable=True,
    )
    product_name: str = AirweaveField(
        ...,
        description="HERB product name this resource belongs to",
        embeddable=True,
    )
