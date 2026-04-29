import type * as React from 'react';

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/shared/ui/card';

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
      <CardHeader className="gap-1.5 px-4 pt-4 pb-0">
        <CardTitle className="text-xl leading-7 font-semibold">
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>

      <CardContent className="p-4">{children}</CardContent>

      <CardFooter className="justify-between gap-4 bg-transparent">
        {footer}
      </CardFooter>
    </Card>
  );
}

export { AccountFormCard };
