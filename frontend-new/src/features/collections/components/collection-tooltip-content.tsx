import type { ReactNode } from 'react';
import { cn } from '@/shared/tailwind/cn';
import { Separator } from '@/shared/ui/separator';
import { TooltipContent } from '@/shared/ui/tooltip';

type CollectionTooltipContentProps = Omit<
  React.ComponentProps<typeof TooltipContent>,
  'title'
> & {
  description: ReactNode;
  footer?: ReactNode;
  title: ReactNode;
};

export function CollectionTooltipContent({
  description,
  footer,
  className,
  title,
  ...props
}: CollectionTooltipContentProps) {
  return (
    <TooltipContent
      className={cn(
        'flex max-w-50 flex-col border bg-secondary px-3 py-1.5 text-foreground [&_svg]:hidden!',
        className,
      )}
      {...props}
    >
      <p>{title}</p>
      <Separator className="w-full" />
      <div className="space-y-0.5 text-center text-balance text-muted-foreground">
        <p>{description}</p>
        {footer ? <p>{footer}</p> : null}
      </div>
    </TooltipContent>
  );
}
