import type { ReactNode } from 'react';
import { cn } from '@/shared/tailwind/cn';
import { Separator } from '@/shared/ui/separator';
import { TooltipContent } from '@/shared/ui/tooltip';

type CollectionTooltipContentProps = Omit<
  React.ComponentProps<typeof TooltipContent>,
  'title'
> & {
  title: ReactNode;
  description: ReactNode;
};

export function CollectionTooltipContent({
  title,
  description,
  className,
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
      <p className="text-center text-balance text-muted-foreground">
        {description}
      </p>
    </TooltipContent>
  );
}
