import { AirweaveConnect, type SessionError } from "@airweave/connect-js";
import "./style.css";

// Configuration - in a real app, these would come from environment variables
const CONFIG = {
  API_URL: "http://localhost:8001",
  API_KEY: "test",
  COLLECTION_ID: "test-16c0r8",
  END_USER_ID: "anand",
  SESSION_MODE: "all",
  CONNECT_URL: "http://localhost:5173",
};

// Get DOM elements
const appsBtn = document.getElementById("apps-btn") as HTMLButtonElement;
const errorMessage = document.getElementById("error-message") as HTMLDivElement;
const modalStatus = document.getElementById("modal-status") as HTMLSpanElement;
const sessionStatus = document.getElementById(
  "session-status",
) as HTMLSpanElement;

// Create the AirweaveConnect instance
const connect = new AirweaveConnect({
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
    showError(error.message);
  },
  onClose: (reason: "success" | "cancel" | "error") => {
    console.log("Modal closed:", reason);
    updateUI();
  },
  onStatusChange: (status) => {
    sessionStatus.textContent = `Status: ${status.status}`;
  },
});

// Update UI based on connect state
function updateUI() {
  const state = connect.getState();

  // Update button state
  appsBtn.disabled = state.isLoading;
  appsBtn.innerHTML = state.isLoading
    ? '<span class="plus-icon">+</span>Loading...'
    : '<span class="plus-icon">+</span>Apps';

  // Update modal status
  modalStatus.textContent = `Modal: ${state.isOpen ? "Open" : "Closed"}`;

  // Update session status
  if (state.status) {
    sessionStatus.textContent = `Status: ${state.status.status}`;
  } else {
    sessionStatus.textContent = "";
  }

  // Hide error if no error
  if (!state.error) {
    hideError();
  }
}

// Show error message
function showError(message: string) {
  errorMessage.textContent = `Error: ${message}`;
  errorMessage.style.display = "block";
}

// Hide error message
function hideError() {
  errorMessage.style.display = "none";
}

// Add click handler to open button
appsBtn.addEventListener("click", async () => {
  hideError();
  appsBtn.disabled = true;
  appsBtn.innerHTML = '<span class="plus-icon">+</span>Loading...';

  await connect.open();
  updateUI();
});

// Initial UI state
updateUI();
