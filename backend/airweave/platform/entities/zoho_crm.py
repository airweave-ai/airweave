"""Zoho CRM entity schemas.

Based on the Zoho CRM REST API v8, we define entity schemas for
Zoho CRM objects including the full sales suite:
- Accounts, Contacts, Deals (core CRM)
- Leads (pre-qualified prospects)
- Products (product catalog)
- Quotes, Sales Orders, Invoices (sales documents)

These schemas follow the same style as other CRM connectors (e.g., Salesforce, HubSpot),
where each entity class inherits from BaseEntity and adds relevant fields with
shared or per-resource metadata as needed.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class ZohoCRMAccountEntity(BaseEntity):
    """Schema for Zoho CRM Account entities.

    Reference:
        https://www.zoho.com/crm/developer/docs/api/v8/modules-api.html
    """

    account_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the account.", is_entity_id=True
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
        description="URL to open the account in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    website: Optional[str] = AirweaveField(
        None, description="Account website URL", embeddable=False
    )
    phone: Optional[str] = AirweaveField(None, description="Account phone number", embeddable=True)
    fax: Optional[str] = AirweaveField(None, description="Account fax number", embeddable=False)
    industry: Optional[str] = AirweaveField(None, description="Account industry", embeddable=True)
    annual_revenue: Optional[float] = AirweaveField(
        None, description="Annual revenue", embeddable=False
    )
    employees: Optional[int] = AirweaveField(
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
    parent_account_id: Optional[str] = AirweaveField(
        None, description="ID of parent account", embeddable=False
    )
    account_type: Optional[str] = AirweaveField(None, description="Account type", embeddable=True)
    billing_street: Optional[str] = AirweaveField(
        None, description="Billing street address", embeddable=True
    )
    billing_city: Optional[str] = AirweaveField(None, description="Billing city", embeddable=True)
    billing_state: Optional[str] = AirweaveField(
        None, description="Billing state/province", embeddable=True
    )
    billing_code: Optional[str] = AirweaveField(
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
    shipping_code: Optional[str] = AirweaveField(
        None, description="Shipping postal code", embeddable=False
    )
    shipping_country: Optional[str] = AirweaveField(
        None, description="Shipping country", embeddable=True
    )
    account_number: Optional[str] = AirweaveField(
        None, description="Account number", embeddable=True
    )
    sic_code: Optional[str] = AirweaveField(None, description="SIC code", embeddable=False)
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the account", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the account owner", embeddable=True
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


class ZohoCRMContactEntity(BaseEntity):
    """Schema for Zoho CRM Contact entities.

    Reference:
        https://www.zoho.com/crm/developer/docs/api/v8/modules-api.html
    """

    contact_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the contact.", is_entity_id=True
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
        description="URL to view the contact in Zoho CRM.",
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
    secondary_email: Optional[str] = AirweaveField(
        None, description="Contact's secondary email address", embeddable=True
    )
    phone: Optional[str] = AirweaveField(
        None, description="Contact's phone number", embeddable=True
    )
    mobile: Optional[str] = AirweaveField(
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
    account_name: Optional[str] = AirweaveField(
        None, description="Name of the associated account", embeddable=True
    )
    lead_source: Optional[str] = AirweaveField(
        None, description="Source of the lead", embeddable=True
    )
    date_of_birth: Optional[str] = AirweaveField(
        None, description="Contact's date of birth", embeddable=False
    )
    description: Optional[str] = AirweaveField(
        None, description="Contact description", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the contact", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the contact owner", embeddable=True
    )
    mailing_street: Optional[str] = AirweaveField(
        None, description="Mailing street address", embeddable=True
    )
    mailing_city: Optional[str] = AirweaveField(None, description="Mailing city", embeddable=True)
    mailing_state: Optional[str] = AirweaveField(
        None, description="Mailing state/province", embeddable=True
    )
    mailing_zip: Optional[str] = AirweaveField(
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
    other_zip: Optional[str] = AirweaveField(
        None, description="Other postal code", embeddable=False
    )
    other_country: Optional[str] = AirweaveField(None, description="Other country", embeddable=True)
    assistant: Optional[str] = AirweaveField(None, description="Assistant's name", embeddable=True)
    asst_phone: Optional[str] = AirweaveField(
        None, description="Assistant's phone number", embeddable=False
    )
    reports_to_id: Optional[str] = AirweaveField(
        None, description="ID of the contact this contact reports to", embeddable=False
    )
    email_opt_out: bool = AirweaveField(
        False,
        description="Indicates whether the contact has opted out of email",
        embeddable=False,
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Additional metadata about the contact", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the contact."""
        return self.web_url_value or ""


