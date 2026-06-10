"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AnalyticsRange } from "@/hooks/use-analytics";

interface DateRangePickerProps {
  value: AnalyticsRange;
  onChange: (value: AnalyticsRange) => void;
  disabled?: boolean;
}

const RANGE_OPTIONS: { value: AnalyticsRange; label: string }[] = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
];

/**
 * Select dropdown for choosing the analytics time range (7d / 30d / 90d).
 */
export function DateRangePicker({
  value,
  onChange,
  disabled,
}: DateRangePickerProps) {
  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger className="w-[160px]">
        <SelectValue placeholder="Select range" />
      </SelectTrigger>
      <SelectContent>
        {RANGE_OPTIONS.map((opt) => (
          <SelectItem key={opt.value} value={opt.value}>
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
