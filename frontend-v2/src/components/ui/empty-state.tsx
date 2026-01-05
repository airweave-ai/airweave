import * as React from "react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  children?: React.ReactNode;
  className?: string;
}

function EmptyState({
  icon,
  title,
  description,
  children,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 text-center",
        className
      )}
    >
      <div className="flex size-16 items-center justify-center">
        {React.isValidElement(icon)
          ? React.cloneElement(
              icon as React.ReactElement<{ className?: string }>,
              {
                className: cn(
                  "size-8 text-muted-foreground",
                  (icon as React.ReactElement<{ className?: string }>).props
                    ?.className
                ),
              }
            )
          : icon}
      </div>
      <h2 className="text-muted-foreground mb-2 font-mono font-medium uppercase opacity-70">
        {title}
      </h2>
      <p className="text-muted-foreground max-w-sm text-sm">{description}</p>
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}

export { EmptyState, type EmptyStateProps };