class ZohoCRMDealEntity(BaseEntity):
    """Schema for Zoho CRM Deal entities (pipelines).

    Reference:
        https://www.zoho.com/crm/developer/docs/api/v8/modules-api.html
    """

    deal_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the deal.", is_entity_id=True
    )
    deal_name: str = AirweaveField(
        ..., description="Display name of the deal.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the deal was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the deal was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the deal in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    account_id: Optional[str] = AirweaveField(
        None, description="ID of the associated account", embeddable=False
    )
    account_name: Optional[str] = AirweaveField(
        None, description="Name of the associated account", embeddable=True
    )
    contact_id: Optional[str] = AirweaveField(
        None, description="ID of the associated contact", embeddable=False
    )
    contact_name: Optional[str] = AirweaveField(
        None, description="Name of the associated contact", embeddable=True
    )
    amount: Optional[float] = AirweaveField(None, description="Deal amount", embeddable=True)
    closing_date: Optional[str] = AirweaveField(
        None, description="Expected closing date", embeddable=True
    )
    stage: Optional[str] = AirweaveField(None, description="Sales stage", embeddable=True)
    probability: Optional[float] = AirweaveField(
        None, description="Probability percentage", embeddable=True
    )
    expected_revenue: Optional[float] = AirweaveField(
        None, description="Expected revenue", embeddable=False
    )
    pipeline: Optional[str] = AirweaveField(None, description="Pipeline name", embeddable=True)
    campaign_source: Optional[str] = AirweaveField(
        None, description="Campaign source", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the deal", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the deal owner", embeddable=True
    )
    lead_source: Optional[str] = AirweaveField(
        None, description="Source of the lead", embeddable=True
    )
    deal_type: Optional[str] = AirweaveField(None, description="Deal type", embeddable=True)
    next_step: Optional[str] = AirweaveField(
        None, description="Next step in the sales process", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Deal description", embeddable=True
    )
    reason_for_loss: Optional[str] = AirweaveField(
        None, description="Reason for loss if deal was lost", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the deal",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the deal."""
        return self.web_url_value or ""


class ZohoCRMLeadEntity(BaseEntity):
    """Schema for Zoho CRM Lead entities.

    Leads are pre-qualified prospects that haven't been converted to contacts yet.

    Reference:
        https://www.zoho.com/crm/developer/docs/api/v8/modules-api.html
    """

    lead_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the lead.", is_entity_id=True
    )
    lead_name: str = AirweaveField(
        ..., description="Display name of the lead.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the lead was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the lead was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the lead in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    first_name: Optional[str] = AirweaveField(
        None, description="Lead's first name", embeddable=True
    )
    last_name: Optional[str] = AirweaveField(None, description="Lead's last name", embeddable=True)
    company: Optional[str] = AirweaveField(None, description="Lead's company name", embeddable=True)
    email: Optional[str] = AirweaveField(None, description="Lead's email address", embeddable=True)
    phone: Optional[str] = AirweaveField(None, description="Lead's phone number", embeddable=True)
    mobile: Optional[str] = AirweaveField(
        None, description="Lead's mobile phone number", embeddable=True
    )
    fax: Optional[str] = AirweaveField(None, description="Lead's fax number", embeddable=False)
    title: Optional[str] = AirweaveField(None, description="Lead's job title", embeddable=True)
    website: Optional[str] = AirweaveField(None, description="Lead's website", embeddable=False)
    lead_source: Optional[str] = AirweaveField(
        None, description="Source of the lead", embeddable=True
    )
    lead_status: Optional[str] = AirweaveField(
        None, description="Current status of the lead", embeddable=True
    )
    industry: Optional[str] = AirweaveField(None, description="Lead's industry", embeddable=True)
    annual_revenue: Optional[float] = AirweaveField(
        None, description="Annual revenue", embeddable=False
    )
    no_of_employees: Optional[int] = AirweaveField(
        None, description="Number of employees", embeddable=False
    )
    rating: Optional[str] = AirweaveField(None, description="Lead rating", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Lead description", embeddable=True
    )
    street: Optional[str] = AirweaveField(None, description="Street address", embeddable=True)
    city: Optional[str] = AirweaveField(None, description="City", embeddable=True)
    state: Optional[str] = AirweaveField(None, description="State/province", embeddable=True)
    zip_code: Optional[str] = AirweaveField(None, description="Postal code", embeddable=False)
    country: Optional[str] = AirweaveField(None, description="Country", embeddable=True)
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the lead", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the lead owner", embeddable=True
    )
    converted: bool = AirweaveField(
        False, description="Whether the lead has been converted", embeddable=False
    )
    email_opt_out: bool = AirweaveField(
        False,
        description="Indicates whether the lead has opted out of email",
        embeddable=False,
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the lead",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the lead."""
        return self.web_url_value or ""


class ZohoCRMProductEntity(BaseEntity):
    """Schema for Zoho CRM Product entities.

    Products represent items in the product catalog.

    Reference:
        https://www.zoho.com/crm/developer/docs/api/v8/modules-api.html
    """

    product_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the product.", is_entity_id=True
    )
    product_name: str = AirweaveField(
        ..., description="Display name of the product.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the product was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the product was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the product in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    product_code: Optional[str] = AirweaveField(
        None, description="Product code/SKU", embeddable=True
    )
    product_category: Optional[str] = AirweaveField(
        None, description="Product category", embeddable=True
    )
    manufacturer: Optional[str] = AirweaveField(
        None, description="Product manufacturer", embeddable=True
    )
    vendor_name: Optional[str] = AirweaveField(None, description="Vendor name", embeddable=True)
    unit_price: Optional[float] = AirweaveField(None, description="Unit price", embeddable=True)
    sales_start_date: Optional[str] = AirweaveField(
        None, description="Sales start date", embeddable=False
    )
    sales_end_date: Optional[str] = AirweaveField(
        None, description="Sales end date", embeddable=False
    )
    support_start_date: Optional[str] = AirweaveField(
        None, description="Support start date", embeddable=False
    )
    support_expiry_date: Optional[str] = AirweaveField(
        None, description="Support expiry date", embeddable=False
    )
    qty_in_stock: Optional[float] = AirweaveField(
        None, description="Quantity in stock", embeddable=False
    )
    qty_in_demand: Optional[float] = AirweaveField(
        None, description="Quantity in demand", embeddable=False
    )
    qty_ordered: Optional[float] = AirweaveField(
        None, description="Quantity ordered", embeddable=False
    )
    reorder_level: Optional[float] = AirweaveField(
        None, description="Reorder level", embeddable=False
    )
    commission_rate: Optional[float] = AirweaveField(
        None, description="Commission rate", embeddable=False
    )
    tax: Optional[str] = AirweaveField(None, description="Tax information", embeddable=False)
    taxable: bool = AirweaveField(
        False, description="Whether the product is taxable", embeddable=False
    )
    product_active: bool = AirweaveField(
        True, description="Whether the product is active", embeddable=False
    )
    description: Optional[str] = AirweaveField(
        None, description="Product description", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the product", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the product owner", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the product",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the product."""
        return self.web_url_value or ""


class ZohoCRMQuoteEntity(BaseEntity):
    """Schema for Zoho CRM Quote entities.

    Quotes are sales proposals sent to potential customers.

    Reference:
        https://www.zoho.com/crm/developer/docs/api/v8/modules-api.html
    """

    quote_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the quote.", is_entity_id=True
    )
    quote_name: str = AirweaveField(
        ..., description="Display name/subject of the quote.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the quote was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the quote was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the quote in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    quote_number: Optional[str] = AirweaveField(None, description="Quote number", embeddable=True)
    quote_stage: Optional[str] = AirweaveField(None, description="Quote stage", embeddable=True)
    account_id: Optional[str] = AirweaveField(
        None, description="ID of the associated account", embeddable=False
    )
    account_name: Optional[str] = AirweaveField(
        None, description="Name of the associated account", embeddable=True
    )
    contact_id: Optional[str] = AirweaveField(
        None, description="ID of the associated contact", embeddable=False
    )
    contact_name: Optional[str] = AirweaveField(
        None, description="Name of the associated contact", embeddable=True
    )
    deal_id: Optional[str] = AirweaveField(
        None, description="ID of the associated deal", embeddable=False
    )
    deal_name: Optional[str] = AirweaveField(
        None, description="Name of the associated deal", embeddable=True
    )
    valid_till: Optional[str] = AirweaveField(
        None, description="Quote validity date", embeddable=False
    )
    sub_total: Optional[float] = AirweaveField(None, description="Subtotal amount", embeddable=True)
    discount: Optional[float] = AirweaveField(None, description="Discount amount", embeddable=False)
    tax: Optional[float] = AirweaveField(None, description="Tax amount", embeddable=False)
    adjustment: Optional[float] = AirweaveField(
        None, description="Adjustment amount", embeddable=False
    )
    grand_total: Optional[float] = AirweaveField(
        None, description="Grand total amount", embeddable=True
    )
    carrier: Optional[str] = AirweaveField(None, description="Carrier/shipper", embeddable=True)
    shipping_charge: Optional[float] = AirweaveField(
        None, description="Shipping charge", embeddable=False
    )
    terms_and_conditions: Optional[str] = AirweaveField(
        None, description="Terms and conditions", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Quote description", embeddable=True
    )
    billing_street: Optional[str] = AirweaveField(
        None, description="Billing street", embeddable=True
    )
    billing_city: Optional[str] = AirweaveField(None, description="Billing city", embeddable=True)
    billing_state: Optional[str] = AirweaveField(None, description="Billing state", embeddable=True)
    billing_code: Optional[str] = AirweaveField(
        None, description="Billing postal code", embeddable=False
    )
    billing_country: Optional[str] = AirweaveField(
        None, description="Billing country", embeddable=True
    )
    shipping_street: Optional[str] = AirweaveField(
        None, description="Shipping street", embeddable=True
    )
    shipping_city: Optional[str] = AirweaveField(None, description="Shipping city", embeddable=True)
    shipping_state: Optional[str] = AirweaveField(
        None, description="Shipping state", embeddable=True
    )
    shipping_code: Optional[str] = AirweaveField(
        None, description="Shipping postal code", embeddable=False
    )
    shipping_country: Optional[str] = AirweaveField(
        None, description="Shipping country", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the quote", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the quote owner", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the quote",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the quote."""
        return self.web_url_value or ""


class ZohoCRMSalesOrderEntity(BaseEntity):
    """Schema for Zoho CRM Sales Order entities.

    Sales Orders are confirmed orders from customers.

    Reference:
        https://www.zoho.com/crm/developer/docs/api/v8/modules-api.html
    """

    sales_order_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the sales order.", is_entity_id=True
    )
    sales_order_name: str = AirweaveField(
        ..., description="Display name/subject of the sales order.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the sales order was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the sales order was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the sales order in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    so_number: Optional[str] = AirweaveField(
        None, description="Sales order number", embeddable=True
    )
    status: Optional[str] = AirweaveField(None, description="Sales order status", embeddable=True)
    account_id: Optional[str] = AirweaveField(
        None, description="ID of the associated account", embeddable=False
    )
    account_name: Optional[str] = AirweaveField(
        None, description="Name of the associated account", embeddable=True
    )
    contact_id: Optional[str] = AirweaveField(
        None, description="ID of the associated contact", embeddable=False
    )
    contact_name: Optional[str] = AirweaveField(
        None, description="Name of the associated contact", embeddable=True
    )
    deal_id: Optional[str] = AirweaveField(
        None, description="ID of the associated deal", embeddable=False
    )
    deal_name: Optional[str] = AirweaveField(
        None, description="Name of the associated deal", embeddable=True
    )
    quote_id: Optional[str] = AirweaveField(
        None, description="ID of the associated quote", embeddable=False
    )
    quote_name: Optional[str] = AirweaveField(
        None, description="Name of the associated quote", embeddable=True
    )
    due_date: Optional[str] = AirweaveField(None, description="Due date", embeddable=False)
    sub_total: Optional[float] = AirweaveField(None, description="Subtotal amount", embeddable=True)
    discount: Optional[float] = AirweaveField(None, description="Discount amount", embeddable=False)
    tax: Optional[float] = AirweaveField(None, description="Tax amount", embeddable=False)
    adjustment: Optional[float] = AirweaveField(
        None, description="Adjustment amount", embeddable=False
    )
    grand_total: Optional[float] = AirweaveField(
        None, description="Grand total amount", embeddable=True
    )
    carrier: Optional[str] = AirweaveField(None, description="Carrier/shipper", embeddable=True)
    shipping_charge: Optional[float] = AirweaveField(
        None, description="Shipping charge", embeddable=False
    )
    excise_duty: Optional[float] = AirweaveField(None, description="Excise duty", embeddable=False)
    terms_and_conditions: Optional[str] = AirweaveField(
        None, description="Terms and conditions", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Sales order description", embeddable=True
    )
    billing_street: Optional[str] = AirweaveField(
        None, description="Billing street", embeddable=True
    )
    billing_city: Optional[str] = AirweaveField(None, description="Billing city", embeddable=True)
    billing_state: Optional[str] = AirweaveField(None, description="Billing state", embeddable=True)
    billing_code: Optional[str] = AirweaveField(
        None, description="Billing postal code", embeddable=False
    )
    billing_country: Optional[str] = AirweaveField(
        None, description="Billing country", embeddable=True
    )
    shipping_street: Optional[str] = AirweaveField(
        None, description="Shipping street", embeddable=True
    )
    shipping_city: Optional[str] = AirweaveField(None, description="Shipping city", embeddable=True)
    shipping_state: Optional[str] = AirweaveField(
        None, description="Shipping state", embeddable=True
    )
    shipping_code: Optional[str] = AirweaveField(
        None, description="Shipping postal code", embeddable=False
    )
    shipping_country: Optional[str] = AirweaveField(
        None, description="Shipping country", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the sales order", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the sales order owner", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the sales order",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the sales order."""
        return self.web_url_value or ""


class ZohoCRMInvoiceEntity(BaseEntity):
    """Schema for Zoho CRM Invoice entities.

    Invoices are billing documents sent to customers.

    Reference:
        https://www.zoho.com/crm/developer/docs/api/v8/modules-api.html
    """

    invoice_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the invoice.", is_entity_id=True
    )
    invoice_name: str = AirweaveField(
        ..., description="Display name/subject of the invoice.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the invoice was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the invoice was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the invoice in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    invoice_number: Optional[str] = AirweaveField(
        None, description="Invoice number", embeddable=True
    )
    invoice_date: Optional[str] = AirweaveField(None, description="Invoice date", embeddable=False)
    status: Optional[str] = AirweaveField(None, description="Invoice status", embeddable=True)
    account_id: Optional[str] = AirweaveField(
        None, description="ID of the associated account", embeddable=False
    )
    account_name: Optional[str] = AirweaveField(
        None, description="Name of the associated account", embeddable=True
    )
    contact_id: Optional[str] = AirweaveField(
        None, description="ID of the associated contact", embeddable=False
    )
    contact_name: Optional[str] = AirweaveField(
        None, description="Name of the associated contact", embeddable=True
    )
    deal_id: Optional[str] = AirweaveField(
        None, description="ID of the associated deal", embeddable=False
    )
    deal_name: Optional[str] = AirweaveField(
        None, description="Name of the associated deal", embeddable=True
    )
    sales_order_id: Optional[str] = AirweaveField(
        None, description="ID of the associated sales order", embeddable=False
    )
    sales_order_name: Optional[str] = AirweaveField(
        None, description="Name of the associated sales order", embeddable=True
    )
    due_date: Optional[str] = AirweaveField(None, description="Payment due date", embeddable=False)
    purchase_order: Optional[str] = AirweaveField(
        None, description="Purchase order number", embeddable=True
    )
    sub_total: Optional[float] = AirweaveField(None, description="Subtotal amount", embeddable=True)
    discount: Optional[float] = AirweaveField(None, description="Discount amount", embeddable=False)
    tax: Optional[float] = AirweaveField(None, description="Tax amount", embeddable=False)
    adjustment: Optional[float] = AirweaveField(
        None, description="Adjustment amount", embeddable=False
    )
    grand_total: Optional[float] = AirweaveField(
        None, description="Grand total amount", embeddable=True
    )
    shipping_charge: Optional[float] = AirweaveField(
        None, description="Shipping charge", embeddable=False
    )
    excise_duty: Optional[float] = AirweaveField(None, description="Excise duty", embeddable=False)
    terms_and_conditions: Optional[str] = AirweaveField(
        None, description="Terms and conditions", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Invoice description", embeddable=True
    )
    billing_street: Optional[str] = AirweaveField(
        None, description="Billing street", embeddable=True
    )
    billing_city: Optional[str] = AirweaveField(None, description="Billing city", embeddable=True)
    billing_state: Optional[str] = AirweaveField(None, description="Billing state", embeddable=True)
    billing_code: Optional[str] = AirweaveField(
        None, description="Billing postal code", embeddable=False
    )
    billing_country: Optional[str] = AirweaveField(
        None, description="Billing country", embeddable=True
    )
    shipping_street: Optional[str] = AirweaveField(
        None, description="Shipping street", embeddable=True
    )
    shipping_city: Optional[str] = AirweaveField(None, description="Shipping city", embeddable=True)
    shipping_state: Optional[str] = AirweaveField(
        None, description="Shipping state", embeddable=True
    )
    shipping_code: Optional[str] = AirweaveField(
        None, description="Shipping postal code", embeddable=False
    )
    shipping_country: Optional[str] = AirweaveField(
        None, description="Shipping country", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the invoice", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the invoice owner", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the invoice",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the invoice."""
        return self.web_url_value or ""
