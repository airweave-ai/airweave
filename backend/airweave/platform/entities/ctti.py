"""CTTI entity definitions."""

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import WebEntity


class CTTIWebEntity(WebEntity):
    """Web entity for CTTI clinical trials from ClinicalTrials.gov.

    This entity will be processed by the web_fetcher transformer to download
    the actual clinical trial content from ClinicalTrials.gov.
    """

    nct_id: str = AirweaveField(
        ...,
        description="The NCT ID of the clinical trial study",
        is_entity_id=True,
        is_name=True,
    )
