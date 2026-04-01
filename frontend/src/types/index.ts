// Single action check response for billing/usage checks
export interface SingleActionCheckResponse {
  allowed: boolean;
  action: string;
  reason?: 'payment_required' | 'usage_limit_exceeded' | null;
  details?: {
    message: string;
    current_usage?: number;
    limit?: number;
    payment_status?: string;
    upgrade_url?: string;
  } | null;
}

// Billing information for organization subscription
export interface BillingInfo {
  plan: string;
  status: string;
  trial_ends_at?: string;
  grace_period_ends_at?: string;
  current_period_end?: string;
  cancel_at_period_end: boolean;
  limits: Record<string, any>;
  is_oss: boolean;
  has_active_subscription: boolean;
  in_trial: boolean;
  in_grace_period: boolean;
  payment_method_added: boolean;
  requires_payment_method: boolean;
}

export interface Connection {
  id: string;
  name: string;
  organization_id: string;
  created_by_email: string;
  modified_by_email: string;
  status: "active" | "inactive" | "error";
  integration_type: string;
  integration_credential_id: string;
  source_id: string;
  short_name: string;
  modified_at: string;
  lastSync?: string;
  syncCount?: number;
  documentsCount?: number;
  healthScore?: number;
  createdAt: string;
}

// Source connection types — shared across collection components
export interface SourceConnectionAuth {
  method?: string;
  authenticated?: boolean;
  authenticated_at?: string;
  expires_at?: string;
  auth_url?: string;
  auth_url_expires?: string;
  provider_id?: string;
  provider_readable_id?: string;
  redirect_url?: string;
}

export interface SourceConnectionLastSyncJob {
  id?: string;
  status?: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  entities_inserted?: number;
  entities_updated?: number;
  entities_deleted?: number;
  entities_failed?: number;
  error?: string;
  error_details?: Record<string, any>;
}

export interface SourceConnectionSchedule {
  cron?: string;
  next_run?: string;
  continuous?: boolean;
  cursor_field?: string;
  cursor_value?: any;
}

export interface SourceConnectionEntitySummary {
  total_entities: number;
  by_type: Record<string, { count: number; last_updated?: string; sync_status: string }>;
  last_updated?: string;
}

export type ErrorCategory =
  | 'oauth_credentials_expired'
  | 'api_key_invalid'
  | 'auth_provider_account_gone'
  | 'auth_provider_credentials_invalid';

export interface SourceConnection {
  id: string;
  name: string;
  description?: string;
  short_name: string;
  readable_collection_id?: string;
  status?: string;
  created_at?: string;
  modified_at?: string;
  auth?: SourceConnectionAuth;
  config?: Record<string, any>;
  schedule?: SourceConnectionSchedule;
  last_sync_job?: SourceConnectionLastSyncJob;
  entities?: SourceConnectionEntitySummary;
  // Credential error info
  error_category?: ErrorCategory;
  error_message?: string;
  provider_settings_url?: string;
  provider_short_name?: string;
  // Source configuration
  federated_search?: boolean;
  // Sync details
  sync?: Record<string, any>;
  sync_id?: string;
  organization_id?: string;
  connection_id?: string;
  created_by_email?: string;
  modified_by_email?: string;
}

// User session types for session management
export interface UserSession {
  id: string;
  ip_address?: string;
  user_agent?: string;
  created_at: string;
  last_active_at?: string;
  is_current: boolean;
}

export interface SessionTerminationResult {
  terminated_count: number;
  terminated_at: string;
}

interface DataSourceCardProps {
  shortName: string;
  name: string;
  description: string;
  status: "connected" | "disconnected";
  onConnect?: () => void;
  onSelect?: () => void;
  existingConnections?: Connection[];
}
