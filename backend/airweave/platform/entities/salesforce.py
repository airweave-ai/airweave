"""Salesforce entity schemas.

Based on the Salesforce REST API, we define entity schemas for
the core Salesforce objects: Accounts, Contacts, and Opportunities.

These schemas follow the same style as other connectors (e.g., Stripe, HubSpot),
where each entity class inherits from BaseEntity and adds relevant fields with
shared or per-resource metadata as needed.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class SalesforceAccountEntity(BaseEntity):
    """Schema for Salesforce Account entities.

    Reference:
        https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_account.htm
    """

    account_id: str = AirweaveField(
        ..., description="Unique Salesforce ID for the account.", is_entity_id=True
    )
    account_name: str = AirweaveField(
        ..., description="Display name of the account.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the account was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the account was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to open the account in Salesforce.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    account_number: Optional[str] = AirweaveField(
        None, description="Account number", embeddable=True
    )
    website: Optional[str] = AirweaveField(
        None, description="Account website URL", embeddable=False
    )
    phone: Optional[str] = AirweaveField(None, description="Account phone number", embeddable=True)
    fax: Optional[str] = AirweaveField(None, description="Account fax number", embeddable=False)
    industry: Optional[str] = AirweaveField(None, description="Account industry", embeddable=True)
    annual_revenue: Optional[float] = AirweaveField(
        None, description="Annual revenue", embeddable=False
    )
    number_of_employees: Optional[int] = AirweaveField(
        None, description="Number of employees", embeddable=False
    )
    ownership: Optional[str] = AirweaveField(
        None, description="Account ownership type", embeddable=True
    )
    ticker_symbol: Optional[str] = AirweaveField(
        None, description="Stock ticker symbol", embeddable=False
    )
    description: Optional[str] = AirweaveField(
        None, description="Account description", embeddable=True
    )
    rating: Optional[str] = AirweaveField(None, description="Account rating", embeddable=True)
    parent_id: Optional[str] = AirweaveField(
        None, description="ID of parent account", embeddable=False
    )
    type: Optional[str] = AirweaveField(None, description="Account type", embeddable=True)
    billing_street: Optional[str] = AirweaveField(
        None, description="Billing street address", embeddable=True
    )
    billing_city: Optional[str] = AirweaveField(None, description="Billing city", embeddable=True)
    billing_state: Optional[str] = AirweaveField(
        None, description="Billing state/province", embeddable=True
    )
    billing_postal_code: Optional[str] = AirweaveField(
        None, description="Billing postal code", embeddable=False
    )
    billing_country: Optional[str] = AirweaveField(
        None, description="Billing country", embeddable=True
    )
    shipping_street: Optional[str] = AirweaveField(
        None, description="Shipping street address", embeddable=True
    )
    shipping_city: Optional[str] = AirweaveField(None, description="Shipping city", embeddable=True)
    shipping_state: Optional[str] = AirweaveField(
        None, description="Shipping state/province", embeddable=True
    )
    shipping_postal_code: Optional[str] = AirweaveField(
        None, description="Shipping postal code", embeddable=False
    )
    shipping_country: Optional[str] = AirweaveField(
        None, description="Shipping country", embeddable=True
    )
    last_activity_date: Optional[Any] = AirweaveField(
        None, description="Date of the last activity on the account", embeddable=False
    )
    last_viewed_date: Optional[Any] = AirweaveField(
        None, description="Date when the account was last viewed", embeddable=False
    )
    last_referenced_date: Optional[Any] = AirweaveField(
        None, description="Date when the account was last referenced", embeddable=False
    )
    is_deleted: bool = AirweaveField(
        False, description="Indicates whether the account has been deleted", embeddable=False
    )
    is_customer_portal: bool = AirweaveField(
        False,
        description="Indicates whether this account has customer portal access",
        embeddable=False,
    )
    is_person_account: bool = AirweaveField(
        False, description="Indicates whether this is a person account", embeddable=False
    )
    jigsaw: Optional[str] = AirweaveField(None, description="Data.com ID", embeddable=False)
    clean_status: Optional[str] = AirweaveField(
        None, description="Clean status from Data.com", embeddable=False
    )
    account_source: Optional[str] = AirweaveField(
        None, description="Source of the account", embeddable=True
    )
    sic_desc: Optional[str] = AirweaveField(None, description="SIC description", embeddable=True)
    duns_number: Optional[str] = AirweaveField(None, description="D-U-N-S number", embeddable=False)
    tradestyle: Optional[str] = AirweaveField(None, description="Tradestyle", embeddable=True)
    naics_code: Optional[str] = AirweaveField(None, description="NAICS code", embeddable=False)
    naics_desc: Optional[str] = AirweaveField(
        None, description="NAICS description", embeddable=True
    )
    year_started: Optional[str] = AirweaveField(
        None, description="Year the account was started", embeddable=False
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the account",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the account."""
        return self.web_url_value or ""


