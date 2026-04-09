import * as React from 'react';
import {
  IconArrowRight,
  IconCheck,
  IconCopy,
  IconExclamationCircle,
  IconRefresh,
} from '@tabler/icons-react';
import type { ConnectSourceAuthState } from './connect-source-auth-state';
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert';
import { Button } from '@/shared/ui/button';
import { Input } from '@/shared/ui/input';
import { Spinner } from '@/shared/ui/spinner';

interface ConnectSourceAuthProps {
  onClose: () => void;
  onConnectNow: () => void;
  onReauthorize: () => Promise<void>;
  sourceName: string;
  state: ConnectSourceAuthState;
}

export function ConnectSourceAuth({
  onClose,
  onConnectNow,
  onReauthorize,
  sourceName,
  state,
}: ConnectSourceAuthProps) {
  switch (state.kind) {
    case 'loading-connection':
      return (
        <ConnectSourceAuthStatusCard
          description="Loading the latest source connection state."
          title="Loading authorization details"
        >
          <Spinner className="size-5 text-muted-foreground" />
        </ConnectSourceAuthStatusCard>
      );
    case 'verifying-return':
      return (
        <ConnectSourceAuthStatusCard
          description="Airweave is verifying the callback and preparing the next step."
          title="Finishing authorization"
        >
          <Spinner className="size-5 text-muted-foreground" />
        </ConnectSourceAuthStatusCard>
      );
    case 'authorize-ready':
      return (
        <AuthorizeReadyCard
          authUrl={state.authUrl}
          authUrlExpiresAt={state.authUrlExpiresAt}
          onClose={onClose}
          onConnectNow={onConnectNow}
          sourceName={sourceName}
        />
      );
    case 'callback-invalid':
      return (
        <MessageCard
          description="The OAuth callback URL is incomplete or no longer valid for this source connection. Start again from the auth link shown in this step."
          onClose={onClose}
          title="Could not resume the OAuth callback"
          variant="destructive"
        />
      );
    case 'reauthorize-required':
      return (
        <ReconnectCard
          actionLabel={`Re-authorize ${sourceName}`}
          description={`The authorization link for ${sourceName} is no longer available. Create a fresh link, then continue from this screen.`}
          onClose={onClose}
          onReauthorize={onReauthorize}
          title={`Re-authorize ${sourceName}`}
        />
      );
    case 'reauthorizing':
      return (
        <ReconnectCard
          actionLabel={`Re-authorize ${sourceName}`}
          description={`Creating a fresh authorization link for ${sourceName}.`}
          isPending
          onClose={onClose}
          onReauthorize={onReauthorize}
          title={`Re-authorize ${sourceName}`}
        />
      );
    case 'reauthorize-failed':
      return (
        <ReconnectCard
          actionLabel={`Try re-authorizing ${sourceName}`}
          description={state.message}
          onClose={onClose}
          onReauthorize={onReauthorize}
          title={`Could not re-authorize ${sourceName}`}
          variant="destructive"
        />
      );
    case 'blocking-missing-claim-token':
      return (
        <MessageCard
          description="Authorization finished, but this browser no longer has the claim token needed to finish setup. Return to the original browser window that started the flow."
          onClose={onClose}
          title="Finish setup from the original browser"
          variant="destructive"
        />
      );
    case 'verify-failed':
      return (
        <MessageCard
          description={state.message}
          onClose={onClose}
          title="Could not verify the callback"
          variant="destructive"
        />
      );
    case 'unknown-authenticated':
      return (
        <MessageCard
          description="This connection is already authenticated, but this authorize URL no longer has the callback context needed to safely resume setup."
          onClose={onClose}
          title="Authorization cannot be resumed here"
        />
      );
    case 'connection-error':
      return (
        <MessageCard
          description={state.message}
          onClose={onClose}
          title="Could not load authorization state"
          variant="destructive"
        />
      );
  }
}

function AuthorizeReadyCard({
  authUrl,
  authUrlExpiresAt,
  onClose,
  onConnectNow,
  sourceName,
}: {
  authUrl: string;
  authUrlExpiresAt: string | null;
  onClose: () => void;
  onConnectNow: () => void;
  sourceName: string;
}) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = React.useCallback(async () => {
    await navigator.clipboard.writeText(authUrl);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }, [authUrl]);

  const expiresText = authUrlExpiresAt
    ? `Expires ${new Date(authUrlExpiresAt).toLocaleString()}.`
    : 'Link expires in about 10 minutes.';

  return (
    <div className="space-y-6 rounded-xl border border-border bg-foreground/[0.03] p-6">
      <div className="space-y-2">
        <p className="text-sm font-medium text-foreground">
          Share the authorization link
        </p>
        <p className="text-sm text-muted-foreground">
          Send this link to someone with access to {sourceName}. Keep this
          window open to finish setup after they authorize. {expiresText}
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <Input
          readOnly
          value={authUrl}
          className="h-10 flex-1 font-mono text-xs"
        />
        <Button
          type="button"
          variant="outline"
          className="sm:self-start"
          onClick={() => void handleCopy()}
        >
          {copied ? (
            <IconCheck className="size-4" />
          ) : (
            <IconCopy className="size-4" />
          )}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>

      <div className="flex flex-col gap-2 rounded-lg border border-border bg-background p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">Connect now</p>
          <p className="text-sm text-muted-foreground">
            Use your own {sourceName} account to authorize in this browser.
          </p>
        </div>
        <Button type="button" size="lg" onClick={onConnectNow}>
          Connect now
          <IconArrowRight className="size-4" />
        </Button>
      </div>

      <div className="flex justify-end">
        <Button type="button" variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>
    </div>
  );
}

function ReconnectCard({
  actionLabel,
  description,
  isPending = false,
  onClose,
  onReauthorize,
  title,
  variant = 'default',
}: {
  actionLabel: string;
  description: string;
  isPending?: boolean;
  onClose: () => void;
  onReauthorize: () => Promise<void>;
  title: string;
  variant?: 'default' | 'destructive';
}) {
  return (
    <div className="space-y-4 rounded-xl border border-border bg-foreground/[0.03] p-6">
      <Alert variant={variant}>
        <IconRefresh className="size-4" />
        <AlertTitle>{title}</AlertTitle>
        <AlertDescription>{description}</AlertDescription>
      </Alert>

      <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="ghost" onClick={onClose}>
          Close
        </Button>
        <Button
          type="button"
          onClick={() => void onReauthorize()}
          disabled={isPending}
        >
          {isPending ? (
            <Spinner className="size-4" />
          ) : (
            <IconRefresh className="size-4" />
          )}
          {actionLabel}
        </Button>
      </div>
    </div>
  );
}

function MessageCard({
  description,
  onClose,
  title,
  variant = 'default',
}: {
  description: string;
  onClose: () => void;
  title: string;
  variant?: 'default' | 'destructive';
}) {
  return (
    <div className="space-y-4 rounded-xl border border-border bg-foreground/[0.03] p-6">
      <Alert variant={variant}>
        <IconExclamationCircle className="size-4" />
        <AlertTitle>{title}</AlertTitle>
        <AlertDescription>{description}</AlertDescription>
      </Alert>

      <div className="flex justify-end">
        <Button type="button" variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>
    </div>
  );
}

function ConnectSourceAuthStatusCard({
  children,
  description,
  title,
}: React.PropsWithChildren<{
  description: string;
  title: string;
}>) {
  return (
    <div className="flex min-h-72 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-foreground/[0.03] p-6 text-center">
      {children}
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}
