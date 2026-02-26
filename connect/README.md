# Airweave Connect

Airweave Connect is a **hosted UI component** that enables end-users to connect data sources to the Airweave platform. It provides a Plaid-style Connect modal experience, designed to be embedded as an iframe in parent applications.

## Overview

When building applications with Airweave, you'll want to let your users connect their own data sources (Slack, GitHub, Google Drive, etc.). Rather than building this UI yourself, Airweave Connect provides a secure, pre-built widget that handles:

- Session validation and authentication
- Browsing available integrations
- OAuth flows and credential management
- Connection status management
- Theme customization to match your app

```
┌─────────────────────────────────────────────────────────────────┐
│  Your Application                                               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Airweave Connect (iframe)                                │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  • Lists available integrations                     │  │  │
│  │  │  • Handles OAuth flows                              │  │  │
│  │  │  • Manages connections                              │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Create a Connect Session (Server-Side)

Your backend creates a short-lived session token by calling the Airweave API:

```bash
curl -X POST https://api.airweave.io/connect/sessions \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "readable_collection_id": "my-collection-abc123",
    "mode": "all",
    "allowed_integrations": ["slack", "github", "google_drive"],
    "end_user_id": "user-123"
  }'
```

Response:
```json
{
  "session_id": "uuid",
  "session_token": "hmac-signed-token",
  "expires_at": "2024-01-01T00:10:00Z"
}
```

### 2. Embed the Connect Widget (Client-Side)

Embed the Connect widget as an iframe and pass the session token:

```html
<iframe
  id="airweave-connect"
  src="https://connect.airweave.io"
  style="width: 100%; height: 600px; border: none;"
></iframe>

<script>
  const iframe = document.getElementById('airweave-connect');

  window.addEventListener('message', (event) => {
    if (event.origin !== 'https://connect.airweave.io') return;

    const { type, payload } = event.data;

    if (type === 'REQUEST_TOKEN') {
      // Send the session token when requested
      iframe.contentWindow.postMessage({
        type: 'TOKEN_RESPONSE',
        payload: { token: 'your-session-token' }
      }, 'https://connect.airweave.io');
    }

    if (type === 'CONNECTION_CREATED') {
      console.log('New connection:', payload.connectionId);
    }

    if (type === 'CLOSE') {
      // User requested to close the modal
    }
  });
</script>
```

### 3. Session Modes

Control what users can do by setting the `mode` parameter:

| Mode | Description |
|------|-------------|
| `all` | Full access: connect, manage, and re-authenticate |
| `connect` | Add-only: can only create new connections |
| `manage` | View/delete only: can only manage existing connections |
| `reauth` | Re-auth only: can only re-authenticate existing connections |

## Backend API Endpoints

The Connect widget communicates with the following Airweave API endpoints:

### Session Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/connect/sessions` | POST | Create a new Connect session (requires API key) |
| `/connect/sessions/{id}` | GET | Validate session and get context (requires session token) |

### Integration Discovery

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/connect/sources` | GET | List available integrations |
| `/connect/sources/{short_name}` | GET | Get details for a specific integration |

### Connection Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/connect/source-connections` | GET | List connections in the session's collection |
| `/connect/source-connections` | POST | Create a new source connection |
| `/connect/source-connections/{id}` | DELETE | Delete a connection |
| `/connect/callback` | GET | OAuth callback handler |

## Parent-Child Communication

The widget communicates with the parent window via `postMessage`:

### Messages from Connect (Child → Parent)

| Type | Payload | Description |
|------|---------|-------------|
| `REQUEST_TOKEN` | `{}` | Requests session token from parent |
| `STATUS_CHANGE` | `{ status: string }` | Notifies of status changes |
| `CONNECTION_CREATED` | `{ connectionId: string }` | New connection created |
| `CLOSE` | `{}` | User requested to close |

### Messages to Connect (Parent → Child)

| Type | Payload | Description |
|------|---------|-------------|
| `TOKEN_RESPONSE` | `{ token: string }` | Session token response |
| `THEME_UPDATE` | `{ theme: ThemeConfig }` | Update widget theme |

