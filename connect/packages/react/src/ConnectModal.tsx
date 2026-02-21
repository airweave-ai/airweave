import { useEffect, useState } from "react";
import type { ModalStyle } from "./useAirweaveConnect";

interface ConnectModalProps {
  connectUrl: string;
  onClose: () => void;
  onIframeRef: (iframe: HTMLIFrameElement | null) => void;
  modalStyle?: ModalStyle;
  showCloseButton?: boolean;
}

export function ConnectModal({
  connectUrl,
  onClose,
  onIframeRef,
  modalStyle,
  showCloseButton = false,
}: ConnectModalProps) {
  const [isVisible, setIsVisible] = useState(false);

  // Trigger entry animation after mount
  useEffect(() => {
    // Small delay to ensure the initial styles are applied before transitioning
    const timer = requestAnimationFrame(() => {
      setIsVisible(true);
    });
    return () => cancelAnimationFrame(timer);
  }, []);

  // Handle ESC key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Handle click outside
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0, 0, 0, 0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10000,
        opacity: isVisible ? 1 : 0,
        transition: "opacity 0.15s ease-out",
      }}
      onClick={handleOverlayClick}
    >
      <div
        style={{
          position: "relative",
          width: modalStyle?.width ?? "90%",
          maxWidth: modalStyle?.maxWidth ?? "400px",
          height: modalStyle?.height ?? "80%",
          maxHeight: modalStyle?.maxHeight ?? "540px",
          backgroundColor: "white",
          borderRadius: modalStyle?.borderRadius ?? "16px",
          overflow: "hidden",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
          transform: isVisible
            ? "scale(1) translateY(0)"
            : "scale(0.95) translateY(10px)",
          opacity: isVisible ? 1 : 0,
          transition: "transform 0.15s ease-out, opacity 0.15s ease-out",
        }}
      >
        {showCloseButton && (
          <button
            onClick={onClose}
            style={{
              position: "absolute",
              top: 12,
              right: 12,
              width: 32,
              height: 32,
              border: "none",
              background: "rgba(0, 0, 0, 0.1)",
              borderRadius: "50%",
              cursor: "pointer",
              fontSize: 20,
              color: "#666",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 10,
              transition: "background 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(0, 0, 0, 0.2)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "rgba(0, 0, 0, 0.1)";
            }}
            aria-label="Close"
          >
            ×
          </button>
        )}
        <iframe
          ref={onIframeRef}
          src={connectUrl}
          style={{
            width: "100%",
            height: "100%",
            border: "none",
          }}
          title="Airweave Connect"
        />
      </div>
    </div>
  );
}
