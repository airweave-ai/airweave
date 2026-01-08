# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- **Billing Settings Page - COMPLETE**
  - Created `/$orgSlug/settings/billing.tsx` with full subscription management
  - Plan cards: Developer (free), Pro ($20/mo), Team ($299/mo), Enterprise (custom)
  - Monthly/Yearly toggle with 20% yearly discount
  - Status badges: Active, Trial, Past Due, Canceled, Trial Expired
  - Upgrade/Downgrade/Switch buttons, Cancel/Reactivate subscription
  - Created `lib/api/billing.ts` with API functions
  - Added Billing tab to settings-layout navigation
  - Build verified passing

## Next Suggested Tasks (in priority order)

1. **Port `/billing/setup` Route (MEDIUM)**
   - Initial billing setup page shown during onboarding
   - Similar to old `frontend/src/pages/BillingSetup.tsx`
   - Should check billing status and redirect to Stripe checkout if needed

2. **Port `/billing/portal` Route (MEDIUM)**
   - Simple redirect page to Stripe Customer Portal
   - Reference: `frontend/src/pages/BillingPortal.tsx`

3. **Polish Phase 7 (LOW)**
   - Port TagInput component
   - Port CollapsibleCard component
   - Enhance CodeBlock component

## Blocked Tasks

- **Edit Member Roles** - Requires backend `PATCH /organizations/{id}/members/{memberId}` endpoint

## Key Files Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- Billing API: `frontend-v2/src/lib/api/billing.ts`
- Billing Settings Page: `frontend-v2/src/routes/$orgSlug/settings/billing.tsx`
- Settings Layout: `frontend-v2/src/components/settings-layout.tsx`
- Validation system: `frontend-v2/src/lib/validation/`
- Date utilities: `frontend-v2/src/lib/date.ts`

## How to Use the Billing API

```typescript
import {
  fetchSubscription,
  createCheckoutSession,
  createPortalSession,
  updatePlan,
  cancelSubscription,
  reactivateSubscription,
} from "@/lib/api";

// Fetch current subscription
const subscription = await fetchSubscription(token);

// Create checkout session for new subscription
const { checkout_url } = await createCheckoutSession(
  token,
  "pro", // plan
  successUrl,
  cancelUrl
);

// Open Stripe billing portal
const { portal_url } = await createPortalSession(token, returnUrl);

// Update plan (upgrade/downgrade)
await updatePlan(token, "team", "yearly");

// Cancel subscription at period end
await cancelSubscription(token, false);
```

## How to Use the Validation System

```typescript
// Option 1: ValidatedInput with built-in validation display
import { ValidatedInput } from "@/components/validated-input";
import { collectionNameValidation } from "@/lib/validation";

function MyForm() {
  const [name, setName] = useState("");

  return (
    <ValidatedInput
      value={name}
      onChange={setName}
      validation={collectionNameValidation}
      placeholder="Enter collection name"
    />
  );
}

// Option 2: With TanStack Form using createFormValidator
import { createFormValidator, collectionNameValidation } from "@/lib/validation";
import { ValidatedInput } from "@/components/validated-input";

function MyTanStackForm() {
  return (
    <form.Field
      name="name"
      validators={{ onChange: createFormValidator(collectionNameValidation) }}
    >
      {(field) => (
        <ValidatedInput
          value={field.state.value}
          onChange={field.handleChange}
          onBlur={field.handleBlur}
          validation={collectionNameValidation}
        />
      )}
    </form.Field>
  );
}
```
