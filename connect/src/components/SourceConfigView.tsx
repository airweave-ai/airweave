import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "../lib/api";
import { generateRandomSuffix } from "../lib/sourceConfig-utils";
import { useTheme } from "../lib/theme";
import type { Source, SourceConnectionCreateRequest } from "../lib/types";
import { useOAuthFlow } from "../lib/useOAuthFlow";
import { AppIcon } from "./AppIcon";
import { AuthMethodSelector } from "./AuthMethodSelector";
import { BackButton } from "./BackButton";
import { Button } from "./Button";
import { LoadingScreen } from "./LoadingScreen";
import { PageLayout } from "./PageLayout";
import {
  ConfigFieldsSection,
  ConnectionNameField,
  DirectAuthSection,
  FormErrorAlert,
  OAuthSection,
} from "./SourceConfigView/index";

interface SourceConfigViewProps {
  source: Source;
  collectionId: string;
  onBack: () => void;
  onSuccess: (connectionId: string) => void;
}

export function SourceConfigView({
  source,
  collectionId,
  onBack,
  onSuccess,
}: SourceConfigViewProps) {
  const { labels, options } = useTheme();

  const {
    data: sourceDetails,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["source-details", source.short_name],
    queryFn: () => apiClient.getSourceDetails(source.short_name),
  });

  const [connectionName, setConnectionName] = useState(() =>
    options.showConnectionName
      ? ""
      : `${source.short_name}_${generateRandomSuffix()}`,
  );
  const [authMethod, setAuthMethod] = useState<"direct" | "oauth_browser">(
    "direct",
  );
  const [authValues, setAuthValues] = useState<Record<string, unknown>>({});
  const [configValues, setConfigValues] = useState<Record<string, unknown>>({});
  const [byocValues, setByocValues] = useState({
    client_id: "",
    client_secret: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const availableAuthMethods =
    sourceDetails?.auth_methods.filter(
      (m): m is "direct" | "oauth_browser" =>
        m === "direct" || m === "oauth_browser",
    ) ?? [];

  const effectiveAuthMethod = availableAuthMethods.includes(authMethod)
    ? authMethod
    : (availableAuthMethods[0] ?? "direct");

  const oauthFlow = useOAuthFlow({
    shortName: source.short_name,
    sourceName: source.name,
    collectionId,
    configValues,
    byocValues,
    requiresByoc: sourceDetails?.requires_byoc ?? false,
    syncImmediately: false,
    onSuccess,
    onCancel: onBack,
  });

  const hasAutoTriggeredOAuth = useRef(false);

  const hasConfigFields =
    (sourceDetails?.config_fields?.fields?.length ?? 0) > 0;
  const shouldAutoTriggerOAuth =
    sourceDetails &&
    effectiveAuthMethod === "oauth_browser" &&
    !sourceDetails.requires_byoc &&
    !hasConfigFields &&
    !options.showConnectionName &&
    availableAuthMethods.length <= 1;

  useEffect(() => {
    if (
      shouldAutoTriggerOAuth &&
      !hasAutoTriggeredOAuth.current &&
      oauthFlow.status === "idle"
    ) {
      hasAutoTriggeredOAuth.current = true;
      oauthFlow.initiateOAuth();
    }
  }, [shouldAutoTriggerOAuth, oauthFlow]);

  const createMutation = useMutation({
    mutationFn: (payload: SourceConnectionCreateRequest) =>
      apiClient.createSourceConnection(payload),
    onSuccess: (response) => onSuccess(response.id),
    onError: (err) => {
      setErrors({
        _form: err instanceof Error ? err.message : labels.connectionFailed,
      });
    },
  });

  const clearError = useCallback((key: string) => {
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const handleAuthValueChange = (fieldName: string, value: unknown) => {
    setAuthValues((prev) => ({ ...prev, [fieldName]: value }));
    if (errors[fieldName]) clearError(fieldName);
  };

  const handleConfigValueChange = (fieldName: string, value: unknown) => {
    setConfigValues((prev) => ({ ...prev, [fieldName]: value }));
    if (errors[`config_${fieldName}`]) clearError(`config_${fieldName}`);
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (effectiveAuthMethod === "direct" && sourceDetails?.auth_fields) {
      for (const field of sourceDetails.auth_fields.fields) {
        if (field.required) {
          const value = authValues[field.name];
          if (value === undefined || value === "" || value === null) {
            newErrors[field.name] = labels.fieldRequired;
          }
        }
      }
    }

    if (
      effectiveAuthMethod === "oauth_browser" &&
      sourceDetails?.requires_byoc
    ) {
      if (!byocValues.client_id.trim()) {
        newErrors.byoc_client_id = labels.fieldRequired;
      }
      if (!byocValues.client_secret.trim()) {
        newErrors.byoc_client_secret = labels.fieldRequired;
      }
    }

    if (sourceDetails?.config_fields) {
      for (const field of sourceDetails.config_fields.fields) {
        if (field.required) {
          const value = configValues[field.name];
          if (value === undefined || value === "" || value === null) {
            newErrors[`config_${field.name}`] = labels.fieldRequired;
          }
        }
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleOAuthConnect = async () => {
    if (sourceDetails?.requires_byoc) {
      const newErrors: Record<string, string> = {};
      if (!byocValues.client_id.trim()) {
        newErrors.byoc_client_id = labels.fieldRequired;
      }
      if (!byocValues.client_secret.trim()) {
        newErrors.byoc_client_secret = labels.fieldRequired;
      }
      if (Object.keys(newErrors).length > 0) {
        setErrors(newErrors);
        return;
      }
    }
    await oauthFlow.initiateOAuth();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    const payload: SourceConnectionCreateRequest = {
      short_name: source.short_name,
      name: connectionName || source.name,
      readable_collection_id: collectionId,
      sync_immediately: !options.enableFolderSelection,
    };

    if (effectiveAuthMethod === "direct") {
      payload.authentication = { credentials: authValues };
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
            : labels.loadSourceDetailsFailed}
        </p>
        <Button onClick={onBack} variant="secondary" className="mt-4">
          {labels.buttonBack}
        </Button>
      </PageLayout>
    );
  }

  const showDirectAuthFields =
    effectiveAuthMethod === "direct" &&
    (sourceDetails?.auth_fields?.fields?.length ?? 0) > 0;

  const showConfigFields =
    (sourceDetails?.config_fields?.fields?.length ?? 0) > 0;

  const showOAuthSection =
    effectiveAuthMethod === "oauth_browser" &&
    (sourceDetails?.requires_byoc ||
      oauthFlow.error ||
      oauthFlow.status === "waiting" ||
      oauthFlow.status === "popup_blocked");

  const isOAuthWaiting =
    effectiveAuthMethod === "oauth_browser" && oauthFlow.status === "waiting";

  const headerLeft = (
    <div className="flex items-center gap-2">
      <BackButton onClick={onBack} />
      <AppIcon shortName={source.short_name} name={source.name} className="size-5" />
    </div>
  );

  const footerContent = isOAuthWaiting ? undefined : (
    effectiveAuthMethod === "direct" ? (
      <Button
        type="submit"
        form="source-config-form"
        disabled={createMutation.isPending}
        className="w-full justify-center"
      >
        {createMutation.isPending ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            {labels.buttonCreatingConnection}
          </>
        ) : (
          labels.buttonCreateConnection
        )}
      </Button>
    ) : (
      <Button
        type="button"
        onClick={handleOAuthConnect}
        disabled={oauthFlow.status === "creating"}
        className="w-full justify-center"
      >
        {oauthFlow.status === "creating" ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            {labels.buttonConnecting}
          </>
        ) : (
          labels.buttonConnectOAuth.replace("{source}", source.name)
        )}
      </Button>
    )
  );

  return (
    <PageLayout title={source.name} headerLeft={headerLeft} footerContent={footerContent}>
      <form onSubmit={handleSubmit} id="source-config-form">
        {errors._form && <FormErrorAlert message={errors._form} />}

        {options.showConnectionName && (
          <ConnectionNameField
            value={connectionName}
            onChange={setConnectionName}
            sourceName={source.name}
            labels={labels}
          />
        )}

        {sourceDetails && (
          <AuthMethodSelector
            methods={sourceDetails.auth_methods}
            selected={effectiveAuthMethod}
            onChange={setAuthMethod}
            sourceName={source.name}
          />
        )}

        {showDirectAuthFields && sourceDetails?.auth_fields?.fields && (
          <DirectAuthSection
            fields={sourceDetails.auth_fields.fields}
            authValues={authValues}
            errors={errors}
            onFieldChange={handleAuthValueChange}
            labels={labels}
          />
        )}

        {showOAuthSection && (
          <OAuthSection
            requiresByoc={sourceDetails?.requires_byoc ?? false}
            byocValues={byocValues}
            onByocChange={setByocValues}
            errors={errors}
            onClearError={clearError}
            oauthStatus={oauthFlow.status}
            oauthError={oauthFlow.error}
            blockedAuthUrl={oauthFlow.blockedAuthUrl}
            onRetryPopup={oauthFlow.retryPopup}
            onManualLinkClick={oauthFlow.handleManualLinkClick}
            labels={labels}
          />
        )}

        {showConfigFields && sourceDetails?.config_fields?.fields && (
          <ConfigFieldsSection
            fields={sourceDetails.config_fields.fields}
            configValues={configValues}
            errors={errors}
            onFieldChange={handleConfigValueChange}
            labels={labels}
          />
        )}

        <div className="h-20" />
      </form>
    </PageLayout>
  );
}
