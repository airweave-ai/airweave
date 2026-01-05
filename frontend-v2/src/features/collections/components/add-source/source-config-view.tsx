/**
 * SourceConfigView - Configure and create a source connection
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useIsDark } from "@/hooks/use-is-dark";
import {
  createSourceConnection,
  fetchSource,
  type CreateSourceConnectionAuth,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";

import { type AuthMode } from "@/stores/add-source-store";

import { getAppIconUrl } from "../../utils/helpers";
import { SourceAuthenticationView } from "../source-authentication-view";
import { ConfigFields } from "./config-fields";
import { DirectAuthFields } from "./direct-auth-fields";
import { OAuthSettings } from "./oauth-settings";

interface SourceConfigViewProps {
  collectionId: string;
  collectionName: string;
  sourceShortName: string;
  sourceName: string;
  connectionName: string;
  authMode: AuthMode | null;
  authFields: Record<string, string>;
  configFields: Record<string, string | string[]>;
  useCustomOAuth: boolean;
  clientId: string;
  clientSecret: string;
  customRedirectUrl: string;
  onBack: () => void;
  onConnectionNameChange: (name: string) => void;
  onAuthModeChange: (mode: AuthMode) => void;
  onAuthFieldChange: (name: string, value: string) => void;
  onConfigFieldChange: (name: string, value: string | string[]) => void;
  onUseCustomOAuthChange: (use: boolean) => void;
  onClientIdChange: (id: string) => void;
  onClientSecretChange: (secret: string) => void;
  onCustomRedirectUrlChange: (url: string) => void;
  onSuccess: (connectionId: string, oauthUrl?: string) => void;
  onCancel: () => void;
}

function getDefaultRedirectUrl(): string {
  return `${window.location.origin}?oauth_return=true`;
}

export function SourceConfigView({
  collectionId,
  collectionName,
  sourceShortName,
  sourceName,
  connectionName,
  authMode,
  authFields,
  configFields,
  useCustomOAuth,
  clientId,
  clientSecret,
  onBack,
  onConnectionNameChange,
  onAuthModeChange,
  onAuthFieldChange,
  onConfigFieldChange,
  onUseCustomOAuthChange,
  onClientIdChange,
  onClientSecretChange,
  onSuccess,
  onCancel,
}: SourceConfigViewProps) {
  const isDark = useIsDark();
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const queryClient = useQueryClient();

  const [oauthUrl, setOauthUrl] = useState<string | null>(null);

  const { data: sourceDetails, isLoading: isLoadingSource } = useQuery({
    queryKey: ["source", organization?.id, sourceShortName],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSource(token, organization!.id, sourceShortName);
    },
    enabled: !!organization && !!sourceShortName,
  });

  const availableAuthMethods = useMemo((): AuthMode[] => {
    if (!sourceDetails?.auth_methods) return [];

    const methods: AuthMode[] = [];

    if (sourceDetails.auth_methods.includes("direct")) {
      methods.push("direct_auth");
    }

    if (
      sourceDetails.auth_methods.includes("oauth_browser") ||
      sourceDetails.auth_methods.includes("oauth_token")
    ) {
      methods.push("oauth2");
    }

    return methods;
  }, [sourceDetails]);

  useEffect(() => {
    if (sourceDetails && !authMode && availableAuthMethods.length > 0) {
      if (availableAuthMethods.includes("direct_auth")) {
        onAuthModeChange("direct_auth");
      } else if (availableAuthMethods.includes("oauth2")) {
        onAuthModeChange("oauth2");
        if (sourceDetails.requires_byoc) {
          onUseCustomOAuthChange(true);
        }
      }
    }
  }, [
    sourceDetails,
    authMode,
    availableAuthMethods,
    onAuthModeChange,
    onUseCustomOAuthChange,
  ]);

  const createMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();

      let authentication: CreateSourceConnectionAuth = {};

      if (authMode === "direct_auth") {
        authentication = { credentials: authFields };
      } else if (authMode === "oauth2") {
        authentication = {
          redirect_uri: getDefaultRedirectUrl(),
        };

        if (sourceDetails?.requires_byoc || useCustomOAuth) {
          authentication.client_id = clientId;
          authentication.client_secret = clientSecret;
        }
      }

      const config: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(configFields)) {
        if (value && (Array.isArray(value) ? value.length > 0 : value !== "")) {
          config[key] = value;
        }
      }

      return createSourceConnection(token, organization!.id, {
        name: connectionName.trim(),
        description: `${sourceName} connection for ${collectionName}`,
        short_name: sourceShortName,
        readable_collection_id: collectionId,
        authentication,
        config: Object.keys(config).length > 0 ? config : undefined,
        sync_immediately: authMode === "direct_auth",
        redirect_url: getDefaultRedirectUrl(),
      });
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sourceConnections.list(
          organization!.id,
          collectionId
        ),
      });

      const authUrl = result.auth?.auth_url;
      if (authUrl) {
        setOauthUrl(authUrl);
        onSuccess(result.id, authUrl);
      } else {
        toast.success("Source connected successfully!");
        onSuccess(result.id);
      }
    },
    onError: (error: Error) => {
      toast.error("Failed to create connection", {
        description: error.message,
      });
    },
  });

  const isFormValid = useMemo(() => {
    const trimmedName = connectionName.trim();
    if (!trimmedName || trimmedName.length < 4 || trimmedName.length > 42) {
      return false;
    }

    if (authMode === "direct_auth" && sourceDetails?.auth_fields?.fields) {
      const requiredFields = sourceDetails.auth_fields.fields.filter(
        (f) => f.required
      );
      for (const field of requiredFields) {
        if (!authFields[field.name]?.trim()) {
          return false;
        }
      }
    }

    if (authMode === "oauth2") {
      if (sourceDetails?.requires_byoc || useCustomOAuth) {
        if (!clientId.trim() || !clientSecret.trim()) {
          return false;
        }
      }
    }

    if (sourceDetails?.config_fields?.fields) {
      const requiredConfigFields = sourceDetails.config_fields.fields.filter(
        (f) => f.required
      );
      for (const field of requiredConfigFields) {
        const value = configFields[field.name];
        if (Array.isArray(value)) {
          if (value.length === 0) return false;
        } else if (!value?.trim()) {
          return false;
        }
      }
    }

    return true;
  }, [
    connectionName,
    authMode,
    authFields,
    configFields,
    sourceDetails,
    useCustomOAuth,
    clientId,
    clientSecret,
  ]);

  const handleSubmit = useCallback(() => {
    if (!isFormValid) return;
    createMutation.mutate();
  }, [isFormValid, createMutation]);

  if (oauthUrl) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex-1 overflow-auto p-6">
          <SourceAuthenticationView
            sourceName={sourceName}
            sourceShortName={sourceShortName}
            authenticationUrl={oauthUrl}
          />
        </div>
        <div className="border-t border-gray-200 px-6 py-4 dark:border-gray-800">
          <button
            onClick={onCancel}
            className="text-sm font-medium text-gray-600 transition-colors hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  if (isLoadingSource) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="flex items-center gap-2">
            <img
              src={getAppIconUrl(sourceShortName, isDark ? "dark" : "light")}
              alt={sourceName}
              className="h-6 w-6 rounded"
            />
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Configure {sourceName}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Set up your connection settings
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Form content */}
      <div className="flex-1 overflow-auto px-6 py-6">
        <div className="space-y-6">
          {/* Connection name */}
          <div className="space-y-2">
            <Label className="text-xs tracking-wider text-gray-500 uppercase dark:text-gray-400">
              Connection Name
            </Label>
            <Input
              value={connectionName}
              onChange={(e) => onConnectionNameChange(e.target.value)}
              placeholder="Enter connection name"
              className="border-gray-200 bg-white placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:placeholder:text-gray-500"
            />
            {connectionName &&
              (connectionName.length < 4 || connectionName.length > 42) && (
                <p className="text-xs text-amber-500">
                  Name must be between 4 and 42 characters
                </p>
              )}
          </div>

          {/* Auth method selection */}
          {availableAuthMethods.length > 1 && (
            <AuthMethodSelector
              availableAuthMethods={availableAuthMethods}
              selectedAuthMode={authMode}
              onAuthModeChange={onAuthModeChange}
            />
          )}

          {/* Direct auth fields */}
          {authMode === "direct_auth" && sourceDetails?.auth_fields?.fields && (
            <DirectAuthFields
              fields={sourceDetails.auth_fields.fields}
              values={authFields}
              onChange={onAuthFieldChange}
            />
          )}

          {/* OAuth settings */}
          {authMode === "oauth2" && (
            <OAuthSettings
              sourceShortName={sourceShortName}
              sourceName={sourceName}
              requiresByoc={sourceDetails?.requires_byoc ?? false}
              useCustomOAuth={useCustomOAuth}
              clientId={clientId}
              clientSecret={clientSecret}
              redirectUrl={getDefaultRedirectUrl()}
              onUseCustomOAuthChange={onUseCustomOAuthChange}
              onClientIdChange={onClientIdChange}
              onClientSecretChange={onClientSecretChange}
            />
          )}

          {/* Config fields */}
          {sourceDetails?.config_fields?.fields &&
            sourceDetails.config_fields.fields.length > 0 && (
              <ConfigFields
                fields={sourceDetails.config_fields.fields}
                values={configFields}
                onChange={onConfigFieldChange}
              />
            )}
        </div>
      </div>

      {/* Footer with actions */}
      <div className="flex items-center justify-between border-t border-gray-200 px-6 py-4 dark:border-gray-800">
        <button
          onClick={onCancel}
          className="text-sm font-medium text-gray-600 transition-colors hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
        >
          Cancel
        </button>

        <Button
          onClick={handleSubmit}
          disabled={!isFormValid || createMutation.isPending}
          className={cn(
            "min-w-[100px]",
            isFormValid && !createMutation.isPending
              ? "bg-blue-600 text-white hover:bg-blue-700"
              : ""
          )}
        >
          {createMutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Creating...
            </>
          ) : (
            "Create"
          )}
        </Button>
      </div>
    </div>
  );
}

