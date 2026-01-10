import { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

export interface SubscriptionLimits {
  source_connections: number;
  entities_per_month: number;
  sync_frequency_minutes: number;
  team_members: number;
}

export interface SubscriptionInfo {
  plan: string;
  status: string;
  trial_ends_at?: string;
  current_period_start?: string;
  current_period_end?: string;
  cancel_at_period_end: boolean;
  payment_method_added?: boolean;
  has_yearly_prepay?: boolean;
  yearly_prepay_started_at?: string;
  yearly_prepay_expires_at?: string;
  limits: SubscriptionLimits;
  is_oss: boolean;
  has_active_subscription: boolean;
  grace_period_ends_at?: string;
  pending_plan_change?: string;
  pending_plan_change_at?: string;
}

export interface CheckoutSessionResponse {
  checkout_url: string;
}

export interface PortalSessionResponse {
  portal_url: string;
}

export interface BillingActionResponse {
  message: string;
}

/**
 * Fetch current subscription information
 */
export async function fetchSubscription(
  token: string
): Promise<SubscriptionInfo> {
  const response = await fetch(`${API_BASE_URL}/billing/subscription`, {
    method: "GET",
    headers: getAuthHeaders(token),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch subscription"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Create a Stripe checkout session for monthly billing
 */
export async function createCheckoutSession(
  token: string,
  plan: string,
  successUrl: string,
  cancelUrl: string
): Promise<CheckoutSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/billing/checkout-session`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify({
      plan,
      success_url: successUrl,
      cancel_url: cancelUrl,
    }),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to create checkout session"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Create a Stripe checkout session for yearly billing
 */
export async function createYearlyCheckoutSession(
  token: string,
  plan: string,
  successUrl: string,
  cancelUrl: string
): Promise<CheckoutSessionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/billing/yearly/checkout-session`,
    {
      method: "POST",
      headers: getAuthHeaders(token),
      body: JSON.stringify({
        plan,
        success_url: successUrl,
        cancel_url: cancelUrl,
      }),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to create yearly checkout session"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Create a Stripe billing portal session
 */
export async function createPortalSession(
  token: string,
  returnUrl: string
): Promise<PortalSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/billing/portal-session`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify({ return_url: returnUrl }),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to create portal session"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Update subscription plan
 */
export async function updatePlan(
  token: string,
  plan: string,
  period: "monthly" | "yearly"
): Promise<BillingActionResponse> {
  const response = await fetch(`${API_BASE_URL}/billing/update-plan`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify({ plan, period }),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(response, "Failed to update plan");
    throw new Error(message);
  }

  return response.json();
}

/**
 * Cancel subscription at end of period
 */
export async function cancelSubscription(
  token: string,
  immediate: boolean = false
): Promise<BillingActionResponse> {
  const response = await fetch(`${API_BASE_URL}/billing/cancel`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify({ immediate }),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to cancel subscription"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Reactivate a cancelled subscription
 */
export async function reactivateSubscription(
  token: string
): Promise<BillingActionResponse> {
  const response = await fetch(`${API_BASE_URL}/billing/reactivate`, {
    method: "POST",
    headers: getAuthHeaders(token),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to reactivate subscription"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Cancel a pending plan change
 */
export async function cancelPlanChange(
  token: string
): Promise<BillingActionResponse> {
  const response = await fetch(`${API_BASE_URL}/billing/cancel-plan-change`, {
    method: "POST",
    headers: getAuthHeaders(token),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to cancel plan change"
    );
    throw new Error(message);
  }

  return response.json();
}
