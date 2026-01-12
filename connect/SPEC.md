# Source Connection Creation - Implementation Spec

## Overview

Add the ability for end users to create new source connections from the Connect widget. This includes rendering dynamic forms for direct authentication (API keys/tokens) and handling OAuth flows via popup windows.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| OAuth strategy | Popup window | Connect runs in an iframe; redirects won't work. Popup communicates back via `postMessage` |
| UI pattern | Full-page view | Consistent with existing SourcesList pattern (not modal) |
| Auth methods | `direct` + `oauth_browser` | Skip `auth_provider` for initial implementation |
| Multiple auth options | Show both | When source supports both direct and OAuth, let user choose |

---

## API Endpoints

### GET `/connect/sources/{short_name}`
Returns source details including auth configuration.

**Response:**
```typescript
{
  name: string;
  short_name: string;
  description?: string;
  auth_methods: ("direct" | "oauth_browser" | "auth_provider")[];
  oauth_type?: "oauth1" | "access_only" | "with_refresh" | "with_rotating_refresh";
  requires_byoc: boolean;
  auth_fields?: { fields: ConfigField[] };
  config_fields?: { fields: ConfigField[] };
}
```

### POST `/connect/source-connections`
Creates a new source connection.

**Request (Direct Auth):**
```typescript
{
  short_name: "github",
  name?: "My GitHub",
  authentication: {
    credentials: { token: "ghp_xxx" }
  },
  config?: { ... },
  sync_immediately?: true
}
```

**Request (OAuth):**
```typescript
{
  short_name: "linear",
  name?: "My Linear",
  authentication: {
    redirect_uri: "https://connect.airweave.io/oauth-callback"
  }
}
```

**Response (OAuth - pending auth):**
```typescript
{
  id: "conn-123",
  name: "Linear Connection",
  short_name: "linear",
  status: "pending_auth",
  auth: {
    method: "oauth_browser",
    authenticated: false,
    auth_url: "https://linear.app/oauth/authorize?..."
  }
}
```

### GET `/connect/callback`
OAuth callback handler. Redirects to `redirect_url` with status params.

**Redirect params:**
- `status=success&source_connection_id=xxx`
- `status=error&error_type=xxx&error_message=xxx`

---

## Types to Add

**File: `src/lib/types.ts`**

```typescript
// Source details from GET /connect/sources/{short_name}
export interface SourceDetails {
  name: string;
  short_name: string;
  description?: string;
  auth_methods: AuthenticationMethod[];
  oauth_type?: "oauth1" | "access_only" | "with_refresh" | "with_rotating_refresh";
  requires_byoc: boolean;
  auth_fields?: Fields;
  config_fields?: Fields;
}

export interface Fields {
  fields: ConfigField[];
}

export interface ConfigField {
  name: string;
  title: string;
  description?: string;
  type: "string" | "number" | "boolean" | "array";
  required: boolean;
  items_type?: string;
  is_secret?: boolean;
}

// Authentication payloads
export interface DirectAuthPayload {
  credentials: Record<string, unknown>;
}

export interface OAuthBrowserAuthPayload {
  redirect_uri: string;
  client_id?: string;      // BYOC
  client_secret?: string;  // BYOC
}

export type AuthenticationPayload = DirectAuthPayload | OAuthBrowserAuthPayload;

// Create connection request
export interface SourceConnectionCreateRequest {
  short_name: string;
  name?: string;
  authentication?: AuthenticationPayload;
  config?: Record<string, unknown>;
  sync_immediately?: boolean;
}

// Create connection response
export interface SourceConnectionCreateResponse {
  id: string;
  name: string;
  short_name: string;
  status: SourceConnectionStatus;
  auth: {
    method: AuthenticationMethod;
    authenticated: boolean;
    auth_url?: string;
  };
}

// OAuth callback result (from popup)
export interface OAuthCallbackResult {
  status: "success" | "error";
  source_connection_id?: string;
  error_type?: string;
  error_message?: string;
}

// Extend NavigateView
export type NavigateView = "connections" | "sources" | "configure";
```

---

## API Client Methods

**File: `src/lib/api.ts`**

```typescript
async getSourceDetails(shortName: string): Promise<SourceDetails> {
  return this.fetch<SourceDetails>(`/connect/sources/${shortName}`);
}

async createSourceConnection(
  payload: SourceConnectionCreateRequest
): Promise<SourceConnectionCreateResponse> {
  return this.fetch<SourceConnectionCreateResponse>("/connect/source-connections", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
```

---

## Components

### 1. SourceConfigView (NEW)

**File: `src/components/SourceConfigView.tsx`**

Main configuration view for creating a source connection.

**Props:**
```typescript
interface SourceConfigViewProps {
  source: Source;
  session: ConnectSessionContext;
  onBack: () => void;
  onSuccess: (connectionId: string) => void;
}
```

