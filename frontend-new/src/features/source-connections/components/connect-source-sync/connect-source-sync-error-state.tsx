import { IconAlertCircleFilled } from '@tabler/icons-react';
import { ChevronDown } from 'lucide-react';
import {
  ConnectSourceBackActionButton,
  ConnectSourcePrimaryActionButton,
  ConnectSourceStepLayoutActions,
  ConnectSourceStepLayoutContent,
} from '../connect-source-step-layout';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/shared/ui/collapsible';
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert';
import { Separator } from '@/shared/ui/separator';

const CONTACT_SUPPORT_MAILTO = 'mailto:hello@airweave.ai';

interface ConnectSourceSyncErrorStateProps {
  description: React.ReactNode;
  details?: string;
  onClose: () => void;
  primaryAction?: React.ReactNode;
  timestamp?: string;
  title: string;
}

export function ConnectSourceSyncErrorState({
  description,
  details,
  onClose,
  primaryAction,
  timestamp,
  title,
}: ConnectSourceSyncErrorStateProps) {
  return (
    <>
      <ConnectSourceStepLayoutContent className="space-y-6">
        <Alert
          variant="destructive"
          className="gap-3 gap-y-1 rounded-lg border-border p-3"
        >
          <IconAlertCircleFilled className="size-4" />
          <AlertTitle className="truncate text-sm font-semibold">
            {title}
          </AlertTitle>
          <AlertDescription className="space-y-3 font-mono text-sm leading-5">
            {timestamp ? (
              <div className="text-destructive">{timestamp}</div>
            ) : null}

            <Separator />

            <div className="text-destructive-foreground">{description}</div>
          </AlertDescription>
        </Alert>

        {details ? (
          <Collapsible className="group">
            <Alert
              variant="destructive"
              className="gap-3 gap-y-0 rounded-lg border-border py-0 pr-0 pl-3"
            >
              <IconAlertCircleFilled className="mt-3 size-4" />
              <CollapsibleTrigger className="col-start-2 flex w-full items-center justify-between gap-3 py-3 pr-3 text-left">
                <AlertTitle className="text-sm font-semibold">
                  Error details
                </AlertTitle>

                <ChevronDown className="size-3.5 shrink-0 text-accent-foreground opacity-50 transition-transform group-data-[state=open]:rotate-180" />
              </CollapsibleTrigger>

              <CollapsibleContent className="col-start-2 pb-3">
                <Separator className="mb-3" />
                <AlertDescription className="font-mono text-sm leading-5 whitespace-pre-wrap text-destructive-foreground">
                  {details}
                </AlertDescription>
              </CollapsibleContent>
            </Alert>
          </Collapsible>
        ) : null}
      </ConnectSourceStepLayoutContent>

      <ConnectSourceStepLayoutActions
        backAction={
          <ConnectSourceBackActionButton asChild>
            <a href={CONTACT_SUPPORT_MAILTO}>Contact support</a>
          </ConnectSourceBackActionButton>
        }
      >
        {primaryAction ?? (
          <ConnectSourcePrimaryActionButton onClick={onClose}>
            Close
          </ConnectSourcePrimaryActionButton>
        )}
      </ConnectSourceStepLayoutActions>
    </>
  );
}
