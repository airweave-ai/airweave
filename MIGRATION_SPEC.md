# Frontend Migration Specification: frontend → frontend-v2

This document provides a comprehensive specification for migrating from the old `frontend` to the new `frontend-v2`. It covers every page, feature, component, and use case that needs to be migrated to ensure feature parity.

## 1. Key Decisions

These decisions were made during migration planning and should guide all implementation work.

### Architecture Decisions

| Decision | Choice | Rationale |
|-|--|--|
| **Router** | Keep TanStack Router | Modern file-based routing, better DX |
| **Form Library** | TanStack Form with Form / Code switcher | Consistent with v2 patterns |
| **Color Theme** | Keep Orange/Amber | New brand direction for v2 |
| **URL Structure** | New URLs OK | `/$orgSlug` prefix is acceptable |

### Feature Decisions

| Feature | Decision | Notes |
||-|-|
| **Dashboard Page** | Keep redirect | No dedicated dashboard - redirect to collections |
| **DAG Visualization** | Simplify | Create simpler sync status view, not full DAG |
| **Connection Animations** | Skip entirely | Use default Tailwind animations only |
| **Logs/Webhooks** | Keep skeleton | Leave as placeholders for now |
| **Admin Dashboard** | Include now | Needed for org management |
| **SemanticMcp Page** | Include | MCP auth as alternative to OAuth |
| **S3 Event Streaming** | Include | Feature-flagged, used by paying customers |
| **QueryTool** | Port full version | Include live API documentation |

### Technical Decisions

| Area | Decision | Implementation |
||-|-|
| **Validation System** | Full migration | Port all 40+ validation rules from old frontend |
| **Real-time Sync** | Full port | SSE with entityStateMediator, syncStorageService |
| **Billing Enforcement** | Strict blocking | Block UI actions when subscription inactive |
| **Team Management** | Full CRUD | Invite, view, edit roles, remove members |
| **Auth Methods** | All methods | OAuth2, Direct Auth, External Provider, Config Auth |
| **PostHog Analytics** | Port it | Include session tracking |
| **Session Header** | Add it | Include `X-Airweave-Session-ID` in API calls |
| **Org Settings** | Dedicated page | Full page at `/$orgSlug/settings` |



## 2. Executive Summary

### Current State

