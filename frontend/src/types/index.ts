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

interface DataSourceCardProps {
  shortName: string;
  name: string;
  description: string;
  status: "connected" | "disconnected";
  onConnect?: () => void;
  onSelect?: () => void;
  existingConnections?: Connection[];
}
