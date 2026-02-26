import type {
  ChildToParentMessage,
  ConnectTheme,
  NavigateView,
  ParentToChildMessage,
  SessionError,
} from "airweave-connect/lib/types";
import { DEFAULT_CONNECT_URL } from "./constants";
import { Modal } from "./Modal";
import { PostMessageHandler } from "./PostMessage";
import type { AirweaveConnectConfig, AirweaveConnectState } from "./types";

/**
 * AirweaveConnect - Vanilla JavaScript SDK for Airweave Connect.
 *
 * Provides a simple class-based API to open a modal containing the
 * Airweave Connect iframe, handle authentication, and receive callbacks
 * when connections are created.
 *
 * @example
 * ```javascript
 * const connect = new AirweaveConnect({
 *   getSessionToken: async () => {
 *     const res = await fetch('/api/connect-session');
 *     const data = await res.json();
 *     return data.session_token;
 *   },
 *   onSuccess: (connectionId) => {
 *     console.log('Connected:', connectionId);
 *   },
 *   onError: (error) => {
 *     console.error('Error:', error.message);
 *   },
 *   onClose: (reason) => {
 *     console.log('Modal closed:', reason);
 *   },
 * });
 *
 * document.getElementById('connect-btn').addEventListener('click', () => {
 *   connect.open();
 * });
 * ```
 */
export class AirweaveConnect {
  private config: Required<
    Pick<AirweaveConnectConfig, "connectUrl" | "showCloseButton">
  > &
    AirweaveConnectConfig;
  private state: AirweaveConnectState;
  private modal: Modal | null = null;
  private postMessageHandler: PostMessageHandler | null = null;
  private sessionToken: string | null = null;
  private expectedOrigin: string;

  constructor(config: AirweaveConnectConfig) {
    this.config = {
      connectUrl: DEFAULT_CONNECT_URL,
      showCloseButton: false,
      ...config,
    };

    this.state = {
      isOpen: false,
      isLoading: false,
      error: null,
      status: null,
    };

    this.expectedOrigin = this.deriveOrigin(this.config.connectUrl);
  }

  /**
   * Open the Connect modal.
   * Fetches a session token using the configured `getSessionToken` function,
   * then displays the modal with the Connect iframe.
   */
  async open(): Promise<void> {
    if (this.state.isOpen) return;

    this.state.isLoading = true;
    this.state.error = null;

    try {
      // Fetch session token
      this.sessionToken = await this.config.getSessionToken();

      // Build iframe URL
      const iframeUrl = this.buildIframeUrl();

      // Create and show modal
      this.modal = new Modal({
        url: iframeUrl,
        style: this.config.modalStyle,
        showCloseButton: this.config.showCloseButton,
        onClose: () => this.handleClose("cancel"),
        onIframeLoad: (iframe) => this.setupPostMessage(iframe),
      });

      this.modal.show();
      this.state.isOpen = true;
    } catch (err) {
      const sessionError: SessionError = {
        code: "network_error",
        message:
          err instanceof Error ? err.message : "Failed to get session token",
      };
      this.state.error = sessionError;
      this.config.onError?.(sessionError);
    } finally {
      this.state.isLoading = false;
    }
  }

  /**
   * Close the Connect modal.
   */
  close(): void {
    this.handleClose("cancel");
  }

  /**
   * Dynamically update the theme while the modal is open.
   */
  setTheme(theme: ConnectTheme): void {
    this.config.theme = theme;
    this.sendToIframe({ type: "SET_THEME", theme });
  }

  /**
   * Navigate to a specific view within the Connect modal.
   */
  navigate(view: NavigateView): void {
    this.sendToIframe({ type: "NAVIGATE", view });
  }

  /**
   * Get the current state (read-only).
   */
  getState(): Readonly<AirweaveConnectState> {
    return { ...this.state };
  }

  /**
   * Update configuration options.
   * Useful for changing callbacks after initialization.
   */
  updateConfig(config: Partial<AirweaveConnectConfig>): void {
    this.config = { ...this.config, ...config };
    if (config.connectUrl) {
      this.expectedOrigin = this.deriveOrigin(config.connectUrl);
    }
  }

  /**
   * Clean up all resources.
   * Call this when you're done with the instance.
   */
  destroy(): void {
    this.handleClose("cancel");
  }

  private deriveOrigin(url: string): string {
    try {
      return new URL(url).origin;
    } catch {
      // Fallback for invalid URLs - will cause postMessage to fail safely
      return url;
    }
  }

  private buildIframeUrl(): string {
    const url = new URL(this.config.connectUrl);
    if (this.config.theme?.mode) {
      url.searchParams.set("theme", this.config.theme.mode);
    }
    return url.toString();
  }

  private handleClose(reason: "success" | "cancel" | "error"): void {
    if (!this.state.isOpen) return;

    this.modal?.destroy();
    this.modal = null;
    this.postMessageHandler?.destroy();
    this.postMessageHandler = null;
    this.sessionToken = null;
    this.state.isOpen = false;
    this.state.status = null;

    this.config.onClose?.(reason);
  }

  private setupPostMessage(iframe: HTMLIFrameElement): void {
    this.postMessageHandler = new PostMessageHandler({
      iframe,
      expectedOrigin: this.expectedOrigin,
      onMessage: (message) => this.handleMessage(message),
    });
  }

  private sendToIframe(message: ParentToChildMessage): void {
    this.postMessageHandler?.send(message);
  }

  private handleMessage(data: ChildToParentMessage): void {
    switch (data.type) {
      case "CONNECT_READY":
        // Iframe is ready - navigate to initial view if specified
        if (this.config.initialView) {
          this.sendToIframe({ type: "NAVIGATE", view: this.config.initialView });
        }
        break;

      case "REQUEST_TOKEN":
        // Re-fetch token from the customer's backend to handle expiry/refresh
        this.config
          .getSessionToken()
          .then((token) => {
            this.sessionToken = token;
            this.sendToIframe({
              type: "TOKEN_RESPONSE",
              requestId: data.requestId,
              token,
              theme: this.config.theme,
            });
          })
          .catch(() => {
            this.sendToIframe({
              type: "TOKEN_ERROR",
              requestId: data.requestId,
              error: "Failed to refresh session token",
            });
          });
        break;

      case "STATUS_CHANGE":
        this.state.status = data.status;
        this.config.onStatusChange?.(data.status);

        if (data.status.status === "error") {
          this.state.error = data.status.error;
          this.config.onError?.(data.status.error);
        }
        break;

      case "CONNECTION_CREATED":
        this.config.onConnectionCreated?.(data.connectionId);
        this.config.onSuccess?.(data.connectionId);
        break;

      case "CLOSE":
        this.handleClose(data.reason);
        break;
    }
  }
}
