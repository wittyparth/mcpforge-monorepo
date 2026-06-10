import { Check } from "lucide-react";

interface PlanFeaturesProps {
  features: string[];
}

export function PlanFeatures({ features }: PlanFeaturesProps) {
  return (
    <ul className="space-y-2">
      {features.map((feature) => (
        <li key={feature} className="flex items-start gap-2 text-sm">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <span className="text-muted-foreground">{feature}</span>
        </li>
      ))}
    </ul>
  );
}
