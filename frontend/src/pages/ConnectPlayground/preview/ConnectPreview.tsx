import { useEffect, useState, useMemo } from "react";
import { X } from "lucide-react";
import { useIframeBridge } from "./useIframeBridge";
import type { PlaygroundConfig, ShadowSize } from "../hooks/usePlaygroundState";

interface ConnectPreviewProps {
  isOpen: boolean;
  onClose: () => void;
  sessionToken: string | null;
  config: PlaygroundConfig;
  connectUrl: string;
}

const SHADOW_MAP: Record<ShadowSize, string> = {
  none: "none",
  sm: "0 1px 2px 0 rgba(0,0,0,.05)",
  md: "0 4px 6px -1px rgba(0,0,0,.1), 0 2px 4px -2px rgba(0,0,0,.1)",
  lg: "0 10px 15px -3px rgba(0,0,0,.1), 0 4px 6px -4px rgba(0,0,0,.1)",
  xl: "0 25px 50px -12px rgba(0,0,0,.25)",
};

export function ConnectPreview({
  isOpen,
  onClose,
  sessionToken,
  config,
  connectUrl,
}: ConnectPreviewProps) {
  const { iframeRef } = useIframeBridge({ sessionToken, config, isOpen });
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isOpen) {
      requestAnimationFrame(() => setVisible(true));
    } else {
      setVisible(false);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  const modalStyle = useMemo(() => ({
    width: 400,
    height: 520,
    borderRadius: config.modal.borderRadius,
    boxShadow: SHADOW_MAP[config.modal.shadow],
    border: config.modal.borderWidth > 0
      ? `${config.modal.borderWidth}px solid ${config.modal.borderColor}`
      : "none",
  }), [config.modal]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity duration-200"
        style={{ opacity: visible ? 1 : 0 }}
      />

      {/* Modal */}
      <div
        className="relative transition-all duration-200 ease-out"
        style={{
          opacity: visible ? 1 : 0,
          transform: visible ? "scale(1) translateY(0)" : "scale(0.96) translateY(8px)",
        }}
      >
        <button
          onClick={onClose}
          className="absolute -top-3 -right-3 z-10 w-7 h-7 rounded-full bg-background border border-border/50 shadow-lg flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>

        <div
          className="overflow-hidden"
          style={modalStyle}
        >
          <iframe
            ref={iframeRef}
            src={connectUrl}
            className="w-full h-full border-0"
            allow="clipboard-write"
            title="Airweave Connect"
          />
        </div>
      </div>
    </div>
  );
}
