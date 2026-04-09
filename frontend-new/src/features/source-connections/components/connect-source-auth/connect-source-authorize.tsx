import * as React from 'react';
import { IconArrowUpRight, IconCheck, IconCopy } from '@tabler/icons-react';
import {
  ConnectSourcePrimaryActionButton,
  ConnectSourceStepLayoutActions,
  ConnectSourceStepLayoutContent,
} from '../connect-source-step-layout';
import { SourceIcon } from '../source-icon';
import { ConnectSourceAuthError } from './connect-source-auth-error';
import type { SourceConnection } from '@/shared/api';
import { useCopyToClipboard } from '@/shared/hooks/use-copy-to-clipboard';
import { Button } from '@/shared/ui/button';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from '@/shared/ui/input-group';
import { Separator } from '@/shared/ui/separator';

interface ConnectSourceAuthorizeProps {
  onBack: () => void;
  sourceConnection: SourceConnection;
  sourceConnectionId: string;
  sourceName: string;
  sourceShortName: string;
}

export function ConnectSourceAuthorize({
  onBack,
  sourceConnection,
  sourceConnectionId,
  sourceName,
  sourceShortName,
}: ConnectSourceAuthorizeProps) {
  const authUrl = sourceConnection.auth.auth_url;
  const authUrlExpiresAt = sourceConnection.auth.auth_url_expires ?? null;

  if (authUrl) {
    return (
      <AuthorizeReadyCard
        authUrl={authUrl}
        authUrlExpiresAt={authUrlExpiresAt}
        onBack={onBack}
        sourceName={sourceName}
        sourceShortName={sourceShortName}
      />
    );
  }

  return (
    <ConnectSourceAuthError
      description={
        <>
          <p>
            Your {sourceName} authorization expired or was revoked.
            <br />
            You need to re-authorize to complete the connection.
          </p>
        </>
      }
      hints={[
        'You took too long to complete authorization',
        `Access was revoked in your ${sourceName} settings`,
        'The authorization window expired (10 min limit)',
      ]}
      onBack={onBack}
      sourceConnectionId={sourceConnectionId}
      sourceName={sourceName}
      title="Authorization failed"
    />
  );
}

function AuthorizeReadyCard({
  authUrl,
  authUrlExpiresAt,
  onBack,
  sourceName,
  sourceShortName,
}: {
  authUrl: string;
  authUrlExpiresAt: string | null;
  onBack: () => void;
  sourceName: string;
  sourceShortName: string;
}) {
  const { copied, copy } = useCopyToClipboard();
  const openAuthorization = React.useCallback(
    () => window.location.assign(authUrl),
    [authUrl],
  );
  const expiresText = React.useMemo(
    () =>
      authUrlExpiresAt
        ? `Link expires ${getRelativeExpirationLabel(authUrlExpiresAt)}.`
        : 'Link expires in 10 minutes.',
    [authUrlExpiresAt],
  );

  return (
    <>
      <ConnectSourceStepLayoutContent>
        <div className="space-y-2">
          <p className="text-sm font-medium text-foreground">
            Authorize to complete the connection
          </p>
          <InputGroup className="h-8 rounded-md border-border bg-background">
            <InputGroupInput
              readOnly
              value={authUrl}
              onFocus={(event) => event.currentTarget.select()}
              className="px-2.5 font-mono text-sm text-muted-foreground"
            />
            <InputGroupAddon
              align="inline-end"
              className="h-full gap-0 border-l border-input p-0"
            >
              <InputGroupButton
                variant="ghost"
                size="sm"
                className="h-full rounded-none rounded-r-md px-2.5 text-xs text-foreground"
                onClick={() => void copy(authUrl)}
              >
                {copied ? (
                  <IconCheck className="size-3.5" />
                ) : (
                  <IconCopy className="size-3.5" />
                )}
                {copied ? 'Copied' : 'Copy'}
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
          <p className="text-sm text-muted-foreground">
            Your app should redirect users to this URL. {expiresText}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Separator className="flex-1" />
          <span className="font-mono text-sm text-foreground/50 uppercase">
            or
          </span>
          <Separator className="flex-1" />
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <p className="text-base font-medium text-foreground">
              Connect your own {sourceName} Account
            </p>
            <p className="text-sm text-muted-foreground">
              Testing? Authorize with your own {sourceName} account to verify
              the connection works.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="shrink-0"
            onClick={openAuthorization}
          >
            <SourceIcon
              className="size-3.5"
              name={sourceName}
              shortName={sourceShortName}
            />
            Connect Now
            <IconArrowUpRight className="size-3.5" />
          </Button>
        </div>
      </ConnectSourceStepLayoutContent>

      <ConnectSourceStepLayoutActions onBack={onBack}>
        <ConnectSourcePrimaryActionButton
          type="button"
          icon={<IconArrowUpRight className="size-4" />}
          onClick={openAuthorization}
        >
          Open {sourceName} Authorization
        </ConnectSourcePrimaryActionButton>
      </ConnectSourceStepLayoutActions>
    </>
  );
}

function getRelativeExpirationLabel(expiresAt: string) {
  const expirationTime = new Date(expiresAt).getTime();
  const remainingMinutes = Math.max(
    1,
    Math.ceil((expirationTime - Date.now()) / 60000),
  );

  return remainingMinutes <= 1
    ? 'in 1 minute'
    : `in ${remainingMinutes} minutes`;
}
