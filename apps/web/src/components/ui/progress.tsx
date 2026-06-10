import * as React from "react";
import { cn } from "@/lib/utils";

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number;
  max?: number;
  className?: string;
  indicatorClassName?: string;
}

const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ value, max = 100, className, indicatorClassName, ...props }, ref) => {
    const percentage = Math.min(100, Math.max(0, (value / max) * 100));

    return (
      <div
        ref={ref}
        className={cn(
          "relative h-2 w-full overflow-hidden rounded-full bg-primary/20",
          className,
        )}
        {...props}
      >
        <div
          className={cn(
            "h-full w-full flex-1 rounded-full bg-primary transition-all duration-300 ease-in-out",
            indicatorClassName,
          )}
          style={{ transform: `translateX(-${100 - percentage}%)` }}
        />
      </div>
    );
  },
);

Progress.displayName = "Progress";

export { Progress };
