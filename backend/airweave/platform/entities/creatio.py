"""Creatio CRM entity schemas.

Defines entity schemas for Creatio OData 4 API objects
"""

from datetime import datetime
from typing import Optional
from pydantic import ConfigDict

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class CreatioContactEntity(BaseEntity):
    """Schema for Creatio Contact entities.

    Reference:
        https://academy.creatio.com/docs/8.x/dev/development-on-creatio-platform/integrations-and-api/data-services/odata/basics
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    contact_id: str = AirweaveField(
        ..., validation_alias="Id", description="Unique Creatio ID for the contact.", is_entity_id=True
    )
    display_name: str = AirweaveField(
        ..., validation_alias="Name", description="Full name of the contact.", embeddable=True, is_name=True
    )
    created_on: Optional[datetime] = AirweaveField(
        None, validation_alias="CreatedOn", description="When the contact was created.", is_created_at=True
    )
    modified_on: Optional[datetime] = AirweaveField(
        None, validation_alias="ModifiedOn", description="When the contact was last modified.", is_updated_at=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, validation_alias="OwnerId", description="Owner user ID.", embeddable=False
    )
    dear: Optional[str] = AirweaveField(
        None, validation_alias="Dear", description="Salutation name.", embeddable=True
    )
    salutation_type_id: Optional[str] = AirweaveField(
        None, validation_alias="SalutationTypeId", description="Salutation type lookup ID.", embeddable=False
    )
    gender_id: Optional[str] = AirweaveField(
        None, validation_alias="GenderId", description="Gender lookup ID.", embeddable=False
    )
    account_id: Optional[str] = AirweaveField(
        None, validation_alias="AccountId", description="ID of the associated account.", embeddable=False
    )
    decision_role_id: Optional[str] = AirweaveField(
        None, validation_alias="DecisionRoleId", description="Decision role lookup ID.", embeddable=False
    )
    type_id: Optional[str] = AirweaveField(
        None, validation_alias="TypeId", description="Contact type lookup ID.", embeddable=False
    )
    job_id: Optional[str] = AirweaveField(
        None, validation_alias="JobId", description="Job lookup ID.", embeddable=False
    )
    job_title: Optional[str] = AirweaveField(
        None, validation_alias="JobTitle", description="Contact job title.", embeddable=True
    )
    department_id: Optional[str] = AirweaveField(
        None, validation_alias="DepartmentId", description="Department lookup ID.", embeddable=False
    )
    birth_date: Optional[datetime] = AirweaveField(
        None, validation_alias="BirthDate", description="Date of birth.", embeddable=False
    )
    phone: Optional[str] = AirweaveField(
        None, validation_alias="Phone", description="Contact phone number.", embeddable=True
    )
    mobile_phone: Optional[str] = AirweaveField(
        None, validation_alias="MobilePhone", description="Contact mobile phone number.", embeddable=True
    )
    home_phone: Optional[str] = AirweaveField(
        None, validation_alias="HomePhone", description="Contact home phone number.", embeddable=True
    )
    skype: Optional[str] = AirweaveField(
        None, validation_alias="Skype", description="Skype handle.", embeddable=True
    )
    email: Optional[str] = AirweaveField(
        None, validation_alias="Email", description="Contact email address.", embeddable=True
    )
    address_type_id: Optional[str] = AirweaveField(
        None, validation_alias="AddressTypeId", description="Address type lookup ID.", embeddable=False
    )
    address: Optional[str] = AirweaveField(
        None, validation_alias="Address", description="Contact address.", embeddable=True
    )
    city_id: Optional[str] = AirweaveField(
        None, validation_alias="CityId", description="City lookup ID.", embeddable=False
    )
    region_id: Optional[str] = AirweaveField(
        None, validation_alias="RegionId", description="Region lookup ID.", embeddable=False
    )
    zip_code: Optional[str] = AirweaveField(
        None, validation_alias="Zip", description="Postal/ZIP code.", embeddable=True
    )
    country_id: Optional[str] = AirweaveField(
        None, validation_alias="CountryId", description="Country lookup ID.", embeddable=False
    )


class CreatioAccountEntity(BaseEntity):
    """Schema for Creatio Account entities.

    Reference:
        https://academy.creatio.com/docs/8.x/dev/development-on-creatio-platform/integrations-and-api/data-services/odata/basics/references/odata-odata-4
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    account_id: str = AirweaveField(
        ..., validation_alias="Id", description="Unique Creatio ID for the account.", is_entity_id=True
    )
    display_name: str = AirweaveField(
        ..., validation_alias="Name", description="Name of the account.", embeddable=True, is_name=True
    )
    created_on: Optional[datetime] = AirweaveField(
        None, validation_alias="CreatedOn", description="When the account was created.", is_created_at=True
    )
    modified_on: Optional[datetime] = AirweaveField(
        None, validation_alias="ModifiedOn", description="When the account was last modified.", is_updated_at=True
    )
    code: Optional[str] = AirweaveField(
        None, validation_alias="Code", description="Account code.", embeddable=False
    )
    type_id: Optional[str] = AirweaveField(
        None, validation_alias="TypeId", description="Account type lookup ID.", embeddable=False
    )
    industry_id: Optional[str] = AirweaveField(
        None, validation_alias="IndustryId", description="Account industry lookup ID.", embeddable=False
    )
    web: Optional[str] = AirweaveField(
        None, validation_alias="Web", description="Website URL of the account.", embeddable=True
    )
    phone: Optional[str] = AirweaveField(
        None, validation_alias="Phone", description="Account phone number.", embeddable=True
    )
    address: Optional[str] = AirweaveField(
        None, validation_alias="Address", description="Account address.", embeddable=True
    )


