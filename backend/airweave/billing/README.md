# Billing System Architecture

## Overview

This is a refactored billing system for Airweave that provides clean separation of concerns and modular, maintainable code. The key improvements over the previous implementation are:

1. **Pure Business Logic** - All business rules are isolated in `plan_logic.py` as pure functions
2. **Repository Pattern** - Database operations are cleanly abstracted in `billing_data_access.py`
3. **Simplified Webhook Processing** - Clear event handling without complex conditionals
4. **Clean API Layer** - API endpoints focus only on HTTP concerns

## Module Structure

```
platform/billing/
├── __init__.py              # Module exports
├── plan_logic.py            # Pure business logic and rules
├── billing_data_access.py   # Database operations (repository pattern)
├── billing_service.py       # Main orchestrator service
├── webhook_handler.py       # Stripe webhook processing
└── README.md                # This file

api/v1/endpoints/
└── billing.py               # API endpoints

integrations/
└── stripe_client.py         # Stripe API wrapper
```

## File Descriptions

### `plan_logic.py`
Pure functions for billing business rules:
- Plan comparison and ranking
- Plan change analysis
- Webhook plan inference
- Billing period transitions
- Usage limits configuration

Key functions:
- `analyze_plan_change()` - Determines if a plan change is allowed
- `infer_plan_from_webhook()` - Infers plan from Stripe events
- `compare_plans()` - Compares two plans (upgrade/downgrade/same)

### `billing_data_access.py`
Repository pattern for database operations:
- CRUD operations for billing records
- Billing period management
- Usage tracking
- Clean interface to the database layer

Key class:
- `BillingRepository` - All database operations

### `billing_service.py`
Main orchestrator that coordinates between components:
- Subscription lifecycle management
- Checkout session creation
- Plan updates and cancellations
- Customer portal sessions

Key class:
- `BillingService` - Main service orchestrator

### `webhook_handler.py`
Processes incoming Stripe webhook events:
- Subscription lifecycle events
- Payment success/failure
- Invoice events

Key class:
- `BillingWebhookProcessor` - Event processing

### `billing.py` (API endpoints)
HTTP endpoints for billing operations:
- `/checkout-session` - Create checkout
- `/portal-session` - Customer portal
- `/subscription` - Get subscription info
- `/update-plan` - Change plans
- `/cancel` - Cancel subscription
- `/webhook` - Stripe webhook handler

### `stripe_client.py`
Stripe API wrapper:
- Customer management
- Subscription operations
- Checkout sessions
- Portal sessions
- Webhook signature verification

## Integration Points

### With Frontend
The frontend interacts with billing through the API endpoints:
```typescript
// Example: Create checkout session
const response = await api.post('/billing/checkout-session', {
  plan: 'pro',
  success_url: 'https://app.airweave.ai/success',
  cancel_url: 'https://app.airweave.ai/cancel'
});
```

### With Organization Creation
When creating an organization, a billing record is initialized:
```python
from airweave.platform.billing import billing_service

billing = await billing_service.create_billing_record(
    db=db,
    organization=org,
    stripe_customer_id=customer.id,
    billing_email=user.email,
    ctx=ctx,
    uow=uow,
)
```

### With Usage Tracking
The guard rail service checks billing limits:
```python
subscription = await billing_service.get_subscription_info(db, org_id)
limits = subscription.usage_limits
```

## Configuration

Required environment variables:
- `STRIPE_ENABLED` - Enable/disable billing
- `STRIPE_SECRET_KEY` - Stripe API key
- `STRIPE_WEBHOOK_SECRET` - Webhook signature secret
- `STRIPE_DEVELOPER_MONTHLY` - Price ID for developer plan
- `STRIPE_PRO_MONTHLY` - Price ID for pro plan
- `STRIPE_TEAM_MONTHLY` - Price ID for team plan

## Testing

Test the billing system using the E2E script:
```bash
cd backend
python scripts/stripe_billing_e2e.py
```

This tests:
- Customer creation
- Checkout session
- Subscription updates
- Plan changes
- Cancellation flows

## Key Design Decisions

### 1. Pure Business Logic
All business rules are in `plan_logic.py` as pure functions with no side effects. This makes the logic easy to test and reason about.

### 2. Repository Pattern
Database operations are abstracted through `BillingRepository`, providing a clean interface that can be easily mocked for testing.

### 3. Service Orchestration
`BillingService` coordinates between the repository, Stripe client, and business logic without containing business rules itself.

### 4. Webhook Simplification
Webhook processing is split into clear, focused handlers instead of monolithic functions with complex conditionals.

### 5. Type Safety
Extensive use of dataclasses and enums for type safety and clarity:
- `PlanChangeContext` / `PlanChangeDecision`
- `PlanInferenceContext` / `InferredPlan`
- `ChangeType` / `PlanRank` enums

## Migration from Old System

The new system replaces:
- `core/billing_service.py` → `platform/billing/` (split into multiple files)
- `core/stripe_webhook_handler.py` → `platform/billing/webhook_handler.py`
- `api/v1/endpoints/billing.py` → unchanged location, updated imports
- `integrations/stripe_client.py` → unchanged location, simplified

Import changes:
```python
# Old
from airweave.core.billing_service import billing_service
from airweave.integrations.stripe_client import stripe_client

# New
from airweave.platform.billing import billing_service
from airweave.integrations.stripe_client import stripe_client
```

## Future Enhancements

1. **More Billing Providers** - Abstract Stripe-specific logic to support other providers
2. **Usage-Based Billing** - Add metered billing support
3. **Team Billing** - Support for team seats and per-seat pricing
4. **Invoice Management** - Direct invoice generation and management
5. **Billing Analytics** - Revenue tracking and reporting
