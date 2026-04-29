import type * as React from 'react';

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/shared/ui/card';
import { cn } from '@/shared/tailwind/cn';

type AccountFormCardProps = React.PropsWithChildren<{
  description: React.ReactNode;
  footer: React.ReactNode;
  title: React.ReactNode;
}>;

function AccountFormCard({
  children,
  description,
  footer,
  title,
}: AccountFormCardProps) {
  return (
    <Card className="gap-0 rounded-lg bg-foreground/5 py-0 shadow-xs">
      <CardHeader
        className={cn('gap-1.5 px-4 pt-4', children ? 'pb-0' : 'pb-4')}
      >
        <CardTitle className="text-xl leading-7 font-semibold">
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>

      {children ? <CardContent className="p-4">{children}</CardContent> : null}

      <CardFooter className="justify-between gap-4 bg-transparent">
        {footer}
      </CardFooter>
    </Card>
  );
}

export { AccountFormCard };
