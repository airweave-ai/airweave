import type {
  ChildToParentMessage,
  ParentToChildMessage,
} from "airweave-connect/lib/types";

export interface PostMessageHandlerOptions {
  iframe: HTMLIFrameElement;
  expectedOrigin: string;
  onMessage: (message: ChildToParentMessage) => void;
}

/**
 * Handles secure postMessage communication with the Connect iframe.
 * Validates message origins to prevent spoofed messages from malicious sites.
 */
export class PostMessageHandler {
  private iframe: HTMLIFrameElement;
  private expectedOrigin: string;
  private onMessage: (message: ChildToParentMessage) => void;
  private messageHandler: ((event: MessageEvent) => void) | null = null;

  constructor(options: PostMessageHandlerOptions) {
    this.iframe = options.iframe;
    this.expectedOrigin = options.expectedOrigin;
    this.onMessage = options.onMessage;
    this.attachListener();
  }

  /**
   * Send a message to the iframe with the expected origin.
   */
  send(message: ParentToChildMessage): void {
    this.iframe.contentWindow?.postMessage(message, this.expectedOrigin);
  }

  /**
   * Clean up event listeners.
   */
  destroy(): void {
    this.detachListener();
  }

  private attachListener(): void {
    this.messageHandler = (event: MessageEvent) => {
      // Validate origin to prevent spoofed messages
      if (event.origin !== this.expectedOrigin) {
        return;
      }

      const data = event.data as ChildToParentMessage;
      if (!data || typeof data !== "object" || !("type" in data)) {
        return;
      }

      this.onMessage(data);
    };

    window.addEventListener("message", this.messageHandler);
  }

  private detachListener(): void {
    if (this.messageHandler) {
      window.removeEventListener("message", this.messageHandler);
      this.messageHandler = null;
    }
  }
}
