import { ComponentType } from "react";


enum AuthType {
  OAUTH2 = "oauth2",
  OAUTH2_WITH_REFRESH = "oauth2_with_refresh",
  OAUTH2_WITH_REFRESH_ROTATING = "oauth2_with_refresh_rotating",
  TRELLO_AUTH = "trello_auth",
  API_KEY = "api_key",
  NATIVE_FUNCTIONALITY = "native_functionality",
  CONFIG_CLASS = "config_class",
  SIGV4 = "sigv4",
}
interface DataSource {
  id: string;
  name: string;
  description: string;
  short_name: string;
  auth_type?: AuthType;
  class_name: string;
  skipCredentials?: boolean;
}

export const dataSources: DataSource[] = [
  {
    id: "notion",
    name: "Notion",
    short_name: "notion",
    description: "Sync your Notion workspace",
    class_name: "NotionSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "slack",
    name: "Slack",
    short_name: "slack",
    description: "Sync your Slack messages",
    class_name: "SlackSource",
    auth_type: AuthType.OAUTH2,
  },
  {
    id: "google_drive",
    name: "Google Drive",
    short_name: "google_drive",
    description: "Sync your Google Drive files",
    class_name: "GoogleDriveSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "dropbox",
    name: "Dropbox",
    short_name: "dropbox",
    description: "Sync your Dropbox files",
    class_name: "DropboxSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "asana",
    name: "Asana",
    short_name: "asana",
    description: "Sync your Asana tasks and projects",
    class_name: "AsanaSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "calendly",
    name: "Calendly",
    short_name: "calendly",
    description: "Sync your Calendly meetings",
    class_name: "CalendlySource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "chatgpt",
    name: "ChatGPT",
    short_name: "chatgpt",
    description: "Sync your ChatGPT conversations",
    class_name: "ChatGPTSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "facebook",
    name: "Facebook",
    short_name: "facebook",
    description: "Sync your Facebook content",
    class_name: "FacebookSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "gmail",
    name: "Gmail",
    short_name: "gmail",
    description: "Sync your Gmail messages",
    class_name: "GmailSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH_ROTATING,
  },
  {
    id: "google-calendar",
    name: "Google Calendar",
    short_name: "google_calendar",
    description: "Sync your Google Calendar events",
    class_name: "GoogleCalendarSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "hubspot",
    name: "HubSpot",
    short_name: "hubspot",
    description: "Sync your HubSpot CRM data",
    class_name: "HubSpotSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "intercom",
    name: "Intercom",
    short_name: "intercom",
    description: "Sync your Intercom conversations",
    class_name: "IntercomSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "knowledge-bucket",
    name: "Knowledge Bucket",
    short_name: "knowledge_bucket",
    description: "Sync your Knowledge Bucket content",
    class_name: "KnowledgeBucketSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "linkedin",
    name: "LinkedIn",
    short_name: "linkedin",
    description: "Sync your LinkedIn content",
    class_name: "LinkedInSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "perplexity",
    name: "Perplexity",
    short_name: "perplexity",
    description: "Sync your Perplexity data",
    class_name: "PerplexitySource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "stripe",
    name: "Stripe",
    short_name: "stripe",
    description: "Sync your Stripe transactions",
    class_name: "StripeSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "todoist",
    name: "Todoist",
    short_name: "todoist",
    description: "Sync your Todoist tasks",
    class_name: "TodoistSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "trello",
    name: "Trello",
    short_name: "trello",
    description: "Sync your Trello boards",
    class_name: "TrelloSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "whatsapp",
    name: "WhatsApp",
    short_name: "whatsapp",
    description: "Sync your WhatsApp messages",
    class_name: "WhatsAppSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "whoppah-cms",
    name: "Whoppah CMS",
    short_name: "whoppah_cms",
    description: "Sync your Whoppah CMS content",
    class_name: "WhoppahCMSSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
  {
    id: "zendesk",
    name: "Zendesk",
    short_name: "zendesk",
    description: "Sync your Zendesk tickets",
    class_name: "ZendeskSource",
    auth_type: AuthType.OAUTH2_WITH_REFRESH,
  },
];
