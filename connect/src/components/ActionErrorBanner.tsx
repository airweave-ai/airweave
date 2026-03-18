import { X } from "lucide-react";
import { useEffect } from "react";

interface ActionErrorBannerProps {
  message: string;
  onDismiss: () => void;
  autoDismissMs?: number;
}

export function ActionErrorBanner({
  message,
  onDismiss,
  autoDismissMs = 5000,
}: ActionErrorBannerProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, autoDismissMs);
    return () => clearTimeout(timer);
  }, [onDismiss, autoDismissMs]);

  return (
    <div
      className="flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg text-sm animate-in fade-in slide-in-from-top-1 duration-200"
      role="alert"
      style={{
        backgroundColor:
          "color-mix(in srgb, var(--connect-error) 10%, transparent)",
        color: "var(--connect-error)",
        border:
          "1px solid color-mix(in srgb, var(--connect-error) 20%, transparent)",
      }}
    >
      <span>{message}</span>
      <button
        onClick={onDismiss}
        className="shrink-0 p-0.5 rounded cursor-pointer border-none bg-transparent transition-opacity opacity-60 hover:opacity-100"
        style={{ color: "var(--connect-error)" }}
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  );
}
