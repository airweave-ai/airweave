"""All source connectors."""

from .airtable import AirtableSource
from .apollo import ApolloSource
from .asana import AsanaSource
from .attio import AttioSource
from .bitbucket import BitbucketSource
from .box import BoxSource
from .clickup import ClickUpSource
from .coda import CodaSource
from .confluence import ConfluenceSource
from .ctti import CTTISource
from .document360 import Document360Source
from .dropbox import DropboxSource
from .file_stub import FileStubSource
from .fireflies import FirefliesSource
from .freshdesk import FreshdeskSource
from .github import GitHubSource
from .gitlab import GitLabSource
from .gmail import GmailSource
from .google_calendar import GoogleCalendarSource
from .google_docs import GoogleDocsSource
from .google_drive import GoogleDriveSource
from .google_slides import GoogleSlidesSource
from .hubspot import HubspotSource
from .jira import JiraSource
from .linear import LinearSource
from .monday import MondaySource
from .notion import NotionSource
from .onedrive import OneDriveSource
from .onenote import OneNoteSource
from .outlook_calendar import OutlookCalendarSource
from .outlook_mail import OutlookMailSource
from .pipedrive import PipedriveSource
from .salesforce import SalesforceSource
from .servicenow import ServiceNowSource
from .sharepoint import SharePointSource
from .sharepoint2019v2.source import SharePoint2019V2Source
from .shopify import ShopifySource
from .slack import SlackSource
from .slite import SliteSource
from .snapshot import SnapshotSource
from .stripe import StripeSource
from .stub import StubSource
from .teams import TeamsSource
from .todoist import TodoistSource
from .trello import TrelloSource
from .word import WordSource
from .zendesk import ZendeskSource
from .zoho_crm import ZohoCRMSource

ALL_SOURCES: list[type] = [
    AirtableSource,
    ApolloSource,
    AsanaSource,
    AttioSource,
    BitbucketSource,
    BoxSource,
    ClickUpSource,
    CodaSource,
    ConfluenceSource,
    CTTISource,
    Document360Source,
    DropboxSource,
    FileStubSource,
    FirefliesSource,
    FreshdeskSource,
    GitHubSource,
    GitLabSource,
    GmailSource,
    GoogleCalendarSource,
    GoogleDocsSource,
    GoogleDriveSource,
    GoogleSlidesSource,
    HubspotSource,
    JiraSource,
    LinearSource,
    MondaySource,
    NotionSource,
    OneDriveSource,
    OneNoteSource,
    OutlookCalendarSource,
    OutlookMailSource,
    PipedriveSource,
    SalesforceSource,
    ServiceNowSource,
    SharePointSource,
    SharePoint2019V2Source,
    ShopifySource,
    SliteSource,
    SlackSource,
    SnapshotSource,
    StripeSource,
    StubSource,
    TeamsSource,
    TodoistSource,
    TrelloSource,
    WordSource,
    ZendeskSource,
    ZohoCRMSource,
]
