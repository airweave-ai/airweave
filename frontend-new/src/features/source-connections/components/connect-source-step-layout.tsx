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
    <FlowDialogMain
      className={cn('overflow-visible lg:overflow-hidden', className)}
      {...props}
    >
      <div className="flex min-h-0 max-w-full flex-col gap-6 lg:h-full">
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
  backAction,
  children,
  className,
  ...props
}: React.ComponentProps<'div'> & {
  backAction: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className={cn('shrink-0', className)} {...props}>
      <div className="flex flex-col gap-2 sm:flex-row sm:justify-between">
        <div className="w-full sm:max-w-55">{backAction}</div>

        <div className="w-full sm:max-w-130">{children}</div>
      </div>
    </div>
  );
}

export interface ConnectSourceBackActionButtonProps extends React.ComponentProps<
  typeof Button
> {}

export function ConnectSourceBackActionButton({
  asChild = false,
  children,
  className,
  size = 'lg',
  type = 'button',
  variant = 'ghost',
  ...props
}: ConnectSourceBackActionButtonProps) {
  return (
    <Button
      asChild={asChild}
      type={asChild ? undefined : type}
      size={size}
      variant={variant}
      className={cn('w-full', className)}
      {...props}
    >
      {children}
    </Button>
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
  return (
    <FlowDialogAside
      className={cn(
        'min-h-0 overflow-visible px-0 py-0 lg:w-112 lg:overflow-hidden',
        className,
      )}
      {...props}
    />
  );
}