## Theme Customization

Customize the widget appearance by sending a `THEME_UPDATE` message:

```javascript
iframe.contentWindow.postMessage({
  type: 'THEME_UPDATE',
  payload: {
    theme: {
      mode: 'dark', // 'light', 'dark', or 'system'
      colors: {
        background: '#0f172a',
        surface: '#1e293b',
        text: '#ffffff',
        primary: '#06b6d4',
        secondary: '#334155',
        success: '#22c55e',
        error: '#ef4444'
      }
    }
  }
}, 'https://connect.airweave.io');
```

## Development

### Prerequisites

- Node.js 18+
- npm

### Setup

```bash
npm install
npm run dev
```

The app will be available at http://localhost:3000

### Testing with Parent Window

Use the test harness at `public/test-parent.html` to test the iframe communication:

```bash
# Start the dev server
npm run dev

# Open test-parent.html in your browser
# It simulates a parent application embedding the Connect widget
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8001` | Backend API URL |

### Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server on port 3000 |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run test` | Run Vitest tests |
| `npm run lint` | Run ESLint |

## Project Structure

```
connect/
├── public/
│   ├── test-parent.html       # Test harness for iframe testing
│   ├── manifest.json          # PWA manifest
│   └── robots.txt
├── src/
│   ├── components/
│   │   ├── SessionProvider.tsx    # Main session state management
│   │   ├── LoadingScreen.tsx      # Loading state UI
│   │   ├── SuccessScreen.tsx      # Session valid state UI
│   │   └── ErrorScreen.tsx        # Error handling UI
│   ├── hooks/
│   │   └── useParentMessaging.ts  # postMessage communication
│   ├── lib/
│   │   ├── api.ts                 # API client for backend
│   │   ├── theme.tsx              # Theme context & customization
│   │   ├── types.ts               # TypeScript definitions
│   │   └── env.ts                 # Environment variables
│   ├── routes/
│   │   ├── __root.tsx             # Root layout
│   │   └── index.tsx              # Main entry point
│   ├── styles.css                 # Global styles (CSS variables)
│   └── router.tsx                 # Router configuration
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## Tech Stack

- **Framework**: [TanStack Start](https://tanstack.com/start) - Full-stack React framework
- **Routing**: [TanStack Router](https://tanstack.com/router) - Type-safe file-based routing
- **Styling**: [Tailwind CSS](https://tailwindcss.com/) - Utility-first CSS
- **Icons**: [Lucide React](https://lucide.dev/) - Icon library
- **Build**: Vite with Nitro for server-side rendering
- **Testing**: Vitest with React Testing Library

## Session Flow

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ Your Backend │     │  Airweave API   │     │ Airweave Connect │
└──────┬───────┘     └────────┬────────┘     └────────┬─────────┘
       │                      │                       │
       │ POST /connect/sessions                       │
       │ (with API key)       │                       │
       │─────────────────────>│                       │
       │                      │                       │
       │   session_token      │                       │
       │<─────────────────────│                       │
       │                      │                       │
       │                      │    TOKEN_RESPONSE     │
       │──────────────────────┼──────────────────────>│
       │                      │                       │
       │                      │  GET /sessions/{id}   │
       │                      │<──────────────────────│
       │                      │                       │
       │                      │   session_context     │
       │                      │──────────────────────>│
       │                      │                       │
       │                      │  CONNECTION_CREATED   │
       │<─────────────────────┼───────────────────────│
       │                      │                       │
```

## Security

- **Session tokens** are HMAC-signed and expire in 10 minutes (extended to 30 minutes during OAuth flows)
- Sessions are scoped to a specific **collection** - users can only manage connections in that collection
- **allowed_integrations** restricts which integrations users can access
- The `readable_collection_id` from the request body is always overridden by the session's collection (preventing escalation)

## Learn More

- [Airweave Documentation](https://docs.airweave.io)
- [TanStack Start Documentation](https://tanstack.com/start)
- [TanStack Router Documentation](https://tanstack.com/router)
