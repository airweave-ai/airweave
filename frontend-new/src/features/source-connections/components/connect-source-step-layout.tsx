import * as React from 'react';
import { Slot } from 'radix-ui';
import { Button } from '@/shared/ui/button';
import { DialogDescription, DialogTitle } from '@/shared/ui/dialog';
import {
  FlowDialogAside,
  FlowDialogHeader,
  FlowDialogMain,
} from '@/shared/ui/flow-dialog';
import { Spinner } from '@/shared/ui/spinner';
import { cn } from '@/shared/tailwind/cn';

export function ConnectSourceStepDialogHeader({
  onClose,
  sourceName,
}: {
  onClose: () => void;
  sourceName: string;
}) {
  return (
    <FlowDialogHeader onClose={onClose}>
      <div className="min-w-0 space-y-1">
        <DialogTitle className="text-xl font-semibold text-foreground">
          Create Source Connection
        </DialogTitle>
        <DialogDescription className="font-mono text-sm text-muted-foreground">
          Make your {sourceName} content searchable for your agent.
        </DialogDescription>
      </div>
    </FlowDialogHeader>
  );
}

export function ConnectSourceStepLayoutMain({
  children,
  className,
  ...props
}: React.ComponentProps<typeof FlowDialogMain>) {
  return (
    <FlowDialogMain className={cn('overflow-hidden', className)} {...props}>
      <div className="flex h-full min-h-0 max-w-full flex-col gap-6">
        {children}
      </div>
    </FlowDialogMain>
  );
}

export function ConnectSourceStepLayoutContent({
  asChild = false,
  className,
  ...props
}: React.ComponentProps<'div'> & {
  asChild?: boolean;
}) {
  const Comp = asChild ? Slot.Root : 'div';

  return (
    <Comp
      className={cn(
        'min-h-0 flex-1 space-y-6 overflow-x-hidden overflow-y-auto',
        className,
      )}
      {...props}
    />
  );
}

export function ConnectSourceStepLayoutActions({
  backDisabled = false,
  backLabel = 'Back',
  children,
  className,
  onBack,
  ...props
}: React.ComponentProps<'div'> & {
  backDisabled?: boolean;
  backLabel?: string;
  children?: React.ReactNode;
  onBack: () => void;
}) {
  return (
    <div className={cn('shrink-0', className)} {...props}>
      <div className="flex flex-col gap-2 sm:flex-row sm:justify-between">
        <Button
          type="button"
          size="lg"
          variant="ghost"
          className="w-full sm:max-w-55"
          disabled={backDisabled}
          onClick={onBack}
        >
          {backLabel}
        </Button>

        <div className="w-full sm:max-w-130">{children}</div>
      </div>
    </div>
  );
}

export interface ConnectSourcePrimaryActionButtonProps extends React.ComponentProps<
  typeof Button
> {
  icon?: React.ReactNode;
  isLoading?: boolean;
}

export function ConnectSourcePrimaryActionButton({
  children,
  className,
  disabled,
  icon,
  isLoading = false,
  size = 'lg',
  type = 'button',
  ...props
}: ConnectSourcePrimaryActionButtonProps) {
  return (
    <Button
      type={type}
      size={size}
      className={cn('w-full', className)}
      disabled={disabled || isLoading}
      {...props}
    >
      {children}
      {isLoading ? <Spinner className="size-4" /> : icon}
    </Button>
  );
}

export function ConnectSourceStepLayoutAside({
  className,
  ...props
}: React.ComponentProps<typeof FlowDialogAside>) {
  return <FlowDialogAside className={cn('xl:w-112', className)} {...props} />;
}