class CreatioLeadEntity(BaseEntity):
    """Schema for Creatio Lead entities.

    Reference:
        https://academy.creatio.com/docs/8.x/dev/development-on-creatio-platform/integrations-and-api/data-services/odata/basics
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    lead_id: str = AirweaveField(
        ..., validation_alias="Id", description="Unique Creatio ID for the lead.", is_entity_id=True
    )
    lead_name: str = AirweaveField(
        ..., validation_alias="LeadName", description="Name of the lead.", embeddable=True, is_name=True
    )
    created_on: Optional[datetime] = AirweaveField(
        None, validation_alias="CreatedOn", description="When the lead was created.", is_created_at=True
    )
    modified_on: Optional[datetime] = AirweaveField(
        None, validation_alias="ModifiedOn", description="When the lead was last modified.", is_updated_at=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, validation_alias="OwnerId", description="Owner user ID.", embeddable=False
    )
    contact: Optional[str] = AirweaveField(
        None, validation_alias="Contact", description="Contact name associated with the lead.", embeddable=True
    )
    account: Optional[str] = AirweaveField(
        None, validation_alias="Account", description="Account name associated with the lead.", embeddable=True
    )
    status_id: Optional[str] = AirweaveField(
        None, validation_alias="StatusId", description="Lead status lookup ID.", embeddable=False
    )
    qualify_status_id: Optional[str] = AirweaveField(
        None, validation_alias="QualifyStatusId", description="Qualification status lookup ID.", embeddable=False
    )
    lead_type_id: Optional[str] = AirweaveField(
        None, validation_alias="LeadTypeId", description="Lead type lookup ID.", embeddable=False
    )
    budget: Optional[float] = AirweaveField(
        None, validation_alias="Budget", description="Lead budget amount.", embeddable=False
    )
    score: Optional[int] = AirweaveField(
        None, validation_alias="Score", description="Lead score.", embeddable=False
    )
    predictive_score: Optional[int] = AirweaveField(
        None, validation_alias="PredictiveScore", description="Predictive lead score.", embeddable=False
    )
    full_job_title: Optional[str] = AirweaveField(
        None, validation_alias="FullJobTitle", description="Full job title of the lead contact.", embeddable=True
    )
    dear: Optional[str] = AirweaveField(
        None, validation_alias="Dear", description="Salutation name.", embeddable=True
    )
    email: Optional[str] = AirweaveField(
        None, validation_alias="Email", description="Lead email address.", embeddable=True
    )
    business_phone: Optional[str] = AirweaveField(
        None, validation_alias="BusinesPhone", description="Business phone number.", embeddable=True
    )
    mobile_phone: Optional[str] = AirweaveField(
        None, validation_alias="MobilePhone", description="Mobile phone number.", embeddable=True
    )
    website: Optional[str] = AirweaveField(
        None, validation_alias="Website", description="Website URL.", embeddable=True
    )
    address: Optional[str] = AirweaveField(
        None, validation_alias="Address", description="Lead address.", embeddable=True
    )
    zip_code: Optional[str] = AirweaveField(
        None, validation_alias="Zip", description="Postal/ZIP code.", embeddable=True
    )
    notes: Optional[str] = AirweaveField(
        None, validation_alias="Notes", description="Lead notes.", embeddable=True
    )
    commentary: Optional[str] = AirweaveField(
        None, validation_alias="Commentary", description="Lead commentary.", embeddable=True
    )
    qualified_contact_id: Optional[str] = AirweaveField(
        None, validation_alias="QualifiedContactId", description="Qualified contact ID.", embeddable=False
    )
    qualified_account_id: Optional[str] = AirweaveField(
        None, validation_alias="QualifiedAccountId", description="Qualified account ID.", embeddable=False
    )
    decision_role_id: Optional[str] = AirweaveField(
        None, validation_alias="DecisionRoleId", description="Decision role lookup ID.", embeddable=False
    )
    industry_id: Optional[str] = AirweaveField(
        None, validation_alias="IndustryId", description="Industry lookup ID.", embeddable=False
    )
    meeting_date: Optional[datetime] = AirweaveField(
        None, validation_alias="MeetingDate", description="Meeting date.", embeddable=False
    )
    decision_date: Optional[datetime] = AirweaveField(
        None, validation_alias="DecisionDate", description="Decision date.", embeddable=False
    )


class CreatioOpportunityEntity(BaseEntity):
    """Schema for Creatio Opportunity entities.

    Reference:
        https://academy.creatio.com/docs/8.x/dev/development-on-creatio-platform/integrations-and-api/data-services/odata/basics
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    opportunity_id: str = AirweaveField(
        ..., validation_alias="Id", description="Unique Creatio ID for the opportunity.", is_entity_id=True
    )
    title: str = AirweaveField(
        ..., validation_alias="Title", description="Title of the opportunity.", embeddable=True, is_name=True
    )
    created_on: Optional[datetime] = AirweaveField(
        None, validation_alias="CreatedOn", description="When the opportunity was created.", is_created_at=True
    )
    modified_on: Optional[datetime] = AirweaveField(
        None, validation_alias="ModifiedOn", description="When the opportunity was last modified.", is_updated_at=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, validation_alias="OwnerId", description="Owner user ID.", embeddable=False
    )
    account_id: Optional[str] = AirweaveField(
        None, validation_alias="AccountId", description="Associated account ID.", embeddable=False
    )
    contact_id: Optional[str] = AirweaveField(
        None, validation_alias="ContactId", description="Associated contact ID.", embeddable=False
    )
    type_id: Optional[str] = AirweaveField(
        None, validation_alias="TypeId", description="Opportunity type lookup ID.", embeddable=False
    )
    stage_id: Optional[str] = AirweaveField(
        None, validation_alias="StageId", description="Current stage lookup ID.", embeddable=False
    )
    category_id: Optional[str] = AirweaveField(
        None, validation_alias="CategoryId", description="Category lookup ID.", embeddable=False
    )
    source_id: Optional[str] = AirweaveField(
        None, validation_alias="SourceId", description="Lead source lookup ID.", embeddable=False
    )
    responsible_department_id: Optional[str] = AirweaveField(
        None, validation_alias="ResponsibleDepartmentId", description="Responsible department lookup ID.", embeddable=False
    )
    lead_type_id: Optional[str] = AirweaveField(
        None, validation_alias="LeadTypeId", description="Lead type lookup ID.", embeddable=False
    )
    close_reason_id: Optional[str] = AirweaveField(
        None, validation_alias="CloseReasonId", description="Close reason lookup ID.", embeddable=False
    )
    budget: Optional[float] = AirweaveField(
        None, validation_alias="Budget", description="Opportunity budget.", embeddable=False
    )
    amount: Optional[float] = AirweaveField(
        None, validation_alias="Amount", description="Opportunity amount.", embeddable=False
    )
    probability: Optional[int] = AirweaveField(
        None, validation_alias="Probability", description="Win probability percentage.", embeddable=False
    )
    predictive_probability: Optional[int] = AirweaveField(
        None, validation_alias="PredictiveProbability", description="Predictive win probability.", embeddable=False
    )
    completeness: Optional[int] = AirweaveField(
        None, validation_alias="Completeness", description="Opportunity completeness percentage.", embeddable=False
    )
    due_date: Optional[datetime] = AirweaveField(
        None, validation_alias="DueDate", description="Due date for the opportunity.", embeddable=False
    )
    is_primary: Optional[bool] = AirweaveField(
        None, validation_alias="IsPrimary", description="Whether this is a primary opportunity.", embeddable=False
    )
    notes: Optional[str] = AirweaveField(
        None, validation_alias="Notes", description="Opportunity notes.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, validation_alias="Description", description="Opportunity description.", embeddable=True
    )
    weaknesses: Optional[str] = AirweaveField(
        None, validation_alias="Weaknesses", description="Identified weaknesses.", embeddable=True
    )
    strength: Optional[str] = AirweaveField(
        None, validation_alias="Strength", description="Identified strengths.", embeddable=True
    )
    tactic: Optional[str] = AirweaveField(
        None, validation_alias="Tactic", description="Sales tactic.", embeddable=True
    )
    decision_maker_id: Optional[str] = AirweaveField(
        None, validation_alias="DecisionMakerId", description="Decision maker contact ID.", embeddable=False
    )
    winner_id: Optional[str] = AirweaveField(
        None, validation_alias="WinnerId", description="Winner lookup ID.", embeddable=False
    )
    partner_id: Optional[str] = AirweaveField(
        None, validation_alias="PartnerId", description="Partner lookup ID.", embeddable=False
    )
    mood_id: Optional[str] = AirweaveField(
        None, validation_alias="MoodId", description="Mood lookup ID.", embeddable=False
    )
    mood_value: Optional[int] = AirweaveField(
        None, validation_alias="MoodValue", description="Mood value.", embeddable=False
    )
    forecast_commit: Optional[bool] = AirweaveField(
        None, validation_alias="ForecastCommit", description="Whether included in forecast commit.", embeddable=False
    )


