import { CheckCircle } from "lucide-react";
import type { ConnectSessionContext } from "../lib/types";

interface SuccessScreenProps {
  session: ConnectSessionContext;
}

export function SuccessScreen({ session }: SuccessScreenProps) {
  const expiresAt = new Date(session.expires_at);
  const formattedExpiry = expiresAt.toLocaleTimeString();

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-6 text-center"
      style={{ backgroundColor: "var(--connect-bg)" }}
    >
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
        style={{
          backgroundColor:
            "color-mix(in srgb, var(--connect-success) 20%, transparent)",
        }}
      >
        <CheckCircle
          className="w-8 h-8"
          strokeWidth={1.5}
          style={{ color: "var(--connect-success)" }}
        />
      </div>
      <h1
        className="font-medium text-lg mb-2"
        style={{ color: "var(--connect-text)" }}
      >
        Session Validated
      </h1>
      <p className="mb-1" style={{ color: "var(--connect-text-muted)" }}>
        Your session is active and ready.
      </p>
      <p className="text-sm" style={{ color: "var(--connect-text-muted)" }}>
        Mode: <span className="capitalize">{session.mode}</span> · Expires:{" "}
        {formattedExpiry}
      </p>
    </div>
  );
}
