import type { ConfigField, DirectAuthentication, Source } from '@/shared/api';

export type SourceConnectionAuthMethod =
  | 'direct'
  | 'oauth_browser'
  | 'oauth_token'
  | 'auth_provider';

export interface SourceConnectionFormValues {
  authMethod: SourceConnectionAuthMethod;
  authentication: SourceConnectionAuthenticationFormValue;
  config: Record<string, unknown>;
  name: string;
}

export interface SourceConnectionAuthenticationFormValue {
  client_id?: string;
  client_secret?: string;
  consumer_key?: string;
  consumer_secret?: string;
  credentials?: Record<string, unknown>;
  expires_at?: string;
  provider_config?: Record<string, unknown>;
  provider_readable_id?: string;
  redirect_uri?: string;
  refresh_token?: string;
  access_token?: string;
}

export interface SourceConnectionFormErrors {
  authentication: Record<string, string>;
  config: Record<string, string>;
  form?: string;
}

export interface SourceFieldGroupProps {
  errors?: Record<string, string>;
  fields: Array<ConfigField>;
  onChange: (fieldName: string, value: unknown) => void;
  values: Record<string, unknown>;
}

export interface SourceConnectionAuthSectionProps {
  authFields: Array<ConfigField>;
  errors?: Record<string, string>;
  onChange: (fieldName: string, value: unknown) => void;
  source: Source;
  values: Record<string, unknown>;
}

export type DirectAuthenticationPayload = DirectAuthentication;
