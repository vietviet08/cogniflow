import * as React from "react";

import { cn } from "@/lib/utils";

interface PageWrapperProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  description?: string;
}

export function PageWrapper({
  title,
  description,
  children,
  className,
  ...props
}: PageWrapperProps) {
  return (
    <div className={cn("flex flex-col gap-6 p-6 md:p-8", className)} {...props}>
      {(title || description) && (
        <div className="flex flex-col gap-1">
          {title && (
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              {title}
            </h1>
          )}
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      {children}
    </div>
  );
}