interface AuthMethodSelectorProps {
  availableAuthMethods: AuthMode[];
  selectedAuthMode: AuthMode | null;
  onAuthModeChange: (mode: AuthMode) => void;
}

function AuthMethodSelector({
  availableAuthMethods,
  selectedAuthMode,
  onAuthModeChange,
}: AuthMethodSelectorProps) {
  return (
    <div className="space-y-2">
      <Label className="text-xs tracking-wider text-gray-500 uppercase dark:text-gray-400">
        Authentication Method
      </Label>
      <div className="flex gap-2">
        {availableAuthMethods.includes("direct_auth") && (
          <button
            onClick={() => onAuthModeChange("direct_auth")}
            className={cn(
              "flex-1 rounded-lg border px-4 py-2 text-sm font-medium transition-colors",
              selectedAuthMode === "direct_auth"
                ? "border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400"
                : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:border-gray-600"
            )}
          >
            API Key / Credentials
          </button>
        )}
        {availableAuthMethods.includes("oauth2") && (
          <button
            onClick={() => onAuthModeChange("oauth2")}
            className={cn(
              "flex-1 rounded-lg border px-4 py-2 text-sm font-medium transition-colors",
              selectedAuthMode === "oauth2"
                ? "border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400"
                : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:border-gray-600"
            )}
          >
            OAuth
          </button>
        )}
      </div>
    </div>
  );
}
