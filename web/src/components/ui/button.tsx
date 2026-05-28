import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-semibold ring-offset-background transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 cursor-pointer select-none active:scale-[0.98]",
  {
    variants: {
      variant: {
        default:
          "border border-primary/30 bg-[linear-gradient(135deg,var(--color-primary),var(--color-accent),oklch(0.66_0.19_286))] text-primary-foreground shadow-[0_10px_28px_color-mix(in_oklch,var(--color-primary)_22%,transparent)] hover:brightness-110 hover:shadow-[0_14px_36px_color-mix(in_oklch,var(--color-primary)_30%,transparent)]",
        destructive:
          "border border-destructive/25 bg-destructive text-destructive-foreground shadow-[0_10px_26px_color-mix(in_oklch,var(--color-destructive)_18%,transparent)] hover:bg-destructive/90",
        outline:
          "border border-input bg-card/50 shadow-sm backdrop-blur hover:border-primary/35 hover:bg-primary/10 hover:text-foreground hover:shadow-[0_0_22px_color-mix(in_oklch,var(--color-primary)_14%,transparent)]",
        secondary:
          "border border-border/80 bg-secondary/75 text-secondary-foreground shadow-sm backdrop-blur hover:border-accent/40 hover:bg-secondary",
        ghost: "hover:bg-accent/70 hover:text-accent-foreground hover:shadow-[inset_0_0_0_1px_var(--color-border)]",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-10 rounded-lg px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
