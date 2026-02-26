import { useAirweaveConnect, type SessionError } from "@airweave/connect-react";

// Configuration - in a real app, these would come from environment variables
const CONFIG = {
  API_URL: "http://localhost:8001",
  API_KEY: "test",
  COLLECTION_ID: "test-16c0r8",
  END_USER_ID: "anand",
  SESSION_MODE: "all",
  CONNECT_URL: "http://localhost:5173",
};

function App() {
  const { open, isOpen, isLoading, error, status } = useAirweaveConnect({
    connectUrl: CONFIG.CONNECT_URL,
    getSessionToken: async () => {
      const response = await fetch(`${CONFIG.API_URL}/connect/sessions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": CONFIG.API_KEY,
        },
        body: JSON.stringify({
          readable_collection_id: CONFIG.COLLECTION_ID,
          mode: CONFIG.SESSION_MODE,
          end_user_id: CONFIG.END_USER_ID,
        }),
      });
      const data = await response.json();
      return data.session_token;
    },
    theme: {
      mode: "light",
    },
    onSuccess: (connectionId: string) => {
      console.log("Connection created:", connectionId);
    },
    onError: (error: SessionError) => {
      console.error("Error:", error.message);
    },
    onClose: (reason: "success" | "cancel" | "error") => {
      console.log("Modal closed:", reason);
    },
  });

  return (
    <div className="container">
      <img
        src="https://avatars.githubusercontent.com/u/14957082?s=200&v=4"
        alt="Logo"
        className="logo"
      />

      <div className="chat-input-container">
        <div className="input-row">
          <input
            type="text"
            className="chat-input"
            placeholder="Ask anything..."
          />
        </div>

        <div className="toolbar">
          <button className="apps-btn" onClick={open} disabled={isLoading}>
            <span className="plus-icon">+</span>
            {isLoading ? "Loading..." : "Apps"}
          </button>
        </div>
      </div>

      {error && <div className="error-message">Error: {error.message}</div>}

      <div className="status-bar">
        <span>Modal: {isOpen ? "Open" : "Closed"}</span>
        {status && <span>Status: {status.status}</span>}
      </div>
    </div>
  );
}

export default App;
