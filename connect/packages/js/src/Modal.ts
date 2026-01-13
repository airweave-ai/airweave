import type { ModalStyle } from "./types";

export interface ModalOptions {
  url: string;
  style?: ModalStyle;
  showCloseButton?: boolean;
  onClose: () => void;
  onIframeLoad: (iframe: HTMLIFrameElement) => void;
}

const CONTAINER_ID = "airweave-connect-root";
const STYLES_ID = "airweave-connect-styles";

/**
 * Manages the modal DOM element that contains the Connect iframe.
 * Handles creating the overlay, modal box, iframe, and close button.
 */
export class Modal {
  private container: HTMLDivElement | null = null;
  private iframe: HTMLIFrameElement | null = null;
  private options: ModalOptions;
  private keydownHandler: ((e: KeyboardEvent) => void) | null = null;

  constructor(options: ModalOptions) {
    this.options = options;
  }

  /**
   * Show the modal with entrance animation.
   */
  show(): void {
    this.createContainer();
    this.createModal();
    this.attachEventListeners();

    // Trigger entrance animation on next frame
    requestAnimationFrame(() => {
      this.container?.classList.add("airweave-visible");
    });
  }

  /**
   * Destroy the modal and clean up DOM.
   */
  destroy(): void {
    this.detachEventListeners();

    if (this.container?.parentNode) {
      this.container.parentNode.removeChild(this.container);
    }

    this.container = null;
    this.iframe = null;
  }

  private createContainer(): void {
    // Remove existing container if present
    const existing = document.getElementById(CONTAINER_ID);
    if (existing) {
      existing.remove();
    }

    this.container = document.createElement("div");
    this.container.id = CONTAINER_ID;
    this.injectStyles();
    document.body.appendChild(this.container);
  }

  private createModal(): void {
    if (!this.container) return;

    const { style, showCloseButton, url } = this.options;

    // Overlay (dark background)
    const overlay = document.createElement("div");
    overlay.className = "airweave-overlay";
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        this.options.onClose();
      }
    });

    // Modal box
    const modalBox = document.createElement("div");
    modalBox.className = "airweave-modal";
    modalBox.style.width = style?.width ?? "90%";
    modalBox.style.maxWidth = style?.maxWidth ?? "400px";
    modalBox.style.height = style?.height ?? "80%";
    modalBox.style.maxHeight = style?.maxHeight ?? "540px";
    modalBox.style.borderRadius = style?.borderRadius ?? "16px";

    // Close button
    if (showCloseButton) {
      const closeBtn = document.createElement("button");
      closeBtn.className = "airweave-close-btn";
      closeBtn.innerHTML = "&times;";
      closeBtn.setAttribute("aria-label", "Close");
      closeBtn.addEventListener("click", () => this.options.onClose());
      modalBox.appendChild(closeBtn);
    }

    // Iframe
    this.iframe = document.createElement("iframe");
    this.iframe.src = url;
    this.iframe.className = "airweave-iframe";
    this.iframe.title = "Airweave Connect";
    this.iframe.addEventListener("load", () => {
      if (this.iframe) {
        this.options.onIframeLoad(this.iframe);
      }
    });

    modalBox.appendChild(this.iframe);
    overlay.appendChild(modalBox);
    this.container.appendChild(overlay);
  }

  private injectStyles(): void {
    // Check if styles already exist
    if (document.getElementById(STYLES_ID)) return;

    const style = document.createElement("style");
    style.id = STYLES_ID;
    style.textContent = `
      #${CONTAINER_ID} {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 10000;
        pointer-events: none;
      }

      .airweave-overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 0;
        transition: opacity 0.15s ease-out;
        pointer-events: auto;
      }

      #${CONTAINER_ID}.airweave-visible .airweave-overlay {
        opacity: 1;
      }

      .airweave-modal {
        position: relative;
        background-color: white;
        overflow: hidden;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
        transform: scale(0.95) translateY(10px);
        opacity: 0;
        transition: transform 0.15s ease-out, opacity 0.15s ease-out;
      }

      #${CONTAINER_ID}.airweave-visible .airweave-modal {
        transform: scale(1) translateY(0);
        opacity: 1;
      }

      .airweave-close-btn {
        position: absolute;
        top: 12px;
        right: 12px;
        width: 32px;
        height: 32px;
        border: none;
        background: rgba(0, 0, 0, 0.1);
        border-radius: 50%;
        cursor: pointer;
        font-size: 20px;
        color: #666;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10;
        transition: background 0.2s;
      }

      .airweave-close-btn:hover {
        background: rgba(0, 0, 0, 0.2);
      }

      .airweave-iframe {
        width: 100%;
        height: 100%;
        border: none;
      }
    `;
    document.head.appendChild(style);
  }

  private attachEventListeners(): void {
    this.keydownHandler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        this.options.onClose();
      }
    };
    document.addEventListener("keydown", this.keydownHandler);
  }

  private detachEventListeners(): void {
    if (this.keydownHandler) {
      document.removeEventListener("keydown", this.keydownHandler);
      this.keydownHandler = null;
    }
  }
}
