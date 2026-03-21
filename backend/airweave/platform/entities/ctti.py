"""CTTI entity definitions."""

from __future__ import annotations

from typing import Any

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import Breadcrumb, WebEntity


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

    @classmethod
    def from_api(
        cls,
        data: dict[str, Any],
        *,
        breadcrumbs: list[Breadcrumb] | None = None,
    ) -> CTTIWebEntity | None:
        """Build entity from an AACT row (e.g. ``{"nct_id": "NCT01234567"}``)."""
        nct_id = data.get("nct_id")
        if not nct_id or not str(nct_id).strip():
            return None
        clean = str(nct_id).strip()
        return cls(
            nct_id=clean,
            name=f"Clinical Trial {clean}",
            crawl_url=f"https://clinicaltrials.gov/study/{clean}",
            breadcrumbs=list(breadcrumbs or []),
        )
