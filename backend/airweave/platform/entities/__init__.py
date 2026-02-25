"""All entity definitions, grouped by source."""

from ._base import (  # noqa: F401
    AccessControl,
    BaseEntity,
    Breadcrumb,
    CodeFileEntity,
    FileEntity,
)
from .airtable import (
    AirtableAttachmentEntity,
    AirtableBaseEntity,
    AirtableCommentEntity,
    AirtableRecordEntity,
    AirtableTableEntity,
    AirtableUserEntity,
)
from .apollo import (
    ApolloAccountEntity,
    ApolloContactEntity,
    ApolloEmailActivityEntity,
    ApolloSequenceEntity,
)
from .asana import (
    AsanaCommentEntity,
    AsanaFileEntity,
    AsanaProjectEntity,
    AsanaSectionEntity,
    AsanaTaskEntity,
    AsanaWorkspaceEntity,
)
from .attio import (
    AttioListEntity,
    AttioNoteEntity,
    AttioObjectEntity,
    AttioRecordEntity,
)
from .bitbucket import (
    BitbucketCodeFileEntity,
    BitbucketDirectoryEntity,
    BitbucketRepositoryEntity,
    BitbucketWorkspaceEntity,
)
from .box import (
    BoxCollaborationEntity,
    BoxCommentEntity,
    BoxFileEntity,
    BoxFolderEntity,
    BoxUserEntity,
)
from .clickup import (
    ClickUpCommentEntity,
    ClickUpFileEntity,
    ClickUpFolderEntity,
    ClickUpListEntity,
    ClickUpSpaceEntity,
    ClickUpSubtaskEntity,
    ClickUpTaskEntity,
    ClickUpWorkspaceEntity,
)
from .coda import (
    CodaDocEntity,
    CodaPageEntity,
    CodaRowEntity,
    CodaTableEntity,
)
from .confluence import (
    ConfluenceBlogPostEntity,
    ConfluenceCommentEntity,
    ConfluenceCustomContentEntity,
    ConfluenceDatabaseEntity,
    ConfluenceFolderEntity,
    ConfluenceLabelEntity,
    ConfluencePageEntity,
    ConfluenceSpaceEntity,
    ConfluenceTaskEntity,
    ConfluenceWhiteboardEntity,
)
from .ctti import CTTIWebEntity
from .document360 import (
    Document360ArticleEntity,
    Document360CategoryEntity,
    Document360ProjectVersionEntity,
)
from .dropbox import (
    DropboxAccountEntity,
    DropboxFileEntity,
    DropboxFolderEntity,
)
from .file_stub import (
    DocxFileStubEntity,
    FileStubContainerEntity,
    PdfFileStubEntity,
    PptxFileStubEntity,
    ScannedPdfFileStubEntity,
)
from .fireflies import (
    FirefliesTranscriptEntity,
)
from .freshdesk import (
    FreshdeskCompanyEntity,
    FreshdeskContactEntity,
    FreshdeskConversationEntity,
    FreshdeskSolutionArticleEntity,
    FreshdeskTicketEntity,
)
from .github import (
    GitHubCodeFileEntity,
    GithubContentEntity,
    GitHubDirectoryEntity,
    GitHubFileDeletionEntity,
    GithubRepoEntity,
    GitHubRepositoryEntity,
)
from .gitlab import (
    GitLabCodeFileEntity,
    GitLabDirectoryEntity,
    GitLabIssueEntity,
    GitLabMergeRequestEntity,
    GitLabProjectEntity,
    GitLabUserEntity,
)
from .gmail import (
    GmailAttachmentEntity,
    GmailMessageDeletionEntity,
    GmailMessageEntity,
    GmailThreadEntity,
)
from .google_calendar import (
    GoogleCalendarCalendarEntity,
    GoogleCalendarEventEntity,
    GoogleCalendarFreeBusyEntity,
    GoogleCalendarListEntity,
)
from .google_docs import GoogleDocsDocumentEntity
from .google_drive import (
    GoogleDriveDriveEntity,
    GoogleDriveFileDeletionEntity,
    GoogleDriveFileEntity,
)
from .google_slides import (
    GoogleSlidesPresentationEntity,
    GoogleSlidesSlideEntity,
)
from .hubspot import (
    HubspotCompanyEntity,
    HubspotContactEntity,
    HubspotDealEntity,
    HubspotTicketEntity,
)
from .jira import (
    JiraIssueEntity,
    JiraProjectEntity,
    ZephyrTestCaseEntity,
    ZephyrTestCycleEntity,
    ZephyrTestPlanEntity,
)
from .linear import (
    LinearAttachmentEntity,
    LinearCommentEntity,
    LinearIssueEntity,
    LinearProjectEntity,
    LinearTeamEntity,
    LinearUserEntity,
)
from .monday import (
    MondayBoardEntity,
    MondayColumnEntity,
    MondayGroupEntity,
    MondayItemEntity,
    MondaySubitemEntity,
    MondayUpdateEntity,
)
from .notion import (
    NotionDatabaseEntity,
    NotionFileEntity,
    NotionPageEntity,
    NotionPropertyEntity,
)
from .onedrive import (
    OneDriveDriveEntity,
    OneDriveDriveItemEntity,
)
from .onenote import (
    OneNoteNotebookEntity,
    OneNotePageFileEntity,
    OneNoteSectionEntity,
    OneNoteSectionGroupEntity,
)
from .outlook_calendar import (
    OutlookCalendarAttachmentEntity,
    OutlookCalendarCalendarEntity,
    OutlookCalendarEventEntity,
)
from .outlook_mail import (
    OutlookAttachmentEntity,
    OutlookMailFolderDeletionEntity,
    OutlookMailFolderEntity,
    OutlookMessageDeletionEntity,
    OutlookMessageEntity,
)
from .pipedrive import (
    PipedriveActivityEntity,
    PipedriveDealEntity,
    PipedriveLeadEntity,
    PipedriveNoteEntity,
    PipedriveOrganizationEntity,
    PipedrivePersonEntity,
    PipedriveProductEntity,
)
from .salesforce import (
    SalesforceAccountEntity,
    SalesforceContactEntity,
    SalesforceOpportunityEntity,
)
from .servicenow import (
    ServiceNowCatalogItemEntity,
    ServiceNowChangeRequestEntity,
    ServiceNowIncidentEntity,
    ServiceNowKnowledgeArticleEntity,
    ServiceNowProblemEntity,
)
from .sharepoint import (
    SharePointDriveEntity,
    SharePointDriveItemEntity,
    SharePointGroupEntity,
    SharePointListEntity,
    SharePointListItemEntity,
    SharePointPageEntity,
    SharePointSiteEntity,
    SharePointUserEntity,
)
from .sharepoint2019v2 import (
    SharePoint2019V2FileEntity,
    SharePoint2019V2ItemEntity,
    SharePoint2019V2ListEntity,
    SharePoint2019V2SiteEntity,
)
from .shopify import (
    ShopifyCollectionEntity,
    ShopifyCustomerEntity,
    ShopifyDiscountEntity,
    ShopifyDraftOrderEntity,
    ShopifyFileEntity,
    ShopifyFulfillmentEntity,
    ShopifyGiftCardEntity,
    ShopifyInventoryItemEntity,
    ShopifyInventoryLevelEntity,
    ShopifyLocationEntity,
    ShopifyMetaobjectEntity,
    ShopifyOrderEntity,
    ShopifyProductEntity,
    ShopifyProductVariantEntity,
    ShopifyThemeEntity,
)
from .slack import SlackMessageEntity
from .slite import SliteNoteEntity
from .stripe import (
    StripeBalanceEntity,
    StripeBalanceTransactionEntity,
    StripeChargeEntity,
    StripeCustomerEntity,
    StripeEventEntity,
    StripeInvoiceEntity,
    StripePaymentIntentEntity,
    StripePaymentMethodEntity,
    StripePayoutEntity,
    StripeRefundEntity,
    StripeSubscriptionEntity,
)
from .stub import (
    CodeStubFileEntity,
    LargeStubEntity,
    LargeStubFileEntity,
    MediumStubEntity,
    PdfStubFileEntity,
    PptxStubFileEntity,
    SmallStubEntity,
    SmallStubFileEntity,
    StubContainerEntity,
)
from .teams import (
    TeamsChannelEntity,
    TeamsChatEntity,
    TeamsMessageEntity,
    TeamsTeamEntity,
    TeamsUserEntity,
)
from .todoist import (
    TodoistCommentEntity,
    TodoistProjectEntity,
    TodoistSectionEntity,
    TodoistTaskEntity,
)
from .trello import (
    TrelloBoardEntity,
    TrelloCardEntity,
    TrelloChecklistEntity,
    TrelloListEntity,
    TrelloMemberEntity,
)
from .web import WebFileEntity
from .word import WordDocumentEntity
from .zendesk import (
    ZendeskAttachmentEntity,
    ZendeskCommentEntity,
    ZendeskOrganizationEntity,
    ZendeskTicketEntity,
    ZendeskUserEntity,
)
from .zoho_crm import (
    ZohoCRMAccountEntity,
    ZohoCRMContactEntity,
    ZohoCRMDealEntity,
    ZohoCRMInvoiceEntity,
    ZohoCRMLeadEntity,
    ZohoCRMProductEntity,
    ZohoCRMQuoteEntity,
    ZohoCRMSalesOrderEntity,
)