class SalesforceContactEntity(BaseEntity):
    """Schema for Salesforce Contact entities.

    Reference:
        https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_contact.htm
    """

    contact_id: str = AirweaveField(
        ..., description="Unique Salesforce ID for the contact.", is_entity_id=True
    )
    contact_name: str = AirweaveField(
        ..., description="Display name of the contact.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the contact was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the contact was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the contact in Salesforce.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    first_name: Optional[str] = AirweaveField(
        None, description="Contact's first name", embeddable=True
    )
    last_name: Optional[str] = AirweaveField(
        None, description="Contact's last name", embeddable=True
    )
    email: Optional[str] = AirweaveField(
        None, description="Contact's email address", embeddable=True
    )
    phone: Optional[str] = AirweaveField(
        None, description="Contact's phone number", embeddable=True
    )
    mobile_phone: Optional[str] = AirweaveField(
        None, description="Contact's mobile phone number", embeddable=True
    )
    fax: Optional[str] = AirweaveField(None, description="Contact's fax number", embeddable=False)
    title: Optional[str] = AirweaveField(None, description="Contact's job title", embeddable=True)
    department: Optional[str] = AirweaveField(
        None, description="Contact's department", embeddable=True
    )
    account_id: Optional[str] = AirweaveField(
        None, description="ID of the associated account", embeddable=False
    )
    lead_source: Optional[str] = AirweaveField(
        None, description="Source of the lead", embeddable=True
    )
    birthdate: Optional[Any] = AirweaveField(
        None, description="Contact's birthdate", embeddable=False
    )
    description: Optional[str] = AirweaveField(
        None, description="Contact description", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the contact", embeddable=False
    )
    last_activity_date: Optional[Any] = AirweaveField(
        None, description="Date of the last activity on the contact", embeddable=False
    )
    last_viewed_date: Optional[Any] = AirweaveField(
        None, description="Date when the contact was last viewed", embeddable=False
    )
    last_referenced_date: Optional[Any] = AirweaveField(
        None, description="Date when the contact was last referenced", embeddable=False
    )
    is_deleted: bool = AirweaveField(
        False, description="Indicates whether the contact has been deleted", embeddable=False
    )
    is_email_bounced: bool = AirweaveField(
        False,
        description="Indicates whether emails to this contact bounce",
        embeddable=False,
    )
    is_unread_by_owner: bool = AirweaveField(
        False,
        description="Indicates whether the contact is unread by the owner",
        embeddable=False,
    )
    jigsaw: Optional[str] = AirweaveField(None, description="Data.com ID", embeddable=False)
    jigsaw_contact_id: Optional[str] = AirweaveField(
        None, description="Data.com contact ID", embeddable=False
    )
    clean_status: Optional[str] = AirweaveField(
        None, description="Clean status from Data.com", embeddable=False
    )
    level: Optional[str] = AirweaveField(None, description="Contact level", embeddable=True)
    languages: Optional[str] = AirweaveField(None, description="Languages spoken", embeddable=True)
    has_opted_out_of_email: bool = AirweaveField(
        False,
        description="Indicates whether the contact has opted out of email",
        embeddable=False,
    )
    has_opted_out_of_fax: bool = AirweaveField(
        False,
        description="Indicates whether the contact has opted out of fax",
        embeddable=False,
    )
    do_not_call: bool = AirweaveField(
        False,
        description="Indicates whether the contact should not be called",
        embeddable=False,
    )
    mailing_street: Optional[str] = AirweaveField(
        None, description="Mailing street address", embeddable=True
    )
    mailing_city: Optional[str] = AirweaveField(None, description="Mailing city", embeddable=True)
    mailing_state: Optional[str] = AirweaveField(
        None, description="Mailing state/province", embeddable=True
    )
    mailing_postal_code: Optional[str] = AirweaveField(
        None, description="Mailing postal code", embeddable=False
    )
    mailing_country: Optional[str] = AirweaveField(
        None, description="Mailing country", embeddable=True
    )
    other_street: Optional[str] = AirweaveField(
        None, description="Other street address", embeddable=True
    )
    other_city: Optional[str] = AirweaveField(None, description="Other city", embeddable=True)
    other_state: Optional[str] = AirweaveField(
        None, description="Other state/province", embeddable=True
    )
    other_postal_code: Optional[str] = AirweaveField(
        None, description="Other postal code", embeddable=False
    )
    other_country: Optional[str] = AirweaveField(None, description="Other country", embeddable=True)
    assistant_name: Optional[str] = AirweaveField(
        None, description="Assistant's name", embeddable=True
    )
    assistant_phone: Optional[str] = AirweaveField(
        None, description="Assistant's phone number", embeddable=False
    )
    reports_to_id: Optional[str] = AirweaveField(
        None, description="ID of the contact this contact reports to", embeddable=False
    )
    email_bounced_date: Optional[Any] = AirweaveField(
        None, description="Date when email bounced", embeddable=False
    )
    email_bounced_reason: Optional[str] = AirweaveField(
        None, description="Reason why email bounced", embeddable=True
    )
    individual_id: Optional[str] = AirweaveField(
        None, description="ID of the associated individual", embeddable=False
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Additional metadata about the contact", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the contact."""
        return self.web_url_value or ""


class SalesforceOpportunityEntity(BaseEntity):
    """Schema for Salesforce Opportunity entities.

    Reference:
        https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_opportunity.htm
    """

    opportunity_id: str = AirweaveField(
        ..., description="Unique Salesforce ID for the opportunity.", is_entity_id=True
    )
    opportunity_name: str = AirweaveField(
        ..., description="Display name of the opportunity.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the opportunity was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the opportunity was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the opportunity in Salesforce.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    account_id: Optional[str] = AirweaveField(
        None, description="ID of the associated account", embeddable=False
    )
    amount: Optional[float] = AirweaveField(None, description="Opportunity amount", embeddable=True)
    close_date: Optional[Any] = AirweaveField(
        None, description="Expected close date", embeddable=True
    )
    stage_name: Optional[str] = AirweaveField(None, description="Sales stage", embeddable=True)
    probability: Optional[float] = AirweaveField(
        None, description="Probability percentage", embeddable=True
    )
    forecast_category: Optional[str] = AirweaveField(
        None, description="Forecast category", embeddable=True
    )
    forecast_category_name: Optional[str] = AirweaveField(
        None, description="Forecast category name", embeddable=True
    )
    campaign_id: Optional[str] = AirweaveField(
        None, description="ID of the associated campaign", embeddable=False
    )
    has_opportunity_line_item: bool = AirweaveField(
        False,
        description="Indicates whether the opportunity has line items",
        embeddable=False,
    )
    pricebook2_id: Optional[str] = AirweaveField(
        None, description="ID of the associated pricebook", embeddable=False
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the opportunity", embeddable=False
    )
    last_activity_date: Optional[Any] = AirweaveField(
        None, description="Date of the last activity on the opportunity", embeddable=False
    )
    last_viewed_date: Optional[Any] = AirweaveField(
        None, description="Date when the opportunity was last viewed", embeddable=False
    )
    last_referenced_date: Optional[Any] = AirweaveField(
        None,
        description="Date when the opportunity was last referenced",
        embeddable=False,
    )
    is_deleted: bool = AirweaveField(
        False,
        description="Indicates whether the opportunity has been deleted",
        embeddable=False,
    )
    is_won: bool = AirweaveField(
        False, description="Indicates whether the opportunity is won", embeddable=True
    )
    is_closed: bool = AirweaveField(
        False, description="Indicates whether the opportunity is closed", embeddable=True
    )
    has_open_activity: bool = AirweaveField(
        False,
        description="Indicates whether the opportunity has open activities",
        embeddable=False,
    )
    has_overdue_task: bool = AirweaveField(
        False,
        description="Indicates whether the opportunity has overdue tasks",
        embeddable=False,
    )
    description: Optional[str] = AirweaveField(
        None, description="Opportunity description", embeddable=True
    )
    type: Optional[str] = AirweaveField(None, description="Opportunity type", embeddable=True)
    lead_source: Optional[str] = AirweaveField(
        None, description="Source of the lead", embeddable=True
    )
    next_step: Optional[str] = AirweaveField(
        None, description="Next step in the sales process", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the opportunity",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the opportunity."""
        return self.web_url_value or ""
