"""HERB People entity schemas."""

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class HerbEmployeeEntity(BaseEntity):
    """Employee record from the HERB benchmark dataset."""

    employee_id: str = AirweaveField(
        ...,
        description="Employee ID (e.g. 'eid_9b023657')",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Employee full name",
        is_name=True,
        embeddable=True,
    )
    role: str = AirweaveField(
        ...,
        description="Job role/title",
        embeddable=True,
    )
    location: str = AirweaveField(
        ...,
        description="Office location",
        embeddable=True,
    )
    org: str = AirweaveField(
        ...,
        description="Organization unit",
        embeddable=True,
    )


class HerbCustomerEntity(BaseEntity):
    """Customer profile from the HERB benchmark dataset."""

    customer_id: str = AirweaveField(
        ...,
        description="Customer ID (e.g. 'CUST-0001')",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Customer full name",
        is_name=True,
        embeddable=True,
    )
    role: str = AirweaveField(
        ...,
        description="Customer role/title",
        embeddable=True,
    )
    company: str = AirweaveField(
        ...,
        description="Customer company name",
        embeddable=True,
    )
