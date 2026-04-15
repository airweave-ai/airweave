import { IconAlertCircleFilled } from '@tabler/icons-react';

import { Button } from '@/shared/ui/button';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/shared/ui/empty';
import { cn } from '@/shared/tailwind/cn';

type ErrorStateProps = Omit<React.ComponentProps<'div'>, 'title'> & {
  action?: React.ReactNode;
  description?: React.ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
  title?: React.ReactNode;
};

export function ErrorState({
  action,
  className,
  description = 'An unexpected error occurred while loading Airweave.',
  onRetry,
  retryLabel = 'Try again',
  title = "We couldn't load this page",
  ...props
}: ErrorStateProps) {
  return (
    <Empty className={cn('size-full min-h-0', className)} {...props}>
      <EmptyHeader>
        <EmptyMedia
          variant="icon"
          className="size-10 bg-destructive/10 text-destructive"
        >
          <IconAlertCircleFilled className="size-5" />
        </EmptyMedia>

        <EmptyTitle className="text-base text-destructive">{title}</EmptyTitle>
        <EmptyDescription className="font-mono text-destructive-foreground">
          {description}
        </EmptyDescription>
      </EmptyHeader>

      <EmptyContent>
        {action ??
          (onRetry ? (
            <Button type="button" variant="secondary" onClick={onRetry}>
              {retryLabel}
            </Button>
          ) : null)}
      </EmptyContent>
    </Empty>
  );
}
