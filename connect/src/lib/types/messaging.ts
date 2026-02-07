import type { ConnectTheme } from "./theme";
import type { SessionStatus } from "./session";

// postMessage types - messages sent from child (Connect iframe) to parent
export type ChildToParentMessage =
  | { type: "CONNECT_READY" }
  | { type: "REQUEST_TOKEN"; requestId: string }
  | { type: "STATUS_CHANGE"; status: SessionStatus }
  | { type: "CONNECTION_CREATED"; connectionId: string }
  | { type: "CLOSE"; reason: "success" | "cancel" | "error" };

// Navigation views for NAVIGATE message
export type NavigateView =
  | "connections"
  | "sources"
  | "configure"
  | "folder-selection";

// postMessage types - messages sent from parent to child
export type ParentToChildMessage =
  | {
      type: "TOKEN_RESPONSE";
      requestId: string;
      token: string;
      theme?: ConnectTheme;
    }
  | { type: "TOKEN_ERROR"; requestId: string; error: string }
  | { type: "SET_THEME"; theme: ConnectTheme }
  | { type: "NAVIGATE"; view: NavigateView };
