"use client";

import * as React from "react";
import { CheckCircle, Loader2, XCircle } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { CredentialTestResponse } from "@/types/api";

interface CredentialTestResultProps {
  /** The test response, or null before any test */
  result: CredentialTestResponse | null;
  /** Whether a test is in flight */
  loading?: boolean;
  /** Optional error message from the mutation itself (vs API response) */
  error?: string | null;
  className?: string;
}

/**
 * Displays the result of a credential connection test.
 *
 * Shows an inline spinner while loading, a green success pill with
 * latency info on success, or a red failure pill with sanitized error
 * details underneath using an Alert.
 */
const CredentialTestResult = React.forwardRef<
  HTMLDivElement,
  CredentialTestResultProps
>(({ result, loading = false, error, className }, ref) => {
  // Loading state
  if (loading) {
    return (
      <div
        ref={ref}
        className={cn(
          "flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm text-muted-foreground",
          className,
        )}
      >
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        <span>Testing connection...</span>
      </div>
    );
  }

  // No result yet and no error
  if (!result && !error) {
    return null;
  }

  // Mutation-level error (network, etc.)
  if (error) {
    return (
      <div ref={ref} className={cn("space-y-2", className)}>
        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
          <XCircle className="h-4 w-4 shrink-0 text-destructive" />
          <span className="font-medium text-destructive">
            Connection failed
          </span>
        </div>
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  // At this point result is definitely non-null (the early guard above would
  // have returned if result was null AND error was falsy; and the error branch
  // returns above). Help TypeScript narrow:
  if (!result) return null;

  // API result: success
  if (result.success) {
    return (
      <div ref={ref} className={cn("space-y-2", className)}>
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 text-sm">
          <CheckCircle className="h-4 w-4 shrink-0 text-emerald-500" />
          <span className="font-medium text-emerald-600 dark:text-emerald-400">
            Connected in {result.latency_ms ?? "?"}ms
          </span>
          {result.status_code != null && (
            <Badge
              variant={result.status_code < 400 ? "secondary" : "destructive"}
              className="ml-auto text-xs"
            >
              {result.status_code}
            </Badge>
          )}
        </div>
        <Alert variant="default" className="border-emerald-500/20 bg-emerald-500/5">
          <AlertDescription className="text-xs text-muted-foreground">
            Connection test succeeded. The credential is valid and the server
            is reachable.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  // API result: failure (sanitized error)
  return (
    <div ref={ref} className={cn("space-y-2", className)}>
      <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
        <XCircle className="h-4 w-4 shrink-0 text-destructive" />
        <span className="font-medium text-destructive">
          {result.error ?? "Connection test failed"}
        </span>
        {result.status_code != null && (
          <Badge variant="destructive" className="ml-auto text-xs">
            {result.status_code}
          </Badge>
        )}
      </div>
      {result.error && (
        <Alert variant="destructive">
          <AlertDescription className="text-xs">
            {result.error}
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
});
CredentialTestResult.displayName = "CredentialTestResult";

export { CredentialTestResult };
export type { CredentialTestResultProps };
