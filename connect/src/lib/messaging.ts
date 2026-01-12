import type { ChildToParentMessage } from "./types";

/**
 * Helper to send messages to the parent window (when running in iframe)
 */
function sendToParent(message: ChildToParentMessage): void {
  if (typeof window !== "undefined" && window.parent !== window) {
    window.parent.postMessage(message, "*");
  }
}

/**
 * Notify parent that a new connection was created
 */
export function notifyConnectionCreated(connectionId: string): void {
  sendToParent({ type: "CONNECTION_CREATED", connectionId });
}

/**
 * Request the parent to close the Connect widget
 */
export function requestClose(reason: "success" | "cancel" | "error"): void {
  sendToParent({ type: "CLOSE", reason });
}
