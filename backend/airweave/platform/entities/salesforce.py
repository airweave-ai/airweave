"""Salesforce entity schemas.

Based on the Salesforce REST API, we define entity schemas for
the core Salesforce objects: Accounts, Contacts, and Opportunities.

These schemas follow the same style as other connectors (e.g., Stripe, HubSpot),
where each entity class inherits from our  and adds relevant fields with
shared or per-resource metadata as needed.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import 


class SalesforceAccountEntity(BaseEntity):
    """Schema for Salesforce Account entities.

    https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_account.htm
    """

    name: Optional[str] = AirweaveField(None, description="Account name", embeddable=True)
    account_number: Optional[str] = AirweaveField(
        None, description="Account number", embeddable=True
    )
    website: Optional[str] = AirweaveField(None, description="Account website URL")
    phone: Optional[str] = AirweaveField(None, description="Account phone number", embeddable=True)
    fax: Optional[str] = AirweaveField(None, description="Account fax number")
    industry: Optional[str] = AirweaveField(None, description="Account industry", embeddable=True)
    annual_revenue: Optional[float] = AirweaveField(None, description="Annual revenue")
    number_of_employees: Optional[int] = AirweaveField(None, description="Number of employees")
    ownership: Optional[str] = AirweaveField(
        None, description="Account ownership type", embeddable=True
    )
    ticker_symbol: Optional[str] = AirweaveField(None, description="Stock ticker symbol")
    description: Optional[str] = AirweaveField(
        None, description="Account description", embeddable=True
    )
    rating: Optional[str] = AirweaveField(None, description="Account rating", embeddable=True)
    parent_id: Optional[str] = AirweaveField(None, description="ID of parent account")
    type: Optional[str] = AirweaveField(None, description="Account type", embeddable=True)
    billing_street: Optional[str] = AirweaveField(
        None, description="Billing street address", embeddable=True
    )
    billing_city: Optional[str] = AirweaveField(None, description="Billing city", embeddable=True)
    billing_state: Optional[str] = AirweaveField(
        None, description="Billing state/province", embeddable=True
    )
    billing_postal_code: Optional[str] = AirweaveField(None, description="Billing postal code")
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
    shipping_postal_code: Optional[str] = AirweaveField(None, description="Shipping postal code")
    shipping_country: Optional[str] = AirweaveField(
        None, description="Shipping country", embeddable=True
    )
    created_date: Optional[datetime] = AirweaveField(
        None, description="Date and time when the account was created", is_created_at=True
    )
    last_modified_date: Optional[datetime] = AirweaveField(
        None, description="Date and time when the account was last modified", is_updated_at=True
    )
    last_activity_date: Optional[datetime] = AirweaveField(
        None, description="Date of the last activity on the account"
    )
    last_viewed_date: Optional[datetime] = AirweaveField(
        None, description="Date when the account was last viewed"
    )
    last_referenced_date: Optional[datetime] = AirweaveField(
        None, description="Date when the account was last referenced"
    )
    is_deleted: bool = AirweaveField(
        False, description="Indicates whether the account has been deleted"
    )
    is_customer_portal: bool = AirweaveField(
        False, description="Indicates whether this account has customer portal access"
    )
    is_person_account: bool = AirweaveField(
        False, description="Indicates whether this is a person account"
    )
    jigsaw: Optional[str] = AirweaveField(None, description="Data.com ID")
    clean_status: Optional[str] = AirweaveField(None, description="Clean status from Data.com")
    account_source: Optional[str] = AirweaveField(
        None, description="Source of the account", embeddable=True
    )
    sic_desc: Optional[str] = AirweaveField(None, description="SIC description", embeddable=True)
    duns_number: Optional[str] = AirweaveField(None, description="D-U-N-S number")
    tradestyle: Optional[str] = AirweaveField(None, description="Tradestyle", embeddable=True)
    naics_code: Optional[str] = AirweaveField(None, description="NAICS code")
    naics_desc: Optional[str] = AirweaveField(
        None, description="NAICS description", embeddable=True
    )
    year_started: Optional[str] = AirweaveField(None, description="Year the account was started")
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Additional metadata about the account"
    )


class SalesforceContactEntity(BaseEntity):
    """Schema for Salesforce Contact entities.

    https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_contact.htm
    """

    first_name: Optional[str] = AirweaveField(
        None, description="Contact's first name", embeddable=True
    )
    last_name: Optional[str] = AirweaveField(
        None, description="Contact's last name", embeddable=True
    )
    name: Optional[str] = AirweaveField(
        None, description="Full name (computed field)", embeddable=True
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
    fax: Optional[str] = AirweaveField(None, description="Contact's fax number")
    title: Optional[str] = AirweaveField(None, description="Contact's job title", embeddable=True)
    department: Optional[str] = AirweaveField(
        None, description="Contact's department", embeddable=True
    )
    account_id: Optional[str] = AirweaveField(None, description="ID of the associated account")
    lead_source: Optional[str] = AirweaveField(
        None, description="Source of the lead", embeddable=True
    )
    birthdate: Optional[datetime] = AirweaveField(None, description="Contact's birthdate")
    description: Optional[str] = AirweaveField(
        None, description="Contact description", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(None, description="ID of the user who owns the contact")
    created_date: Optional[datetime] = AirweaveField(
        None, description="Date and time when the contact was created", is_created_at=True
    )
    last_modified_date: Optional[datetime] = AirweaveField(
        None, description="Date and time when the contact was last modified", is_updated_at=True
    )
    last_activity_date: Optional[datetime] = AirweaveField(
        None, description="Date of the last activity on the contact"
    )
    last_viewed_date: Optional[datetime] = AirweaveField(
        None, description="Date when the contact was last viewed"
    )
    last_referenced_date: Optional[datetime] = AirweaveField(
        None, description="Date when the contact was last referenced"
    )
    is_deleted: bool = AirweaveField(
        False, description="Indicates whether the contact has been deleted"
    )
    is_email_bounced: bool = AirweaveField(
        False, description="Indicates whether emails to this contact bounce"
    )
    is_unread_by_owner: bool = AirweaveField(
        False, description="Indicates whether the contact is unread by the owner"
    )
    jigsaw: Optional[str] = AirweaveField(None, description="Data.com ID")
    jigsaw_contact_id: Optional[str] = AirweaveField(None, description="Data.com contact ID")
    clean_status: Optional[str] = AirweaveField(None, description="Clean status from Data.com")
    level: Optional[str] = AirweaveField(None, description="Contact level", embeddable=True)
    languages: Optional[str] = AirweaveField(None, description="Languages spoken", embeddable=True)
    has_opted_out_of_email: bool = AirweaveField(
        False, description="Indicates whether the contact has opted out of email"
    )
    has_opted_out_of_fax: bool = AirweaveField(
        False, description="Indicates whether the contact has opted out of fax"
    )
    do_not_call: bool = AirweaveField(
        False, description="Indicates whether the contact should not be called"
    )
    mailing_street: Optional[str] = AirweaveField(
        None, description="Mailing street address", embeddable=True
    )
    mailing_city: Optional[str] = AirweaveField(None, description="Mailing city", embeddable=True)
    mailing_state: Optional[str] = AirweaveField(
        None, description="Mailing state/province", embeddable=True
    )
    mailing_postal_code: Optional[str] = AirweaveField(None, description="Mailing postal code")
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
    other_postal_code: Optional[str] = AirweaveField(None, description="Other postal code")
    other_country: Optional[str] = AirweaveField(None, description="Other country", embeddable=True)
    assistant_name: Optional[str] = AirweaveField(
        None, description="Assistant's name", embeddable=True
    )
    assistant_phone: Optional[str] = AirweaveField(None, description="Assistant's phone number")
    reports_to_id: Optional[str] = AirweaveField(
        None, description="ID of the contact this contact reports to"
    )
    email_bounced_date: Optional[datetime] = AirweaveField(
        None, description="Date when email bounced"
    )
    email_bounced_reason: Optional[str] = AirweaveField(
        None, description="Reason why email bounced", embeddable=True
    )
    individual_id: Optional[str] = AirweaveField(
        None, description="ID of the associated individual"
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Additional metadata about the contact"
    )


class SalesforceOpportunityEntity(BaseEntity):
    """Schema for Salesforce Opportunity entities.

    https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_opportunity.htm
    """

    name: Optional[str] = AirweaveField(None, description="Opportunity name", embeddable=True)
    account_id: Optional[str] = AirweaveField(None, description="ID of the associated account")
    amount: Optional[float] = AirweaveField(None, description="Opportunity amount")
    close_date: Optional[datetime] = AirweaveField(None, description="Expected close date")
    stage_name: Optional[str] = AirweaveField(None, description="Sales stage", embeddable=True)
    probability: Optional[float] = AirweaveField(None, description="Probability percentage")
    forecast_category: Optional[str] = AirweaveField(
        None, description="Forecast category", embeddable=True
    )
    forecast_category_name: Optional[str] = AirweaveField(
        None, description="Forecast category name", embeddable=True
    )
    campaign_id: Optional[str] = AirweaveField(None, description="ID of the associated campaign")
    has_opportunity_line_item: bool = AirweaveField(
        False, description="Indicates whether the opportunity has line items"
    )
    pricebook2_id: Optional[str] = AirweaveField(None, description="ID of the associated pricebook")
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the opportunity"
    )
    created_date: Optional[datetime] = AirweaveField(
        None, description="Date and time when the opportunity was created", is_created_at=True
    )
    last_modified_date: Optional[datetime] = AirweaveField(
        None, description="Date and time when the opportunity was last modified", is_updated_at=True
    )
    last_activity_date: Optional[datetime] = AirweaveField(
        None, description="Date of the last activity on the opportunity"
    )
    last_viewed_date: Optional[datetime] = AirweaveField(
        None, description="Date when the opportunity was last viewed"
    )
    last_referenced_date: Optional[datetime] = AirweaveField(
        None, description="Date when the opportunity was last referenced"
    )
    is_deleted: bool = AirweaveField(
        False, description="Indicates whether the opportunity has been deleted"
    )
    is_won: bool = AirweaveField(False, description="Indicates whether the opportunity is won")
    is_closed: bool = AirweaveField(
        False, description="Indicates whether the opportunity is closed"
    )
    has_open_activity: bool = AirweaveField(
        False, description="Indicates whether the opportunity has open activities"
    )
    has_overdue_task: bool = AirweaveField(
        False, description="Indicates whether the opportunity has overdue tasks"
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
        default_factory=dict, description="Additional metadata about the opportunity"
    )