**Structure:**
```
SourceConfigView
├── Header
│   ├── Back button
│   └── Source icon + name
├── Main (scrollable)
│   ├── Connection name input
│   ├── Auth method selector (if multiple methods)
│   ├── Direct auth section (if selected/only option)
│   │   └── DynamicFormField for each auth_field
│   ├── OAuth section (if selected/only option)
│   │   ├── "Connect with {Source}" button
│   │   └── BYOC fields (if requires_byoc)
│   └── Config section (if config_fields exist)
│       └── DynamicFormField for each config_field
├── Action bar
│   └── Submit button
└── Footer (PoweredByAirweave)
```

**State:**
```typescript
const [sourceDetails, setSourceDetails] = useState<SourceDetails | null>(null);
const [authMethod, setAuthMethod] = useState<"direct" | "oauth_browser">("direct");
const [connectionName, setConnectionName] = useState("");
const [authValues, setAuthValues] = useState<Record<string, unknown>>({});
const [configValues, setConfigValues] = useState<Record<string, unknown>>({});
const [errors, setErrors] = useState<Record<string, string>>({});
const [isSubmitting, setIsSubmitting] = useState(false);
```

### 2. DynamicFormField (NEW)

**File: `src/components/DynamicFormField.tsx`**

Renders a form field based on ConfigField definition.

**Props:**
```typescript
interface DynamicFormFieldProps {
  field: ConfigField;
  value: unknown;
  onChange: (value: unknown) => void;
  error?: string;
}
```

**Field type mapping:**
| Type | is_secret | Component |
|------|-----------|-----------|
| string | true | Password input with show/hide |
| string | false | Text input |
| number | - | Number input |
| boolean | - | Toggle switch |
| array | - | Tag input |

### 3. AuthMethodSelector (NEW)

**File: `src/components/AuthMethodSelector.tsx`**

Radio group for selecting between auth methods.

**Props:**
```typescript
interface AuthMethodSelectorProps {
  methods: AuthenticationMethod[];
  selected: "direct" | "oauth_browser";
  onChange: (method: "direct" | "oauth_browser") => void;
  sourceName: string;
}
```

---

## OAuth Utilities

**File: `src/lib/oauth.ts`**

```typescript
interface OAuthPopupOptions {
  url: string;
  width?: number;
  height?: number;
}

// Open centered popup window
export function openOAuthPopup(options: OAuthPopupOptions): Window | null {
  const { url, width = 600, height = 700 } = options;
  const left = window.screenX + (window.outerWidth - width) / 2;
  const top = window.screenY + (window.outerHeight - height) / 2;

  return window.open(
    url,
    "oauth-popup",
    `width=${width},height=${height},left=${left},top=${top}`
  );
}

// Listen for OAuth completion message
export function listenForOAuthComplete(
  callback: (result: OAuthCallbackResult) => void
): () => void {
  const handler = (event: MessageEvent) => {
    if (event.data?.type === "OAUTH_COMPLETE") {
      callback(event.data);
    }
  };
  window.addEventListener("message", handler);
  return () => window.removeEventListener("message", handler);
}
```

---

## OAuth Callback Route

**File: `src/routes/oauth-callback.tsx`**

Minimal page that receives OAuth result and posts to opener.

```typescript
export default function OAuthCallback() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result: OAuthCallbackResult = {
      status: params.get("status") as "success" | "error",
      source_connection_id: params.get("source_connection_id") ?? undefined,
      error_type: params.get("error_type") ?? undefined,
      error_message: params.get("error_message") ?? undefined,
    };

    // Post to opener (the Connect iframe)
    if (window.opener) {
      window.opener.postMessage({ type: "OAUTH_COMPLETE", ...result }, "*");
    }

    // Auto-close after short delay
    setTimeout(() => window.close(), 1000);
  }, []);

  return <div>Completing authentication...</div>;
}
```

---

## SuccessScreen Modifications

**File: `src/components/SuccessScreen.tsx`**

```typescript
// Add state for selected source
const [selectedSource, setSelectedSource] = useState<Source | null>(null);

// Update handler
const handleSelectSource = (source: Source) => {
  setSelectedSource(source);
  setView("configure");
};

// Add render case
if (view === "configure" && selectedSource) {
  return (
    <SourceConfigView
      source={selectedSource}
      session={session}
      onBack={() => {
        setSelectedSource(null);
        setView("sources");
      }}
      onSuccess={(connectionId) => {
        notifyConnectionCreated(connectionId);
        setSelectedSource(null);
        setView("connections");
        queryClient.invalidateQueries({ queryKey: ["source-connections"] });
      }}
    />
  );
}
```

---

