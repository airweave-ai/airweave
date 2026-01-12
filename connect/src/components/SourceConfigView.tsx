import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { apiClient } from "../lib/api";
import { useTheme } from "../lib/theme";
import type {
  ConfigField,
  ConnectSessionContext,
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
  session: ConnectSessionContext;
  onBack: () => void;
  onSuccess: (connectionId: string) => void;
}

export function SourceConfigView({
  source,
  session: _session,
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
            <div
              className="mb-4 p-4 rounded-md text-sm text-center"
              style={{
                backgroundColor: "var(--connect-surface)",
                color: "var(--connect-text-muted)",
                border: "1px dashed var(--connect-border)",
              }}
            >
              OAuth flow will be available soon.
            </div>
          )}

          {showConfigFields && (
            <div className="mb-4">
              <h2
                className="text-sm font-medium mb-3"
                style={{ color: "var(--connect-text)" }}
              >
                Configuration
              </h2>
              {sourceDetails.config_fields?.fields.map((field: ConfigField) => (
                <DynamicFormField
                  key={field.name}
                  field={field}
                  value={configValues[field.name]}
                  onChange={(value) =>
                    handleConfigValueChange(field.name, value)
                  }
                  error={errors[`config_${field.name}`]}
                />
              ))}
            </div>
          )}

          <div className="h-20" />
        </form>
      </main>

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
          disabled={
            createMutation.isPending || effectiveAuthMethod === "oauth_browser"
          }
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

      <footer className="flex-shrink-0">
        <PoweredByAirweave />
      </footer>
    </div>
  );
}
