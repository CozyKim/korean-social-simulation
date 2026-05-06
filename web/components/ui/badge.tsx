import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
  {
    variants: {
      variant: {
        default: "border-transparent bg-zinc-700 text-zinc-50",
        positive: "border-transparent bg-emerald-600/30 text-emerald-300",
        negative: "border-transparent bg-red-600/30 text-red-300",
        neutral: "border-transparent bg-zinc-600/30 text-zinc-200",
        mixed: "border-transparent bg-amber-600/30 text-amber-300",
        outline: "border-zinc-700 text-zinc-300",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { badgeVariants };
