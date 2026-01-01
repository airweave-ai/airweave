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
        className,
      )}
    >
      <div className="size-16 rounded-full bg-muted flex items-center justify-center mb-4">
        {React.isValidElement(icon)
          ? React.cloneElement(
              icon as React.ReactElement<{ className?: string }>,
              {
                className: cn(
                  "size-8 text-muted-foreground",
                  (icon as React.ReactElement<{ className?: string }>).props
                    ?.className,
                ),
              },
            )
          : icon}
      </div>
      <h2 className="text-lg font-semibold mb-2">{title}</h2>
      <p className="text-muted-foreground max-w-sm">{description}</p>
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}

export { EmptyState, type EmptyStateProps };
