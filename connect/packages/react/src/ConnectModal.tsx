import { useEffect } from "react";

interface ConnectModalProps {
  connectUrl: string;
  onClose: () => void;
  onIframeRef: (iframe: HTMLIFrameElement | null) => void;
}

export function ConnectModal({
  connectUrl,
  onClose,
  onIframeRef,
}: ConnectModalProps) {
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
      }}
      onClick={handleOverlayClick}
    >
      <div
        style={{
          width: "90%",
          maxWidth: "480px",
          height: "80%",
          maxHeight: "700px",
          backgroundColor: "white",
          borderRadius: "16px",
          overflow: "hidden",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
        }}
      >
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
