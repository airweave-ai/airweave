# @airweave/connect-react

React hook for integrating Airweave Connect into your application.

## Installation

```bash
npm install @airweave/connect-react
```

## Usage

```tsx
import { useAirweaveConnect } from "@airweave/connect-react";

function App() {
  const { open, close, isOpen, isLoading, error, status } = useAirweaveConnect({
    getSessionToken: async () => {
      // Call your backend to get a session token
      const response = await fetch("/api/airweave/session", {
        method: "POST",
      });
      const data = await response.json();
      return data.sessionToken;
    },
    theme: {
      mode: "light", // or 'dark' or 'system'
    },
    onSuccess: (connectionId) => {
      console.log("Connection created:", connectionId);
    },
    onError: (error) => {
      console.error("Error:", error.message);
    },
    onClose: (reason) => {
      console.log("Modal closed:", reason);
    },
  });

  return (
    <button onClick={open} disabled={isLoading}>
      {isLoading ? "Loading..." : "Connect Apps"}
    </button>
  );
}
```

## API Reference

### `useAirweaveConnect(options)`

#### Options

| Option               | Type                                           | Required | Description                                    |
| -------------------- | ---------------------------------------------- | -------- | ---------------------------------------------- |
| `getSessionToken`    | `() => Promise<string>`                        | Yes      | Async function to fetch a session token        |
| `theme`              | `ConnectTheme`                                 | No       | Theme configuration for the Connect UI         |
| `connectUrl`         | `string`                                       | No       | URL of the hosted Connect iframe               |
| `onSuccess`          | `(connectionId: string) => void`               | No       | Called when a connection is created            |
| `onError`            | `(error: SessionError) => void`                | No       | Called when an error occurs                    |
| `onClose`            | `(reason: 'success' \| 'cancel' \| 'error') => void` | No       | Called when the modal is closed                |
| `onConnectionCreated`| `(connectionId: string) => void`               | No       | Called when a new connection is created        |
| `onStatusChange`     | `(status: SessionStatus) => void`              | No       | Called when the session status changes         |

#### Returns

| Property    | Type                   | Description                          |
| ----------- | ---------------------- | ------------------------------------ |
| `open`      | `() => void`           | Opens the Connect modal              |
| `close`     | `() => void`           | Closes the Connect modal             |
| `isOpen`    | `boolean`              | Whether the modal is currently open  |
| `isLoading` | `boolean`              | Whether a token is being fetched     |
| `error`     | `SessionError \| null` | Current error, if any                |
| `status`    | `SessionStatus \| null`| Current session status from iframe   |

## Theme Customization

You can customize the appearance of the Connect modal by passing a theme object:

```tsx
const { open } = useAirweaveConnect({
  getSessionToken,
  theme: {
    mode: "dark", // 'light', 'dark', or 'system'
    colors: {
      dark: {
        primary: "#6366f1",
        background: "#0f172a",
        surface: "#1e293b",
        text: "#ffffff",
        textMuted: "#9ca3af",
        border: "#334155",
        success: "#22c55e",
        error: "#ef4444",
      },
      light: {
        primary: "#4f46e5",
        background: "#ffffff",
        surface: "#f8fafc",
        text: "#1f2937",
        textMuted: "#6b7280",
        border: "#e5e7eb",
        success: "#22c55e",
        error: "#ef4444",
      },
    },
  },
});
```

## Backend Integration

Your backend needs to create session tokens by calling the Airweave API:

```bash
POST /connect/sessions
Headers:
  X-API-Key: your-api-key
  Content-Type: application/json
Body:
  {
    "readable_collection_id": "your-collection-id",
    "mode": "all",
    "end_user_id": "user-123"
  }
```

The response will include a `session_token` that you return from your `getSessionToken` function.

## License

MIT
