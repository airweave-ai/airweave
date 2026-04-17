import type { ReactNode } from 'react';
import { cn } from '@/shared/tailwind/cn';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/shared/ui/empty';
import { Spinner } from '@/shared/ui/spinner';

type LoadingStateProps = Omit<React.ComponentProps<'div'>, 'title'> & {
  action?: ReactNode;
  description?: ReactNode;
  title?: ReactNode;
};

export function LoadingState({
  action,
  className,
  description = 'You can continue working while this completes.',
  title = 'Loading...',
  ...props
}: LoadingStateProps) {
  return (
    <Empty className={cn('size-full min-h-0', className)} {...props}>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Spinner className="size-4" />
        </EmptyMedia>

        <EmptyTitle className="text-base">{title}</EmptyTitle>

        {description ? (
          <EmptyDescription className="font-mono">
            {description}
          </EmptyDescription>
        ) : null}
      </EmptyHeader>

      {action ? <EmptyContent>{action}</EmptyContent> : null}
    </Empty>
  );
}