| Aspect | Frontend (Old) | Frontend-v2 (New) |
|--|-|-|
| **React Version** | 18.3.1 | 19.2.0 |
| **Router** | React Router v6 | TanStack Router v1 (file-based) |
| **State Management** | Zustand (10 stores) | Zustand (4 stores) + React Query |
| **Form Library** | React Hook Form | TanStack Form |
| **Data Fetching** | Manual fetch + stores | React Query |
| **Caching** | localStorage only | IndexedDB + SWR |
| **Tailwind** | v3.x (HSL colors) | v4.x (OKLch colors) |
| **Auth** | Auth0 + custom provider | Auth0 + unified context |
| **Primary Color** | Blue (#1692E5) | Orange/Amber (keeping v2) |

### Migration Status Overview

| Feature | Status | Priority | Notes |
||--|-|-|
| Collections CRUD | ✅ Complete | - | Full feature parity |
| Collection Detail + Search | ✅ Complete | - | Enhanced with streaming |
| API Keys Management | ✅ Complete | - | Full feature parity |
| Auth Providers | ✅ Complete | - | Full feature parity |
| Onboarding | ✅ Complete | - | 6-step wizard |
| Source Connections | ✅ Complete | - | Full sync management |
| Dashboard | ✅ Complete | - | **Decision: Keep redirect to collections** |
| Organization Settings | ❌ Missing | **High** | Dedicated page needed |
| Billing Pages | ❌ Missing | **High** | Strict blocking enforcement |
| Admin Dashboard | ❌ Missing | **High** | Include now per decision |
| Real-time Sync | ❌ Missing | **High** | Full SSE port required |
| Usage Dashboard | ❌ Missing | **High** | Part of settings |
| Members Settings | ❌ Missing | **High** | Full CRUD |
| Validation System | ❌ Missing | **High** | Full 40+ rules migration |
| QueryTool | ⚠️ Different | **Medium** | Port full version with API doc |
| SemanticMcp Page | ❌ Missing | **Medium** | MCP auth alternative |
| S3 Configuration | ❌ Missing | **Medium** | Feature-flagged |
| PostHog Integration | ❌ Missing | **Medium** | Add session tracking |
| Logs | ⚠️ Skeleton | **Low** | Keep skeleton per decision |
| Webhooks | ⚠️ Skeleton | **Low** | Keep skeleton per decision |
| DAG Visualization | ❌ Not needed | **Skip** | Simplify to basic status view |
| Connection Animations | ❌ Not needed | **Skip** | Use Tailwind defaults |



## 3. Routes & Pages

### Old Frontend Routes

| Route | Component | Status in v2 | Priority |
|-|--|--|-|
| `/login` | `Login` | ✅ Handled by Auth0 | - |
| `/callback` | `Callback` | ✅ Complete | - |
| `/auth/callback` | `AuthCallback` | ✅ Complete | - |
| `/onboarding` | `Onboarding` | ✅ Complete | - |
| `/billing/success` | `BillingSuccess` | ❌ Missing | **High** |
| `/billing/cancel` | `BillingCancel` | ❌ Missing | **High** |
| `/semantic-mcp` | `SemanticMcp` | ❌ Missing | **Medium** |
| `/` (dashboard) | `Dashboard` | ✅ Redirect OK | - |
| `/collections` | `CollectionsView` | ✅ Complete | - |
| `/collections/:readable_id` | `CollectionDetailView` | ✅ Complete | - |
| `/api-keys` | N/A (inline) | ✅ Complete | - |
| `/auth-providers` | `AuthProviders` | ✅ Complete | - |
| `/organization/settings` | `OrganizationSettingsUnified` | ❌ Missing | **High** |
| `/billing/setup` | `BillingSetup` | ❌ Missing | **High** |
| `/billing/portal` | `BillingPortal` | ❌ Missing | **High** |
| `/admin` | `AdminDashboard` | ❌ Missing | **High** |
| `*` (404) | `NotFound` | ✅ Complete | - |

### Frontend-v2 Routes (Implemented)

```
/                           → Root redirect to primary org
/onboarding                 → Organization setup wizard
/$orgSlug/                  → Org base (redirects to collections)
/$orgSlug/collections       → Collections list
/$orgSlug/collections/$id   → Collection detail with search
/$orgSlug/api-keys          → API key management
/$orgSlug/auth-providers    → OAuth provider configuration
/$orgSlug/logs              → Sync logs (skeleton - keep as-is)
/$orgSlug/webhooks          → Webhooks (skeleton - keep as-is)
/components                 → Component showcase
```

### Routes to Implement

```
/$orgSlug/settings              → Organization settings (name, desc, S3, delete)
/$orgSlug/settings/billing      → Billing management
/$orgSlug/settings/members      → Team member management (full CRUD)
/$orgSlug/settings/usage        → Usage dashboard
/billing/success                → Billing success callback
/billing/cancel                 → Billing cancel callback
/semantic-mcp                   → Semantic MCP page (MCP auth)
/admin                          → Admin dashboard (superuser only)
```



## 4. Features & Functionality

### 4.1 Collections Feature

#### Status: ✅ Complete (with enhancements needed)

| Feature | Old Frontend | Frontend-v2 | Action |
||-|-|--|
| List collections | ✅ | ✅ | Done |
| Create collection | ✅ | ✅ | Done |
| Delete collection | ✅ | ✅ | Done |
| Source connections | ✅ | ✅ | Done |
| Sync management | ✅ | ✅ | Done |
| Entity statistics | ✅ | ✅ | Done |
| Streaming search | ✅ | ✅ | Done |
| QueryTool with API doc | ✅ | ⚠️ | **Port full QueryTool** |
| DAG visualization | ✅ | ❌ | **Skip - simplify to status view** |
| Real-time entity updates | ✅ | ❌ | **Port SSE system** |

### 4.2 Search Feature

#### Status: ✅ Mostly Complete

| Feature | Old Frontend | Frontend-v2 | Action |
||-|-|--|
| Search with streaming | ✅ | ✅ | Done |
| JSON filter editor | ✅ | ✅ | Done |
| Search toggles | ✅ | ✅ | Done |
| Recency bias | ❌ | ✅ | Done (v2 only) |
| Search trace | ❌ | ✅ | Done (v2 only) |
| Usage limit checking | ✅ | ❌ | **Add to v2** |
| API key validation | ✅ | ❌ | **Add to v2** |

### 4.3 Organization Settings Feature

#### Status: ❌ Missing - **HIGH PRIORITY**

Must implement as dedicated page at `/$orgSlug/settings`:

| Feature | Required | Notes |
||-|-|
| Organization name editing | ✅ Yes | |
| Organization description | ✅ Yes | |
| Primary organization toggle | ✅ Yes | |
| S3 event streaming config | ✅ Yes | Feature-flagged |
| Organization deletion | ✅ Yes | With confirmation |

### 4.4 Billing Feature

#### Status: ❌ Missing - **HIGH PRIORITY**

**Decision: Strict blocking enforcement**

| Feature | Required | Notes |
||-|-|
| BillingSetup page | ✅ Yes | |
| BillingPortal page | ✅ Yes | |
| BillingSuccess callback | ✅ Yes | |
| BillingCancel callback | ✅ Yes | |
| BillingGuard component | ✅ Yes | Block actions when inactive |
| Usage limits enforcement | ✅ Yes | Strict blocking in UI |
| Grace period handling | ✅ Yes | |

### 4.5 Members Settings Feature

#### Status: ❌ Missing - **HIGH PRIORITY**

**Decision: Full CRUD capabilities**

| Feature | Required | Notes |
||-|-|
| View members list | ✅ Yes | |
| Invite new members | ✅ Yes | With email + role |
| Edit member roles | ✅ Yes | |
| Remove members | ✅ Yes | With confirmation |
| View pending invitations | ✅ Yes | |
| Cancel invitations | ✅ Yes | |

### 4.6 Admin Feature

#### Status: ❌ Missing - **HIGH PRIORITY** (per decision)

| Feature | Required | Notes |
||-|-|
| AdminDashboard | ✅ Yes | |
| Organization listing | ✅ Yes | With metrics |
| Feature flag management | ✅ Yes | |
| Plan upgrades | ✅ Yes | |
| User/source/entity counts | ✅ Yes | |
| Superuser access control | ✅ Yes | |

### 4.7 Real-time Features

#### Status: ❌ Missing - **HIGH PRIORITY**

**Decision: Full port of SSE sync system**

| Feature | Required | Notes |
||-|-|
| SSE sync progress | ✅ Yes | Full entityStateMediator |
| Entity state real-time | ✅ Yes | |
| Sync status subscriptions | ✅ Yes | syncStateStore |
| Health check for stale | ✅ Yes | |
| Session storage recovery | ✅ Yes | syncStorageService |

### 4.8 SemanticMcp Feature

#### Status: ❌ Missing - **MEDIUM PRIORITY**

**Decision: Include - MCP auth as alternative to OAuth**

This page provides an alternative authentication method using MCP (Model Context Protocol) instead of traditional OAuth flows.

### 4.9 Features NOT to Migrate

**Per decisions:**

| Feature | Decision | Reason |
||-|--|
| Dedicated Dashboard page | Skip | Keep redirect to collections |
| DAG visualization | Skip | Simplify to basic sync status |
| Connection animations CSS | Skip | Use Tailwind defaults |
| Logs implementation | Defer | Keep skeleton |
| Webhooks implementation | Defer | Keep skeleton |



## 5. Components Inventory

### 5.1 UI Components (Old Frontend → v2)

| Component | Old Frontend | Frontend-v2 | Action |
|--|-|-|--|
| Button | ✅ | ✅ | Done |
| Card | ✅ | ✅ | Done |
| Badge | ✅ | ✅ | Done |
| Input | ✅ | ✅ | Done |
| Select | ✅ | ✅ | Done |
| Dialog | ✅ | ✅ | Done |
| AlertDialog | ✅ | ✅ | Done |
| Tabs | ✅ | ✅ | Done |
| Tooltip | ✅ | ✅ | Done |
| DropdownMenu | ✅ | ✅ | Done |
| Sheet | ✅ | ✅ | Done |
| Toast/Sonner | ✅ | ✅ | Done |
| Table | ✅ | ✅ | Done |
| Progress | ✅ | ✅ | Done |
| Skeleton | ✅ | ✅ | Done |
| Form | ✅ (RHF) | ✅ (TanStack) | Use TanStack Form |
| ValidatedInput | ✅ | ❌ | **Port** |
| TagInput | ✅ | ❌ | **Port** |
| CodeBlock | ✅ | ⚠️ | **Enhance** |
| CollapsibleCard | ✅ | ❌ | **Port** |

### 5.2 Feature Components to Migrate

| Component | Status | Priority | Notes |
|--|--|-|-|
| QueryTool | ⚠️ | **High** | Port full version with API doc |
| LiveApiDoc | ❌ | **High** | Part of QueryTool |
| BillingGuard | ❌ | **High** | Strict blocking |
| OrganizationSettings | ❌ | **High** | Dedicated page |
| MembersSettings | ❌ | **High** | Full CRUD |
| UsageDashboard | ❌ | **High** | Settings sub-page |
| AdminDashboard | ❌ | **High** | Per decision |
| S3ConfigModal | ❌ | **Medium** | Feature-flagged |
| S3StatusCard | ❌ | **Medium** | Feature-flagged |
| SyncDagCard | ❌ | **Skip** | Simplify instead |
| DagToFlow | ❌ | **Skip** | Simplify instead |



## 6. API Integration

### 6.1 API Client Updates Required

**Decision: Add `X-Airweave-Session-ID` header**

Update `frontend-v2/src/lib/api/client.ts`:

```typescript
export function getAuthHeaders(
  token: string,
  organizationId?: string
): HeadersInit {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...(organizationId && { "X-Organization-ID": organizationId }),
    // ADD THIS:
    ...(getPostHogSessionId() && { "X-Airweave-Session-ID": getPostHogSessionId() }),
  };
}
```

### 6.2 Missing API Functions to Implement

```typescript
// Usage (HIGH PRIORITY - for billing enforcement)
fetchUsageDashboard(token, orgId)
checkUsageAction(token, orgId, action)

// Organization Members (HIGH PRIORITY - full CRUD)
fetchOrganizationMembers(token, orgId)
fetchOrganizationInvitations(token, orgId)
inviteOrganizationMember(token, orgId, email, role)
removeOrganizationMember(token, orgId, memberId)
cancelInvitation(token, orgId, invitationId)

// Billing (HIGH PRIORITY)
createCheckoutSession(token, orgId, plan)
createBillingPortalSession(token, orgId)

// S3 (MEDIUM PRIORITY)
fetchS3Status(token, orgId)
configureS3(token, orgId, config)
deleteS3Config(token, orgId)

// Filter Schema
fetchFilterSchema(token, orgId)

// Admin (HIGH PRIORITY)
fetchAllOrganizations(token)  // Admin only
updateOrganizationFeatures(token, orgId, features)  // Admin only
```



## 7. State Management

### 7.1 Stores to Add

**Decision: Full port of real-time sync system**

| Store | Purpose | Priority |
|-||-|
| `usage-store` | Usage limits, action checks | **High** |
| `entity-state-store` | Entity sync state persistence | **High** |
| `sync-state-store` | Real-time SSE subscriptions | **High** |

### 7.2 Services to Port

| Service | Purpose | Priority |
|||-|
| `entityStateMediator` | Real-time entity sync | **High** |
| `syncStorageService` | Session storage for sync recovery | **High** |



## 8. Authentication

### 8.1 Auth Methods Required

**Decision: All auth methods needed**

| Method | Status | Notes |
|--|--|-|
| OAuth2 | ✅ | Working in v2 |
| Direct Auth | ✅ | Working in v2 |
| External Provider | ⚠️ | Verify working |
| Config Auth | ⚠️ | Verify working |

### 8.2 Auth Features to Port

| Feature | Priority | Notes |
||-|-|
| Auth0 conflict error UI | Medium | Detailed error handling |
| Request queuing | Low | Until auth ready |



## 9. Services & Utilities

### 9.1 Validation System

**Decision: Full migration of all 40+ rules**

Port these files:
- `frontend/src/lib/validation/types.ts`
- `frontend/src/lib/validation/rules.ts`

Create ValidatedInput component wrapper for TanStack Form.

### 9.2 Utilities to Port

| Utility | Priority | Notes |
||-|-|
| `dateTime.ts` | Medium | UTC handling |
| `cronParser.ts` | Medium | Schedule display |
| `error-utils.ts` | Medium | Error handling |
| `syncStatus.ts` | High | For real-time features |

### 9.3 PostHog Integration

**Decision: Port PostHog analytics**

- Add PostHog provider
- Implement session ID tracking
- Add `X-Airweave-Session-ID` header to API calls



## 10. Styling & Theming

### 10.1 Key Decision: Keep Orange/Amber Theme

The frontend-v2 uses a new Orange/Amber primary color. This is intentional and should be kept.

### 10.2 CSS NOT to Migrate

**Per decision:**

| File | Decision |
||-|
| `connection-animation.css` | **Skip** - Use Tailwind defaults |
| `sync-progress.css` | **Skip** - Simplify animations |



## 11. Migration Checklist

### Phase 1: Billing & Settings (HIGH PRIORITY)

**These features block user workflows and must be implemented first.**

- [ ] **Billing Enforcement**
  - [ ] Create BillingGuard component
  - [ ] Add usage check API functions
  - [ ] Implement strict blocking throughout app
  - [ ] Create `/billing/success` route
  - [ ] Create `/billing/cancel` route

- [ ] **Organization Settings Page**
  - [ ] Create `/$orgSlug/settings/index.tsx`
  - [ ] Organization name/description editing
  - [ ] Organization deletion with confirmation
  - [ ] S3ConfigModal (feature-flagged)
  - [ ] S3StatusCard (feature-flagged)

- [ ] **Members Settings**
  - [ ] Create `/$orgSlug/settings/members.tsx`
  - [ ] View members list
  - [ ] Invite members (email + role)
  - [ ] Edit member roles
  - [ ] Remove members
  - [ ] View/cancel pending invitations

- [ ] **Usage Dashboard**
  - [ ] Create `/$orgSlug/settings/usage.tsx`
  - [ ] Port UsageDashboard component
  - [ ] Add usage API functions

### Phase 2: Real-time Sync (HIGH PRIORITY)

- [ ] **Port Sync Services**
  - [ ] Port `entityStateMediator.ts`
  - [ ] Port `syncStorageService.ts`
  - [ ] Create `entity-state-store`
  - [ ] Create `sync-state-store`

- [ ] **SSE Integration**
  - [ ] Add SSE sync progress subscription
  - [ ] Health check for stale subscriptions
  - [ ] Session storage recovery

### Phase 3: Admin Dashboard (HIGH PRIORITY)

- [ ] Create `/admin` route
- [ ] Port AdminDashboard component
- [ ] Organization listing with metrics
- [ ] Feature flag management
- [ ] Plan upgrades
- [ ] Superuser access control

### Phase 4: Validation System (HIGH PRIORITY)

- [ ] Port `lib/validation/types.ts`
- [ ] Port `lib/validation/rules.ts` (40+ rules)
- [ ] Create ValidatedInput for TanStack Form
- [ ] Integrate validation in all forms

### Phase 5: QueryTool Enhancement (MEDIUM)

- [ ] Port full QueryTool component
- [ ] Port LiveApiDoc component
- [ ] Add usage limit checking
- [ ] Add API key validation

### Phase 6: Additional Features (MEDIUM)

- [ ] **SemanticMcp Page**
  - [ ] Create `/semantic-mcp` route
  - [ ] Implement MCP authentication flow

- [ ] **PostHog Integration**
  - [ ] Add PostHog provider
  - [ ] Implement session ID tracking
  - [ ] Add `X-Airweave-Session-ID` to API headers

- [ ] **Utilities**
  - [ ] Port `dateTime.ts`
  - [ ] Port `cronParser.ts`
  - [ ] Port `error-utils.ts`

### Phase 7: Polish (LOW)

- [ ] Port TagInput component
- [ ] Port CollapsibleCard component
- [ ] Enhance CodeBlock component
- [ ] Auth0 conflict error handling UI



## Appendix A: API Endpoints Reference

### Endpoints Used in Old Frontend

```
# Collections
GET    /collections
POST   /collections
GET    /collections/{id}
DELETE /collections/{id}
GET    /collections/count
POST   /collections/{id}/search/stream
POST   /collections/{id}/refresh_all
GET    /collections/internal/filter-schema

# Source Connections
GET    /source-connections/?collection_id={id}
POST   /source-connections
GET    /source-connections/{id}
PATCH  /source-connections/{id}
DELETE /source-connections/{id}
POST   /source-connections/{id}/run
POST   /source-connections/{id}/jobs/{jobId}/cancel
GET    /source-connections/{shortName}/oauth2_url
POST   /connections/credentials/source/{shortName}

# Sources
GET    /sources/
GET    /sources/{shortName}

# API Keys
GET    /api-keys
POST   /api-keys
DELETE /api-keys?id={keyId}

# Auth Providers
GET    /auth-providers/list
GET    /auth-providers/detail/{shortName}
GET    /auth-providers/connections/
GET    /auth-providers/connections/{readableId}
POST   /auth-providers/connections/
PATCH  /auth-providers/connections/{readableId}
DELETE /auth-providers/{readableId}

# Organizations
GET    /organizations/
GET    /organizations/{id}
PUT    /organizations/{id}
DELETE /organizations/{id}
GET    /organizations/{id}/members
GET    /organizations/{id}/invitations
POST   /organizations/{id}/invitations
DELETE /organizations/{id}/invitations/{invitationId}
DELETE /organizations/{id}/members/{memberId}

# Users
POST   /users/

# Usage
GET    /usage/check-action?action={action}
POST   /usage/check-actions
GET    /usage/dashboard

# Billing
POST   /billing/checkout-session
POST   /billing/yearly/checkout-session
POST   /billing/portal-session

# S3
GET    /s3/status
POST   /s3/configure
DELETE /s3/configure

# Entities
GET    /entities/definitions/by-source/?source_short_name={name}
GET    /entities/latest_by_source_connection?source_connection_id={id}

# Sync
GET    /sync/{jobId}/progress

# Admin (superuser only)
GET    /admin/organizations
POST   /admin/organizations/{id}/features
```



## Appendix B: Component Props Reference

### Key Interfaces

```typescript
// BillingGuard - HIGH PRIORITY
interface BillingGuardProps {
  children: React.ReactNode;
  requiresActiveBilling?: boolean;
  action?: string;  // For usage limit checks
}

// ValidatedInput - HIGH PRIORITY
interface ValidatedInputProps {
  value: string;
  onChange: (value: string) => void;
  validation: FieldValidation;
  context?: any;
  showValidation?: boolean;
  forceValidate?: boolean;
}

// OrganizationSettings
interface OrganizationSettingsProps {
  currentOrganization: Organization;
  onOrganizationUpdate: (data: Partial<Organization>) => void;
  onPrimaryToggle: (isPrimary: boolean) => void;
  isPrimaryToggleLoading: boolean;
}

// MembersSettings
interface Member {
  id: string;
  email: string;
  role: 'admin' | 'member';
  joined_at: string;
}

interface Invitation {
  id: string;
  email: string;
  role: 'admin' | 'member';
  invited_at: string;
  expires_at: string;
}

// QueryTool
interface QueryToolProps {
  collectionId: string;
  endpoint: string;
}

// AdminDashboard
interface OrganizationMetrics {
  id: string;
  name: string;
  user_count: number;
  source_connection_count: number;
  entity_count: number;
  query_count: number;
  billing_plan?: string;
  billing_status?: string;
  enabled_features?: string[];
}
```



## Progress Notes

> Contributors: Add your progress notes here after completing tasks. This helps the next person know what's done and any context they might need. You can also add notes for the next developer on what you suggest they conitnue to work on. The trick is to break down large tasks into smaller, more manageable tasks and only work on one small task at a time and trust that the next developer will pick up where you left off.

### Notes

**Suggested starting points (simplest first):**
1. `/billing/success` route - simple callback page
2. `/billing/cancel` route - simple callback page
3. Add `X-Airweave-Session-ID` header to API client
4. Port `dateTime.ts` utility
5. Port `cronParser.ts` utility
