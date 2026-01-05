/**
 * OAuthSettings - OAuth configuration form fields
 */

import { ExternalLink, HelpCircle, Info } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useIsDark } from "@/hooks/use-is-dark";
import { cn } from "@/lib/utils";

interface OAuthSettingsProps {
  sourceShortName: string;
  sourceName: string;
  requiresByoc: boolean;
  useCustomOAuth: boolean;
  clientId: string;
  clientSecret: string;
  redirectUrl: string;
  onUseCustomOAuthChange: (use: boolean) => void;
  onClientIdChange: (id: string) => void;
  onClientSecretChange: (secret: string) => void;
}

export function OAuthSettings({
  sourceShortName,
  sourceName,
  requiresByoc,
  useCustomOAuth,
  clientId,
  clientSecret,
  redirectUrl,
  onUseCustomOAuthChange,
  onClientIdChange,
  onClientSecretChange,
}: OAuthSettingsProps) {
  return (
    <div className="space-y-4">
      {requiresByoc ? (
        <ByocOAuthFields
          sourceShortName={sourceShortName}
          sourceName={sourceName}
          clientId={clientId}
          clientSecret={clientSecret}
          onClientIdChange={onClientIdChange}
          onClientSecretChange={onClientSecretChange}
        />
      ) : (
        <OptionalCustomOAuth
          useCustomOAuth={useCustomOAuth}
          clientId={clientId}
          clientSecret={clientSecret}
          onUseCustomOAuthChange={onUseCustomOAuthChange}
          onClientIdChange={onClientIdChange}
          onClientSecretChange={onClientSecretChange}
        />
      )}

      <RedirectUrlDisplay url={redirectUrl} />
    </div>
  );
}

interface ByocOAuthFieldsProps {
  sourceShortName: string;
  sourceName: string;
  clientId: string;
  clientSecret: string;
  onClientIdChange: (id: string) => void;
  onClientSecretChange: (secret: string) => void;
}

function ByocOAuthFields({
  sourceShortName,
  sourceName,
  clientId,
  clientSecret,
  onClientIdChange,
  onClientSecretChange,
}: ByocOAuthFieldsProps) {
  const isDark = useIsDark();
  const docsUrl = `https://docs.airweave.ai/docs/connectors/${sourceShortName.replace(/_/g, "-")}`;

  return (
    <div className="space-y-4">
      <div
        className={cn(
          "flex items-start gap-2 rounded-lg p-3",
          isDark ? "bg-blue-900/20 text-blue-400" : "bg-blue-50 text-blue-600"
        )}
      >
        <Info className="mt-0.5 h-4 w-4 flex-shrink-0" />
        <p className="text-sm">
          {sourceName} requires you to provide your own OAuth application
          credentials. You&apos;ll need to create an OAuth app in {sourceName}
          &apos;s developer console.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <HelpCircle
          className={cn("h-4 w-4", isDark ? "text-gray-500" : "text-gray-400")}
        />
        <span
          className={cn("text-sm", isDark ? "text-gray-400" : "text-gray-600")}
        >
          Need help setting up OAuth?
        </span>
        <a
          href={docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
        >
          View documentation
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>

      <OAuthCredentialInputs
        clientId={clientId}
        clientSecret={clientSecret}
        onClientIdChange={onClientIdChange}
        onClientSecretChange={onClientSecretChange}
        required
      />
    </div>
  );
}

interface OptionalCustomOAuthProps {
  useCustomOAuth: boolean;
  clientId: string;
  clientSecret: string;
  onUseCustomOAuthChange: (use: boolean) => void;
  onClientIdChange: (id: string) => void;
  onClientSecretChange: (secret: string) => void;
}

function OptionalCustomOAuth({
  useCustomOAuth,
  clientId,
  clientSecret,
  onUseCustomOAuthChange,
  onClientIdChange,
  onClientSecretChange,
}: OptionalCustomOAuthProps) {
  const isDark = useIsDark();

  return (
    <div className="space-y-3">
      <label className="flex cursor-pointer items-center gap-3">
        <div className="relative">
          <input
            type="checkbox"
            checked={useCustomOAuth}
            onChange={(e) => onUseCustomOAuthChange(e.target.checked)}
            className="sr-only"
          />
          <div
            className={cn(
              "h-6 w-10 rounded-full transition-colors",
              useCustomOAuth
                ? "bg-blue-600"
                : isDark
                  ? "bg-gray-800"
                  : "bg-gray-200"
            )}
          >
            <div
              className={cn(
                "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white transition-transform",
                useCustomOAuth && "translate-x-4"
              )}
            />
          </div>
        </div>
        <span
          className={cn("text-sm", isDark ? "text-gray-400" : "text-gray-600")}
        >
          Use custom OAuth credentials
        </span>
      </label>

      {useCustomOAuth && (
        <div className="space-y-3 pl-13">
          <OAuthCredentialInputs
            clientId={clientId}
            clientSecret={clientSecret}
            onClientIdChange={onClientIdChange}
            onClientSecretChange={onClientSecretChange}
          />
        </div>
      )}
    </div>
  );
}

interface OAuthCredentialInputsProps {
  clientId: string;
  clientSecret: string;
  onClientIdChange: (id: string) => void;
  onClientSecretChange: (secret: string) => void;
  required?: boolean;
}

function OAuthCredentialInputs({
  clientId,
  clientSecret,
  onClientIdChange,
  onClientSecretChange,
  required,
}: OAuthCredentialInputsProps) {
  const isDark = useIsDark();

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label className="text-sm font-medium">
          Client ID {required && <span className="text-red-500">*</span>}
        </Label>
        <Input
          value={clientId}
          onChange={(e) => onClientIdChange(e.target.value)}
          placeholder={required ? "Your OAuth Client ID" : "Client ID"}
          className={cn(
            isDark
              ? "border-gray-700 bg-gray-800 placeholder:text-gray-500"
              : "border-gray-200 bg-white placeholder:text-gray-400"
          )}
        />
      </div>
      <div className="space-y-1.5">
        <Label className="text-sm font-medium">
          Client Secret {required && <span className="text-red-500">*</span>}
        </Label>
        <Input
          type="password"
          value={clientSecret}
          onChange={(e) => onClientSecretChange(e.target.value)}
          placeholder={required ? "Your OAuth Client Secret" : "Client Secret"}
          className={cn(
            isDark
              ? "border-gray-700 bg-gray-800 placeholder:text-gray-500"
              : "border-gray-200 bg-white placeholder:text-gray-400"
          )}
        />
      </div>
    </div>
  );
}

interface RedirectUrlDisplayProps {
  url: string;
}

function RedirectUrlDisplay({ url }: RedirectUrlDisplayProps) {
  const isDark = useIsDark();

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Label
          className={cn(
            "text-xs tracking-wider uppercase",
            isDark ? "text-gray-500" : "text-gray-400"
          )}
        >
          Redirect URL
        </Label>
        <Info
          className={cn("h-3 w-3", isDark ? "text-gray-600" : "text-gray-400")}
        />
      </div>
      <div
        className={cn(
          "rounded-lg border px-3 py-2 font-mono text-xs",
          isDark
            ? "border-gray-800 bg-gray-900/50 text-gray-500"
            : "border-gray-100 bg-gray-50 text-gray-400"
        )}
      >
        {url}
      </div>
    </div>
  );
}
