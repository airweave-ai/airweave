import { useMutation, useQuery } from "@tanstack/react-query";
import { ExternalLink, Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "../lib/api";
import {
  isPopupOpen,
  listenForOAuthComplete,
  openOAuthPopup,
} from "../lib/oauth";
import { useTheme } from "../lib/theme";
import type {
  ConfigField,
  OAuthCallbackResult,
  Source,
  SourceConnectionCreateRequest,
} from "../lib/types";
import { AppIcon } from "./AppIcon";
import { AuthMethodSelector } from "./AuthMethodSelector";
import { BackButton } from "./BackButton";
import { Button } from "./Button";
import { DynamicFormField } from "./DynamicFormField";
import { LoadingScreen } from "./LoadingScreen";
import { PageLayout } from "./PageLayout";
import { PoweredByAirweave } from "./PoweredByAirweave";

interface SourceConfigViewProps {
  source: Source;
  onBack: () => void;
  onSuccess: (connectionId: string) => void;
}

export function SourceConfigView({
  source,
  onBack,
  onSuccess,
}: SourceConfigViewProps) {
  const { labels } = useTheme();

  const {
    data: sourceDetails,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["source-details", source.short_name],
    queryFn: () => apiClient.getSourceDetails(source.short_name),
  });

  const [connectionName, setConnectionName] = useState("");
  const [authMethod, setAuthMethod] = useState<"direct" | "oauth_browser">(
    "direct",
  );
  const [authValues, setAuthValues] = useState<Record<string, unknown>>({});
  const [configValues, setConfigValues] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  // OAuth flow state
  const [oauthStatus, setOauthStatus] = useState<
    "idle" | "creating" | "waiting" | "error"
  >("idle");
  const [oauthError, setOauthError] = useState<string | null>(null);
  const oauthPopupRef = useRef<Window | null>(null);
  const pendingConnectionIdRef = useRef<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (payload: SourceConnectionCreateRequest) =>
      apiClient.createSourceConnection(payload),
    onSuccess: (response) => {
      onSuccess(response.id);
    },
    onError: (error) => {
      setErrors({
        _form:
          error instanceof Error
            ? error.message
            : "Failed to create connection",
      });
    },
  });

  const availableAuthMethods =
    sourceDetails?.auth_methods.filter(
      (m): m is "direct" | "oauth_browser" =>
        m === "direct" || m === "oauth_browser",
    ) ?? [];

  const effectiveAuthMethod = availableAuthMethods.includes(authMethod)
    ? authMethod
    : (availableAuthMethods[0] ?? "direct");

  const handleAuthValueChange = (fieldName: string, value: unknown) => {
    setAuthValues((prev) => ({ ...prev, [fieldName]: value }));
    if (errors[fieldName]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[fieldName];
        return newErrors;
      });
    }
  };

  const handleConfigValueChange = (fieldName: string, value: unknown) => {
    setConfigValues((prev) => ({ ...prev, [fieldName]: value }));
    if (errors[`config_${fieldName}`]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[`config_${fieldName}`];
        return newErrors;
      });
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (effectiveAuthMethod === "direct" && sourceDetails?.auth_fields) {
      for (const field of sourceDetails.auth_fields.fields) {
        if (field.required) {
          const value = authValues[field.name];
          if (value === undefined || value === "" || value === null) {
            newErrors[field.name] = "This field is required";
          }
        }
      }
    }

    if (sourceDetails?.config_fields) {
      for (const field of sourceDetails.config_fields.fields) {
        if (field.required) {
          const value = configValues[field.name];
          if (value === undefined || value === "" || value === null) {
            newErrors[`config_${field.name}`] = "This field is required";
          }
        }
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle OAuth callback result from popup
  const handleOAuthResult = useCallback(
    (result: OAuthCallbackResult) => {
      // Close popup if still open
      if (oauthPopupRef.current && !oauthPopupRef.current.closed) {
        oauthPopupRef.current.close();
      }
      oauthPopupRef.current = null;

      if (result.status === "success" && result.source_connection_id) {
        setOauthStatus("idle");
        onSuccess(result.source_connection_id);
      } else {
        setOauthStatus("error");
        setOauthError(
          result.error_message ?? "OAuth authentication failed. Please try again."
        );
      }
    },
    [onSuccess]
  );

  // Listen for OAuth completion messages
  useEffect(() => {
    if (oauthStatus !== "waiting") return;

    const cleanup = listenForOAuthComplete(handleOAuthResult);

    // Poll to check if popup was closed without completing
    const pollInterval = setInterval(() => {
      if (!isPopupOpen(oauthPopupRef.current) && oauthStatus === "waiting") {
        setOauthStatus("error");
        setOauthError("Authentication was cancelled. Please try again.");
        oauthPopupRef.current = null;
      }
    }, 500);

    return () => {
      cleanup();
      clearInterval(pollInterval);
    };
  }, [oauthStatus, handleOAuthResult]);

  // Initiate OAuth flow
  const handleOAuthConnect = async () => {
    setOauthStatus("creating");
    setOauthError(null);

    try {
      // Build redirect URI for OAuth callback
      const currentOrigin = window.location.origin;
      const redirectUri = `${currentOrigin}/oauth-callback`;

      const payload: SourceConnectionCreateRequest = {
        short_name: source.short_name,
        sync_immediately: true,
        authentication: {
          redirect_uri: redirectUri,
        },
      };

      if (connectionName.trim()) {
        payload.name = connectionName.trim();
      }

      if (Object.keys(configValues).length > 0) {
        payload.config = configValues;
      }

      const response = await apiClient.createSourceConnection(payload);
      pendingConnectionIdRef.current = response.id;

      // Check if we got an auth_url (OAuth flow)
      if (response.auth?.auth_url) {
        setOauthStatus("waiting");

        // Open OAuth popup
        const popup = openOAuthPopup({ url: response.auth.auth_url });

        if (!popup) {
          // Popup was blocked
          setOauthStatus("error");
          setOauthError(
            "Popup was blocked. Please allow popups for this site and try again."
          );
          return;
        }

        oauthPopupRef.current = popup;
      } else {
        // Unexpected: no auth_url returned
        setOauthStatus("error");
        setOauthError("Failed to get authorization URL. Please try again.");
      }
    } catch (err) {
      setOauthStatus("error");
      setOauthError(
        err instanceof Error ? err.message : "Failed to initiate OAuth flow"
      );
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    const payload: SourceConnectionCreateRequest = {
      short_name: source.short_name,
      sync_immediately: true,
    };

    if (connectionName.trim()) {
      payload.name = connectionName.trim();
    }

    if (effectiveAuthMethod === "direct") {
      payload.authentication = {
        credentials: authValues,
      };
    }

    if (Object.keys(configValues).length > 0) {
      payload.config = configValues;
    }

    createMutation.mutate(payload);
  };

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (error) {
    return (
      <PageLayout
        title="Error"
        headerLeft={<BackButton onClick={onBack} />}
        centerContent
      >
        <p style={{ color: "var(--connect-error)" }}>
          {error instanceof Error
            ? error.message
            : "Failed to load source details"}
        </p>
        <Button onClick={onBack} variant="secondary" className="mt-4">
          {labels.buttonBack}
        </Button>
      </PageLayout>
    );
  }

  const showDirectAuthFields =
    effectiveAuthMethod === "direct" &&
    sourceDetails?.auth_fields?.fields?.length;

  const showConfigFields = sourceDetails?.config_fields?.fields?.length;

  return (
    <div
      className="h-screen flex flex-col"
      style={{ backgroundColor: "var(--connect-bg)" }}
    >
      <header className="flex-shrink-0 p-6 pb-4">
        <div className="flex items-center gap-2">
          <BackButton onClick={onBack} />
          <AppIcon
            shortName={source.short_name}
            name={source.name}
            className="size-5"
          />
          <h1
            className="font-medium text-lg"
            style={{ color: "var(--connect-text)" }}
          >
            {source.name}
          </h1>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto px-6 scrollable-content">
        <form onSubmit={handleSubmit} id="source-config-form">
          {errors._form && (
            <div
              className="mb-4 p-3 rounded-md text-sm"
              style={{
                backgroundColor:
                  "color-mix(in srgb, var(--connect-error) 10%, transparent)",
                color: "var(--connect-error)",
              }}
            >
              {errors._form}
            </div>
          )}

          <div className="mb-4">
            <label
              htmlFor="connection-name"
              className="block text-sm font-medium mb-1"
              style={{ color: "var(--connect-text)" }}
            >
              Connection name
            </label>
            <p
              className="text-xs mt-1 mb-2"
              style={{ color: "var(--connect-text-muted)" }}
            >
              Optional. Give this connection a memorable name.
            </p>
            <input
              id="connection-name"
              type="text"
              value={connectionName}
              onChange={(e) => setConnectionName(e.target.value)}
              placeholder={`My ${source.name} connection`}
              className="w-full px-3 py-2 text-sm rounded-md border outline-none transition-colors"
              style={{
                backgroundColor: "var(--connect-surface)",
                color: "var(--connect-text)",
                borderColor: "var(--connect-border)",
              }}
            />
          </div>

          {sourceDetails && (
            <AuthMethodSelector
              methods={sourceDetails.auth_methods}
              selected={effectiveAuthMethod}
              onChange={setAuthMethod}
              sourceName={source.name}
            />
          )}

          {showDirectAuthFields && (
            <div className="mb-4">
              <h2
                className="text-sm font-medium mb-3"
                style={{ color: "var(--connect-text)" }}
              >
                Authentication
              </h2>
              {sourceDetails.auth_fields?.fields.map((field: ConfigField) => (
                <DynamicFormField
                  key={field.name}
                  field={field}
                  value={authValues[field.name]}
                  onChange={(value) => handleAuthValueChange(field.name, value)}
                  error={errors[field.name]}
                />
              ))}
            </div>
          )}

          {effectiveAuthMethod === "oauth_browser" && (
            <div className="mb-4">
              <h2
                className="text-sm font-medium mb-3"
                style={{ color: "var(--connect-text)" }}
              >
                Authentication
              </h2>

              {oauthError && (
                <div
                  className="mb-3 p-3 rounded-md text-sm"
                  style={{
                    backgroundColor:
                      "color-mix(in srgb, var(--connect-error) 10%, transparent)",
                    color: "var(--connect-error)",
                  }}
                >
                  {oauthError}
                </div>
              )}

              {oauthStatus === "waiting" ? (
                <div
                  className="p-4 rounded-md text-sm text-center"
                  style={{
                    backgroundColor: "var(--connect-surface)",
                    border: "1px solid var(--connect-border)",
                  }}
                >
                  <Loader2
                    className="w-5 h-5 animate-spin mx-auto mb-2"
                    style={{ color: "var(--connect-primary)" }}
                  />
                  <p style={{ color: "var(--connect-text)" }}>
                    Waiting for authorization...
                  </p>
                  <p
                    className="text-xs mt-1"
                    style={{ color: "var(--connect-text-muted)" }}
                  >
                    Complete the sign-in in the popup window
                  </p>
                </div>
              ) : (
                <Button
                  type="button"
                  onClick={handleOAuthConnect}
                  disabled={oauthStatus === "creating"}
                  className="w-full justify-center"
                  variant="secondary"
                >
                  {oauthStatus === "creating" ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <ExternalLink className="w-4 h-4" />
                      Connect with {source.name}
                    </>
                  )}
                </Button>
              )}
            </div>
          )}

          {showConfigFields !== undefined && showConfigFields > 0 && (
            <div className="mb-4">
              <h2
                className="text-sm font-medium mb-3"
                style={{ color: "var(--connect-text)" }}
              >
                Configuration
              </h2>
              {sourceDetails?.config_fields?.fields?.map(
                (field: ConfigField) => (
                  <DynamicFormField
                    key={field.name}
                    field={field}
                    value={configValues[field.name]}
                    onChange={(value) =>
                      handleConfigValueChange(field.name, value)
                    }
                    error={errors[`config_${field.name}`]}
                  />
                ),
              )}
            </div>
          )}

          <div className="h-20" />
        </form>
      </main>

      {effectiveAuthMethod === "direct" && (
        <div
          className="flex-shrink-0 px-6 pt-4 border-t"
          style={{
            backgroundColor: "var(--connect-bg)",
            borderColor: "var(--connect-border)",
          }}
        >
          <Button
            type="submit"
            form="source-config-form"
            disabled={createMutation.isPending}
            className="w-full justify-center"
          >
            {createMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Creating...
              </>
            ) : (
              "Create connection"
            )}
          </Button>
        </div>
      )}

      <footer className="flex-shrink-0">
        <PoweredByAirweave />
      </footer>
    </div>
  );
}