ENTITIES_BY_SOURCE: dict[str, list[type]] = {
    "apollo": [
        ApolloAccountEntity,
        ApolloContactEntity,
        ApolloEmailActivityEntity,
        ApolloSequenceEntity,
    ],
    "airtable": [
        AirtableAttachmentEntity,
        AirtableBaseEntity,
        AirtableCommentEntity,
        AirtableRecordEntity,
        AirtableTableEntity,
        AirtableUserEntity,
    ],
    "asana": [
        AsanaCommentEntity,
        AsanaFileEntity,
        AsanaProjectEntity,
        AsanaSectionEntity,
        AsanaTaskEntity,
        AsanaWorkspaceEntity,
    ],
    "attio": [
        AttioListEntity,
        AttioNoteEntity,
        AttioObjectEntity,
        AttioRecordEntity,
    ],
    "bitbucket": [
        BitbucketCodeFileEntity,
        BitbucketDirectoryEntity,
        BitbucketRepositoryEntity,
        BitbucketWorkspaceEntity,
    ],
    "box": [
        BoxCollaborationEntity,
        BoxCommentEntity,
        BoxFileEntity,
        BoxFolderEntity,
        BoxUserEntity,
    ],
    "clickup": [
        ClickUpCommentEntity,
        ClickUpFileEntity,
        ClickUpFolderEntity,
        ClickUpListEntity,
        ClickUpSpaceEntity,
        ClickUpSubtaskEntity,
        ClickUpTaskEntity,
        ClickUpWorkspaceEntity,
    ],
    "coda": [
        CodaDocEntity,
        CodaPageEntity,
        CodaRowEntity,
        CodaTableEntity,
    ],
    "confluence": [
        ConfluenceBlogPostEntity,
        ConfluenceCommentEntity,
        ConfluenceCustomContentEntity,
        ConfluenceDatabaseEntity,
        ConfluenceFolderEntity,
        ConfluenceLabelEntity,
        ConfluencePageEntity,
        ConfluenceSpaceEntity,
        ConfluenceTaskEntity,
        ConfluenceWhiteboardEntity,
    ],
    "ctti": [
        CTTIWebEntity,
    ],
    "document360": [
        Document360ArticleEntity,
        Document360CategoryEntity,
        Document360ProjectVersionEntity,
    ],
    "dropbox": [
        DropboxAccountEntity,
        DropboxFileEntity,
        DropboxFolderEntity,
    ],
    "file_stub": [
        DocxFileStubEntity,
        FileStubContainerEntity,
        PdfFileStubEntity,
        PptxFileStubEntity,
        ScannedPdfFileStubEntity,
    ],
    "fireflies": [
        FirefliesTranscriptEntity,
    ],
    "freshdesk": [
        FreshdeskCompanyEntity,
        FreshdeskContactEntity,
        FreshdeskConversationEntity,
        FreshdeskSolutionArticleEntity,
        FreshdeskTicketEntity,
    ],
    "github": [
        GitHubCodeFileEntity,
        GithubContentEntity,
        GitHubDirectoryEntity,
        GitHubFileDeletionEntity,
        GithubRepoEntity,
        GitHubRepositoryEntity,
    ],
    "gitlab": [
        GitLabCodeFileEntity,
        GitLabDirectoryEntity,
        GitLabIssueEntity,
        GitLabMergeRequestEntity,
        GitLabProjectEntity,
        GitLabUserEntity,
    ],
    "gmail": [
        GmailAttachmentEntity,
        GmailMessageDeletionEntity,
        GmailMessageEntity,
        GmailThreadEntity,
    ],
    "google_calendar": [
        GoogleCalendarCalendarEntity,
        GoogleCalendarEventEntity,
        GoogleCalendarFreeBusyEntity,
        GoogleCalendarListEntity,
    ],
    "google_docs": [
        GoogleDocsDocumentEntity,
    ],
    "google_drive": [
        GoogleDriveDriveEntity,
        GoogleDriveFileDeletionEntity,
        GoogleDriveFileEntity,
    ],
    "google_slides": [
        GoogleSlidesPresentationEntity,
        GoogleSlidesSlideEntity,
    ],
    "hubspot": [
        HubspotCompanyEntity,
        HubspotContactEntity,
        HubspotDealEntity,
        HubspotTicketEntity,
    ],
    "jira": [
        JiraIssueEntity,
        JiraProjectEntity,
        ZephyrTestCaseEntity,
        ZephyrTestCycleEntity,
        ZephyrTestPlanEntity,
    ],
    "linear": [
        LinearAttachmentEntity,
        LinearCommentEntity,
        LinearIssueEntity,
        LinearProjectEntity,
        LinearTeamEntity,
        LinearUserEntity,
    ],
    "monday": [
        MondayBoardEntity,
        MondayColumnEntity,
        MondayGroupEntity,
        MondayItemEntity,
        MondaySubitemEntity,
        MondayUpdateEntity,
    ],
    "notion": [
        NotionDatabaseEntity,
        NotionFileEntity,
        NotionPageEntity,
        NotionPropertyEntity,
    ],
    "onedrive": [
        OneDriveDriveEntity,
        OneDriveDriveItemEntity,
    ],
    "onenote": [
        OneNoteNotebookEntity,
        OneNotePageFileEntity,
        OneNoteSectionEntity,
        OneNoteSectionGroupEntity,
    ],
    "outlook_calendar": [
        OutlookCalendarAttachmentEntity,
        OutlookCalendarCalendarEntity,
        OutlookCalendarEventEntity,
    ],
    "outlook_mail": [
        OutlookAttachmentEntity,
        OutlookMailFolderDeletionEntity,
        OutlookMailFolderEntity,
        OutlookMessageDeletionEntity,
        OutlookMessageEntity,
    ],
    "pipedrive": [
        PipedriveActivityEntity,
        PipedriveDealEntity,
        PipedriveLeadEntity,
        PipedriveNoteEntity,
        PipedriveOrganizationEntity,
        PipedrivePersonEntity,
        PipedriveProductEntity,
    ],
    "salesforce": [
        SalesforceAccountEntity,
        SalesforceContactEntity,
        SalesforceOpportunityEntity,
    ],
    "sharepoint": [
        SharePointDriveEntity,
        SharePointDriveItemEntity,
        SharePointGroupEntity,
        SharePointListEntity,
        SharePointListItemEntity,
        SharePointPageEntity,
        SharePointSiteEntity,
        SharePointUserEntity,
    ],
    "sharepoint2019v2": [
        SharePoint2019V2FileEntity,
        SharePoint2019V2ItemEntity,
        SharePoint2019V2ListEntity,
        SharePoint2019V2SiteEntity,
    ],
    "slite": [
        SliteNoteEntity,
    ],
    "shopify": [
        ShopifyCollectionEntity,
        ShopifyCustomerEntity,
        ShopifyDiscountEntity,
        ShopifyDraftOrderEntity,
        ShopifyFileEntity,
        ShopifyFulfillmentEntity,
        ShopifyGiftCardEntity,
        ShopifyInventoryItemEntity,
        ShopifyInventoryLevelEntity,
        ShopifyLocationEntity,
        ShopifyMetaobjectEntity,
        ShopifyOrderEntity,
        ShopifyProductEntity,
        ShopifyProductVariantEntity,
        ShopifyThemeEntity,
    ],
    "slack": [
        SlackMessageEntity,
    ],
    "stripe": [
        StripeBalanceEntity,
        StripeBalanceTransactionEntity,
        StripeChargeEntity,
        StripeCustomerEntity,
        StripeEventEntity,
        StripeInvoiceEntity,
        StripePaymentIntentEntity,
        StripePaymentMethodEntity,
        StripePayoutEntity,
        StripeRefundEntity,
        StripeSubscriptionEntity,
    ],
    "stub": [
        CodeStubFileEntity,
        LargeStubEntity,
        LargeStubFileEntity,
        MediumStubEntity,
        PdfStubFileEntity,
        PptxStubFileEntity,
        SmallStubEntity,
        SmallStubFileEntity,
        StubContainerEntity,
    ],
    "teams": [
        TeamsChannelEntity,
        TeamsChatEntity,
        TeamsMessageEntity,
        TeamsTeamEntity,
        TeamsUserEntity,
    ],
    "todoist": [
        TodoistCommentEntity,
        TodoistProjectEntity,
        TodoistSectionEntity,
        TodoistTaskEntity,
    ],
    "trello": [
        TrelloBoardEntity,
        TrelloCardEntity,
        TrelloChecklistEntity,
        TrelloListEntity,
        TrelloMemberEntity,
    ],
    "web": [
        WebFileEntity,
    ],
    "word": [
        WordDocumentEntity,
    ],
    "servicenow": [
        ServiceNowCatalogItemEntity,
        ServiceNowChangeRequestEntity,
        ServiceNowIncidentEntity,
        ServiceNowKnowledgeArticleEntity,
        ServiceNowProblemEntity,
    ],
    "zendesk": [
        ZendeskAttachmentEntity,
        ZendeskCommentEntity,
        ZendeskOrganizationEntity,
        ZendeskTicketEntity,
        ZendeskUserEntity,
    ],
    "zoho_crm": [
        ZohoCRMAccountEntity,
        ZohoCRMContactEntity,
        ZohoCRMDealEntity,
        ZohoCRMInvoiceEntity,
        ZohoCRMLeadEntity,
        ZohoCRMProductEntity,
        ZohoCRMQuoteEntity,
        ZohoCRMSalesOrderEntity,
    ],
}
