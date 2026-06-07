"use client";

import * as React from "react";
import { Check, Key, KeyRound, Lock, ShieldCheck, Unlock } from "lucide-react";

import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { cn } from "@/lib/utils";
import type { AuthScheme } from "@/types/api";

interface AuthSchemeOption {
  value: AuthScheme;
  label: string;
  description: string;
  icon: React.ElementType;
}

const AUTH_SCHEMES: AuthSchemeOption[] = [
  {
    value: "none",
    label: "No authentication",
    description: "Public API, no credentials needed",
    icon: Unlock,
  },
  {
    value: "api_key",
    label: "API Key",
    description: "Header-based API key (e.g., X-API-Key)",
    icon: Key,
  },
  {
    value: "bearer",
    label: "Bearer Token",
    description: "OAuth 2.0 / JWT in Authorization header",
    icon: KeyRound,
  },
  {
    value: "basic",
    label: "Basic Auth",
    description: "Username and password (base64)",
    icon: Lock,
  },
  {
    value: "oauth2",
    label: "OAuth 2.0",
    description: "Client credentials flow",
    icon: ShieldCheck,
  },
];

interface AuthSchemeSelectorProps {
  /** Currently selected auth scheme */
  value: AuthScheme;
  /** Called when the user selects a different scheme */
  onChange: (value: AuthScheme) => void;
  className?: string;
}

/**
 * A RadioGroup presented as a grid of bordered cards.
 *
 * Each card shows an icon, label, and description, with a checkmark
 * overlay when selected. Uses the shadcn RadioGroup for accessibility
 * but hides the default radio circle in favor of a visual card layout.
 */
const AuthSchemeSelector = React.forwardRef<
  HTMLDivElement,
  AuthSchemeSelectorProps
>(({ value, onChange, className }, ref) => {
  return (
    <RadioGroup
      ref={ref}
      value={value}
      onValueChange={(v) => onChange(v as AuthScheme)}
      className={cn(
        "grid grid-cols-1 gap-3 md:grid-cols-2",
        className,
      )}
    >
      {AUTH_SCHEMES.map((scheme) => {
        const Icon = scheme.icon;
        const isSelected = value === scheme.value;

        return (
          <Label
            key={scheme.value}
            htmlFor={`auth-${scheme.value}`}
            className={cn(
              "relative flex cursor-pointer items-start gap-3 rounded-lg border-2 p-4 transition-all duration-200 hover:border-muted-foreground/30 hover:bg-accent/50",
              isSelected
                ? "border-primary bg-primary/5 shadow-sm"
                : "border-border bg-card",
            )}
          >
            {/* Hidden radio input for accessibility */}
            <RadioGroupItem
              value={scheme.value}
              id={`auth-${scheme.value}`}
              className="absolute sr-only"
            />

            {/* Icon */}
            <div
              className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors duration-200",
                isSelected
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
            </div>

            {/* Label + Description */}
            <div className="flex flex-col gap-0.5 min-w-0">
              <span
                className={cn(
                  "text-sm font-medium leading-snug transition-colors duration-200",
                  isSelected ? "text-primary" : "text-foreground",
                )}
              >
                {scheme.label}
              </span>
              <span className="text-xs leading-tight text-muted-foreground">
                {scheme.description}
              </span>
            </div>

            {/* Selected checkmark */}
            {isSelected && (
              <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <Check className="h-3 w-3" />
              </span>
            )}
          </Label>
        );
      })}
    </RadioGroup>
  );
});
AuthSchemeSelector.displayName = "AuthSchemeSelector";

export { AuthSchemeSelector };
export type { AuthSchemeSelectorProps };
