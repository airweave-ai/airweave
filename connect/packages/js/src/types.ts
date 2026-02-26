import type {
  ConnectTheme,
  NavigateView,
  SessionError,
  SessionStatus,
} from "airweave-connect/lib/types";

/** Modal styling options */
export interface ModalStyle {
  /** Modal width (default: "90%") */
  width?: string;
  /** Modal max width (default: "400px") */
  maxWidth?: string;
  /** Modal height (default: "80%") */
  height?: string;
  /** Modal max height (default: "540px") */
  maxHeight?: string;
  /** Modal border radius (default: "16px") */
  borderRadius?: string;
}

/** Configuration options for AirweaveConnect */
export interface AirweaveConnectConfig {
  /** Async function to get a session token from your backend */
  getSessionToken: () => Promise<string>;
  /** Theme configuration for the Connect UI */
  theme?: ConnectTheme;
  /** URL of the hosted Connect iframe (defaults to Airweave hosted) */
  connectUrl?: string;
  /** Called when a connection is successfully created */
  onSuccess?: (connectionId: string) => void;
  /** Called when an error occurs */
  onError?: (error: SessionError) => void;
  /** Called when the modal is closed */
  onClose?: (reason: "success" | "cancel" | "error") => void;
  /** Called when a new connection is created */
  onConnectionCreated?: (connectionId: string) => void;
  /** Called when the session status changes */
  onStatusChange?: (status: SessionStatus) => void;
  /** Initial view to show when modal opens (default: shows connections or sources based on mode) */
  initialView?: NavigateView;
  /** Custom modal styling */
  modalStyle?: ModalStyle;
  /** Show a close button in the modal (default: false) */
  showCloseButton?: boolean;
}

/** Current state of the AirweaveConnect instance */
export interface AirweaveConnectState {
  /** Whether the modal is currently open */
  isOpen: boolean;
  /** Whether a token is being fetched */
  isLoading: boolean;
  /** Current error, if any */
  error: SessionError | null;
  /** Current session status from the iframe */
  status: SessionStatus | null;
}
