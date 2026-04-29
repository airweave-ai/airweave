import * as React from 'react';
import { IconX } from '@tabler/icons-react';

import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';

type AppDialogCloseButtonProps = Omit<
  React.ComponentProps<typeof Button>,
  'type' | 'variant' | 'size' | 'children'
>;

function AppDialogCloseButton({
  className,
  ...props
}: AppDialogCloseButtonProps) {
  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      className={cn(
        'bg-foreground/5 text-foreground hover:bg-foreground/10',
        className,
      )}
      {...props}
    >
      <IconX className="size-4" />
      <span className="sr-only">Close dialog</span>
    </Button>
  );
}

export { AppDialogCloseButton };
