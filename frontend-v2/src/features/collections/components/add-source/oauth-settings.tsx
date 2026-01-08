/**
 * OAuthSettings - OAuth configuration form fields
 */

import { ExternalLink, HelpCircle, Info } from "lucide-react";

import { Label } from "@/components/ui/label";
import { ValidatedInput } from "@/components/validated-input";
import { cn } from "@/lib/utils";
import { clientIdValidation, clientSecretValidation } from "@/lib/validation";

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
  const docsUrl = `https://docs.airweave.ai/docs/connectors/${sourceShortName.replace(/_/g, "-")}`;

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2 rounded-lg bg-blue-50 p-3 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400">
        <Info className="mt-0.5 h-4 w-4 flex-shrink-0" />
        <p className="text-sm">
          {sourceName} requires you to provide your own OAuth application
          credentials. You&apos;ll need to create an OAuth app in {sourceName}
          &apos;s developer console.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <HelpCircle className="text-muted-foreground h-4 w-4" />
        <span className="text-muted-foreground text-sm">
          Need help setting up OAuth?
        </span>
        <a
          href={docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary inline-flex items-center gap-1 text-sm font-medium hover:underline"
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
              useCustomOAuth ? "bg-primary" : "bg-muted"
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
        <span className="text-muted-foreground text-sm">
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
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label className="text-sm font-medium">
          Client ID {required && <span className="text-destructive">*</span>}
        </Label>
        <ValidatedInput
          value={clientId}
          onChange={onClientIdChange}
          validation={clientIdValidation}
          placeholder={required ? "Your OAuth Client ID" : "Client ID"}
        />
      </div>
      <div className="space-y-1.5">
        <Label className="text-sm font-medium">
          Client Secret{" "}
          {required && <span className="text-destructive">*</span>}
        </Label>
        <ValidatedInput
          type="password"
          value={clientSecret}
          onChange={onClientSecretChange}
          validation={clientSecretValidation}
          placeholder={required ? "Your OAuth Client Secret" : "Client Secret"}
        />
      </div>
    </div>
  );
}

interface RedirectUrlDisplayProps {
  url: string;
}

function RedirectUrlDisplay({ url }: RedirectUrlDisplayProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Label className="text-muted-foreground text-xs tracking-wider uppercase">
          Redirect URL
        </Label>
        <Info className="text-muted-foreground h-3 w-3" />
      </div>
      <div className="bg-muted text-muted-foreground rounded-lg border px-3 py-2 font-mono text-xs">
        {url}
      </div>
    </div>
  );
}