## OAuth Flow Sequence

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ SourceConfigView│     │  Backend API    │     │  OAuth Provider │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │ POST /source-connections                      │
         │ { authentication: { redirect_uri } }          │
         │──────────────────────>│                       │
         │                       │                       │
         │ { auth: { auth_url } }│                       │
         │<──────────────────────│                       │
         │                       │                       │
         │ Open popup ───────────┼──────────────────────>│
         │                       │                       │
         │                       │   User authorizes     │
         │                       │<──────────────────────│
         │                       │                       │
         │                       │ GET /connect/callback │
         │                       │   ?state=x&code=y     │
         │                       │<──────────────────────│
         │                       │                       │
         │                       │ Redirect to           │
         │                       │ redirect_url?status=  │
         │                       │──────────────────────>│
         │                       │                       │
         │ postMessage           │                       │
         │ { OAUTH_COMPLETE }    │                       │
         │<──────────────────────┼───────────────────────│
         │                       │                       │
         │ Close popup           │                       │
         │ Show success          │                       │
```

---

## Implementation Checklist

### Phase 1: Types & API
- [ ] Add `SourceDetails` type to `types.ts`
- [ ] Add `ConfigField` type to `types.ts`
- [ ] Add `DirectAuthPayload` type to `types.ts`
- [ ] Add `OAuthBrowserAuthPayload` type to `types.ts`
- [ ] Add `SourceConnectionCreateRequest` type to `types.ts`
- [ ] Add `SourceConnectionCreateResponse` type to `types.ts`
- [ ] Add `OAuthCallbackResult` type to `types.ts`
- [ ] Extend `NavigateView` to include `"configure"`
- [ ] Add `getSourceDetails()` method to `api.ts`
- [ ] Add `createSourceConnection()` method to `api.ts`

### Phase 2: Direct Auth Flow
- [ ] Create `DynamicFormField.tsx` component
- [ ] Create `AuthMethodSelector.tsx` component
- [ ] Create `SourceConfigView.tsx` component (direct auth only)
- [ ] Modify `SuccessScreen.tsx` to handle configure view
- [ ] Add `selectedSource` state to SuccessScreen
- [ ] Update `handleSelectSource` to navigate to configure
- [ ] Test direct auth flow end-to-end

### Phase 3: OAuth Flow
- [ ] Create `src/lib/oauth.ts` utilities
- [ ] Create `src/routes/oauth-callback.tsx` route
- [ ] Add OAuth handling to `SourceConfigView.tsx`
- [ ] Handle popup open/close
- [ ] Listen for `OAUTH_COMPLETE` message
- [ ] Test OAuth flow with popup

### Phase 4: Polish
- [ ] Add form validation (required fields)
- [ ] Add BYOC fields for `requires_byoc` sources
- [ ] Handle popup blockers (show manual link option)
- [ ] Add loading states during submission
- [ ] Add error states and retry options
- [ ] Add labels to theme for new UI text

---

## File Structure

```
connect/src/
├── components/
│   ├── SuccessScreen.tsx        # MODIFY: add configure view
│   ├── SourceConfigView.tsx     # NEW: main config form
│   ├── DynamicFormField.tsx     # NEW: dynamic field renderer
│   ├── AuthMethodSelector.tsx   # NEW: auth method radio group
│   └── ...existing...
├── lib/
│   ├── api.ts                   # MODIFY: add new methods
│   ├── types.ts                 # MODIFY: add new types
│   ├── oauth.ts                 # NEW: OAuth popup utilities
│   └── ...existing...
└── routes/
    ├── oauth-callback.tsx       # NEW: OAuth callback page
    └── ...existing...
```

---

## Labels to Add

Add to `ConnectLabels` interface and defaults:

```typescript
configureHeading: "Connect {source}";
configureNameLabel: "Connection name";
configureNamePlaceholder: "My {source} connection";
configureAuthSection: "Authentication";
configureConfigSection: "Configuration";
authMethodDirect: "Enter credentials";
authMethodOAuth: "Connect with OAuth";
buttonConnectOAuth: "Connect with {source}";
buttonCreateConnection: "Create connection";
oauthPopupBlocked: "Popup was blocked";
oauthPopupBlockedHelp: "Please allow popups and try again";
fieldRequired: "This field is required";
connectionCreated: "Connection created successfully";
connectionFailed: "Failed to create connection";
```

---

## Testing

### Direct Auth Test
1. Open Connect widget in test-parent.html
2. Click "Create connection" button
3. Select a source with direct auth (e.g., one with API key)
4. Enter connection name and credentials
5. Click "Create connection"
6. Verify connection appears in connections list
7. Verify parent received `CONNECTION_CREATED` message

### OAuth Test
1. Open Connect widget
2. Select a source with OAuth (e.g., Linear, GitHub OAuth)
3. Click "Connect with {Source}"
4. Verify popup opens to OAuth provider
5. Complete authorization in popup
6. Verify popup closes automatically
7. Verify connection appears in connections list

### Error Handling Test
1. Test with invalid/empty credentials
2. Test OAuth cancellation (close popup)
3. Test with popup blocker enabled
4. Verify appropriate error messages shown
