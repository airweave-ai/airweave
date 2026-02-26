import type { ConnectLabels, OAuthFlowStatus } from "../../lib/types";
import { ByocFields } from "../ByocFields";
import { OAuthStatusUI } from "../OAuthStatusUI";

interface OAuthSectionProps {
  requiresByoc: boolean;
  byocValues: { client_id: string; client_secret: string };
  onByocChange: (values: { client_id: string; client_secret: string }) => void;
  errors: Record<string, string>;
  onClearError: (key: string) => void;
  oauthStatus: OAuthFlowStatus;
  oauthError: string | null;
  blockedAuthUrl: string | null;
  onRetryPopup: () => void;
  onManualLinkClick: () => void;
  labels: Required<ConnectLabels>;
}

export function OAuthSection({
  requiresByoc,
  byocValues,
  onByocChange,
  errors,
  onClearError,
  oauthStatus,
  oauthError,
  blockedAuthUrl,
  onRetryPopup,
  onManualLinkClick,
  labels,
}: OAuthSectionProps) {
  return (
    <div className="mb-4">
      <h2
        className="text-sm font-bold opacity-70 mb-3"
        style={{ color: "var(--connect-text)" }}
      >
        {labels.configureAuthSection}
      </h2>

      {requiresByoc && (
        <ByocFields
          values={byocValues}
          onChange={onByocChange}
          errors={errors}
          onClearError={onClearError}
        />
      )}

      <OAuthStatusUI
        status={oauthStatus}
        error={oauthError}
        blockedAuthUrl={blockedAuthUrl}
        onRetryPopup={onRetryPopup}
        onManualLinkClick={onManualLinkClick}
      />
    </div>
  );
}