class CreatioCampaignEntity(BaseEntity):
    """Schema for Creatio Campaign entities.

    Reference:
        https://academy.creatio.com/docs/8.x/dev/development-on-creatio-platform/integrations-and-api/data-services/odata/basics
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    campaign_id: str = AirweaveField(
        ..., validation_alias="Id", description="Unique Creatio ID for the campaign.", is_entity_id=True
    )
    name: str = AirweaveField(
        ..., validation_alias="Name", description="Name of the campaign.", embeddable=True, is_name=True
    )
    created_on: Optional[datetime] = AirweaveField(
        None, validation_alias="CreatedOn", description="When the campaign was created.", is_created_at=True
    )
    modified_on: Optional[datetime] = AirweaveField(
        None, validation_alias="ModifiedOn", description="When the campaign was last modified.", is_updated_at=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, validation_alias="OwnerId", description="Owner user ID.", embeddable=False
    )
    campaign_status_id: Optional[str] = AirweaveField(
        None, validation_alias="CampaignStatusId", description="Campaign status lookup ID.", embeddable=False
    )
    type_id: Optional[str] = AirweaveField(
        None, validation_alias="TypeId", description="Campaign type lookup ID.", embeddable=False
    )
    start_date: Optional[datetime] = AirweaveField(
        None, validation_alias="StartDate", description="Campaign start date.", embeddable=False
    )
    end_date: Optional[datetime] = AirweaveField(
        None, validation_alias="EndDate", description="Campaign end date.", embeddable=False
    )
    target_description: Optional[str] = AirweaveField(
        None, validation_alias="TargetDescription", description="Description of the campaign target.", embeddable=True
    )
    target_total: Optional[int] = AirweaveField(
        None, validation_alias="TargetTotal", description="Total target audience size.", embeddable=False
    )
    target_achieve: Optional[int] = AirweaveField(
        None, validation_alias="TargetAchieve", description="Number of targets achieved.", embeddable=False
    )
    target_percent: Optional[int] = AirweaveField(
        None, validation_alias="TargetPercent", description="Target achievement percentage.", embeddable=False
    )
    utm_campaign: Optional[str] = AirweaveField(
        None, validation_alias="UtmCampaign", description="UTM campaign parameter.", embeddable=True
    )
    notes: Optional[str] = AirweaveField(
        None, validation_alias="Notes", description="Campaign notes.", embeddable=True
    )
    in_progress: Optional[bool] = AirweaveField(
        None, validation_alias="InProgress", description="Whether the campaign is in progress.", embeddable=False
    )
    scheduled_start_date: Optional[datetime] = AirweaveField(
        None, validation_alias="ScheduledStartDate", description="Scheduled start date.", embeddable=False
    )
    scheduled_stop_date: Optional[datetime] = AirweaveField(
        None, validation_alias="ScheduledStopDate", description="Scheduled stop date.", embeddable=False
    )


class CreatioOrderEntity(BaseEntity):
    """Schema for Creatio Order entities.

    Reference:
        https://academy.creatio.com/docs/8.x/dev/development-on-creatio-platform/integrations-and-api/data-services/odata/basics
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    order_id: str = AirweaveField(
        ..., validation_alias="Id", description="Unique Creatio ID for the order.", is_entity_id=True
    )
    number: str = AirweaveField(
        ..., validation_alias="Number", description="Order number.", embeddable=True, is_name=True
    )
    created_on: Optional[datetime] = AirweaveField(
        None, validation_alias="CreatedOn", description="When the order was created.", is_created_at=True
    )
    modified_on: Optional[datetime] = AirweaveField(
        None, validation_alias="ModifiedOn", description="When the order was last modified.", is_updated_at=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, validation_alias="OwnerId", description="Owner user ID.", embeddable=False
    )
    account_id: Optional[str] = AirweaveField(
        None, validation_alias="AccountId", description="Associated account ID.", embeddable=False
    )
    contact_id: Optional[str] = AirweaveField(
        None, validation_alias="ContactId", description="Associated contact ID.", embeddable=False
    )
    opportunity_id: Optional[str] = AirweaveField(
        None, validation_alias="OpportunityId", description="Associated opportunity ID.", embeddable=False
    )
    status_id: Optional[str] = AirweaveField(
        None, validation_alias="StatusId", description="Order status lookup ID.", embeddable=False
    )
    payment_status_id: Optional[str] = AirweaveField(
        None, validation_alias="PaymentStatusId", description="Payment status lookup ID.", embeddable=False
    )
    delivery_status_id: Optional[str] = AirweaveField(
        None, validation_alias="DeliveryStatusId", description="Delivery status lookup ID.", embeddable=False
    )
    date: Optional[datetime] = AirweaveField(
        None, validation_alias="Date", description="Order date.", embeddable=False
    )
    due_date: Optional[datetime] = AirweaveField(
        None, validation_alias="DueDate", description="Order due date.", embeddable=False
    )
    actual_date: Optional[datetime] = AirweaveField(
        None, validation_alias="ActualDate", description="Actual completion date.", embeddable=False
    )
    currency_id: Optional[str] = AirweaveField(
        None, validation_alias="CurrencyId", description="Currency lookup ID.", embeddable=False
    )
    currency_rate: Optional[float] = AirweaveField(
        None, validation_alias="CurrencyRate", description="Currency exchange rate.", embeddable=False
    )
    amount: Optional[float] = AirweaveField(
        None, validation_alias="Amount", description="Order total amount.", embeddable=False
    )
    payment_amount: Optional[float] = AirweaveField(
        None, validation_alias="PaymentAmount", description="Amount paid.", embeddable=False
    )
    primary_amount: Optional[float] = AirweaveField(
        None, validation_alias="PrimaryAmount", description="Amount in primary currency.", embeddable=False
    )
    delivery_address: Optional[str] = AirweaveField(
        None, validation_alias="DeliveryAddress", description="Delivery address.", embeddable=True
    )
    delivery_type_id: Optional[str] = AirweaveField(
        None, validation_alias="DeliveryTypeId", description="Delivery type lookup ID.", embeddable=False
    )
    payment_type_id: Optional[str] = AirweaveField(
        None, validation_alias="PaymentTypeId", description="Payment type lookup ID.", embeddable=False
    )
    receiver_name: Optional[str] = AirweaveField(
        None, validation_alias="ReceiverName", description="Receiver name.", embeddable=True
    )
    contact_number: Optional[str] = AirweaveField(
        None, validation_alias="ContactNumber", description="Contact phone number.", embeddable=True
    )
    notes: Optional[str] = AirweaveField(
        None, validation_alias="Notes", description="Order notes.", embeddable=True
    )
    comment: Optional[str] = AirweaveField(
        None, validation_alias="Comment", description="Order comment.", embeddable=True
    )
