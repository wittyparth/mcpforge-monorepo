"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, Loader2, Plus } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type {
  AuthScheme,
  CredentialAuthScheme,
  CredentialCreateRequest,
  CredentialInfo,
  CredentialTestRequest,
  CredentialTestResponse,
} from "@/types/api";
import { CredentialTestResult } from "./credential-test-result";

// ── Form schema ───────────────────────────────────────────────────

const credentialFormSchema = z.object({
  env_var_name: z
    .string()
    .regex(
      /^[A-Z][A-Z0-9_]*$/,
      "Must be uppercase letters, digits, or underscores, starting with a letter",
    ),
  value: z.string().min(1, "Value is required"),
  auth_header_name: z.string().max(100).optional(),
});

type CredentialFormData = z.infer<typeof credentialFormSchema>;

// ── Auth scheme mapping ───────────────────────────────────────────

/** Map public AuthScheme to the credential-specific variant. */
function toCredentialAuthScheme(scheme: AuthScheme): CredentialAuthScheme {
  switch (scheme) {
    case "api_key":
      return "api_key";
    case "bearer":
      return "bearer";
    case "basic":
      return "basic";
    case "oauth2":
      return "oauth2";
    default:
      return "header";
  }
}

// ── Component ─────────────────────────────────────────────────────

interface CredentialInputProps {
  /** Called when the user saves a new credential */
  onAdd: (cred: CredentialCreateRequest) => Promise<void>;
  /** Called when the user clicks "Test Connection" */
  onTest: (cred: CredentialTestRequest) => Promise<CredentialTestResponse>;
  /** Credentials already stored for this server */
  existingCredentials: CredentialInfo[];
  /** The auth scheme selected for the server */
  authScheme: AuthScheme;
  className?: string;
}

/**
 * Form for adding and testing a single credential.
 *
 * Supports uppercase-enforced env variable names, password visibility
 * toggle, and an optional auth header field shown only for the
 * `api_key` scheme. Results from "Test Connection" render inline
 * via `<CredentialTestResult />`.
 */
const CredentialInput = React.forwardRef<HTMLDivElement, CredentialInputProps>(
  (
    { onAdd, onTest, existingCredentials, authScheme, className },
    ref,
  ) => {
    const [showValue, setShowValue] = React.useState(false);
    const [testResult, setTestResult] =
      React.useState<CredentialTestResponse | null>(null);
    const [testError, setTestError] = React.useState<string | null>(null);
    const [isTesting, setIsTesting] = React.useState(false);
    const [isSaving, setIsSaving] = React.useState(false);
    const [warning, setWarning] = React.useState<string | null>(null);

    const {
      register,
      handleSubmit,
      watch,
      reset,
      formState: { errors },
    } = useForm<CredentialFormData>({
      resolver: zodResolver(credentialFormSchema),
      defaultValues: {
        env_var_name: "",
        value: "",
        auth_header_name: "",
      },
    });

    const watchedEnvVar = watch("env_var_name");

    // Check for duplicate env var name
    React.useEffect(() => {
      if (
        watchedEnvVar &&
        existingCredentials.some(
          (c) =>
            c.env_var_name.toUpperCase() === watchedEnvVar.toUpperCase(),
        )
      ) {
        setWarning(
          "This credential already exists. Saving will replace it.",
        );
      } else {
        setWarning(null);
      }
    }, [watchedEnvVar, existingCredentials]);

    const handleTest = React.useCallback(
      async (data: CredentialFormData) => {
        setIsTesting(true);
        setTestError(null);
        setTestResult(null);
        try {
          const result = await onTest({
            env_var_name: data.env_var_name,
            test_value: data.value,
          });
          setTestResult(result);
        } catch (err) {
          setTestError(
            err instanceof Error ? err.message : "Connection test failed",
          );
        } finally {
          setIsTesting(false);
        }
      },
      [onTest],
    );

    const handleSave = React.useCallback(
      async (data: CredentialFormData) => {
        setIsSaving(true);
        try {
          await onAdd({
            env_var_name: data.env_var_name,
            value: data.value,
            auth_scheme: toCredentialAuthScheme(authScheme),
            auth_header_name:
              authScheme === "api_key"
                ? data.auth_header_name || "X-API-Key"
                : undefined,
          });
          reset({
            env_var_name: "",
            value: "",
            auth_header_name: "",
          });
          setTestResult(null);
          setTestError(null);
        } finally {
          setIsSaving(false);
        }
      },
      [onAdd, authScheme, reset],
    );

    // If auth scheme is "none", credential input isn't needed
    if (authScheme === "none") {
      return (
        <div
          ref={ref}
          className={cn(
            "rounded-lg border border-border bg-muted/20 px-4 py-6 text-center text-sm text-muted-foreground",
            className,
          )}
        >
          No authentication selected. Credentials are not required for public
          APIs.
        </div>
      );
    }

    return (
      <div ref={ref} className={cn("space-y-5", className)}>
        <form
          onSubmit={handleSubmit(handleSave)}
          className="space-y-4"
        >
          {/* Env Variable Name */}
          <div className="space-y-2">
            <Label htmlFor="cred-env-var">
              Environment variable name
            </Label>
            <Input
              id="cred-env-var"
              placeholder="API_KEY"
              {...register("env_var_name", {
                onChange: (e) => {
                  e.target.value = e.target.value.toUpperCase();
                },
              })}
              className={cn(
                "font-mono text-sm uppercase",
                errors.env_var_name &&
                  "border-destructive focus-visible:ring-destructive",
              )}
              aria-invalid={!!errors.env_var_name}
            />
            {errors.env_var_name && (
              <p className="text-xs text-destructive">
                {errors.env_var_name.message}
              </p>
            )}
            {warning && (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                {warning}
              </p>
            )}
          </div>

          {/* Value */}
          <div className="space-y-2">
            <Label htmlFor="cred-value">Value</Label>
            <div className="relative">
              <Input
                id="cred-value"
                type={showValue ? "text" : "password"}
                placeholder={
                  authScheme === "api_key"
                    ? "sk-..."
                    : authScheme === "bearer"
                      ? "eyJhbGci..."
                      : "Enter credential value"
                }
                {...register("value")}
                className={cn(
                  "pr-10",
                  errors.value &&
                    "border-destructive focus-visible:ring-destructive",
                )}
                aria-invalid={!!errors.value}
              />
              <button
                type="button"
                onClick={() => setShowValue((prev) => !prev)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring rounded-sm p-0.5"
                tabIndex={-1}
                aria-label={showValue ? "Hide value" : "Show value"}
              >
                {showValue ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
            {errors.value && (
              <p className="text-xs text-destructive">
                {errors.value.message}
              </p>
            )}
          </div>

          {/* Auth header name — only for api_key */}
          {authScheme === "api_key" && (
            <div className="space-y-2">
              <Label htmlFor="cred-auth-header">
                Auth header name{" "}
                <span className="text-muted-foreground font-normal">
                  (optional)
                </span>
              </Label>
              <Input
                id="cred-auth-header"
                placeholder="X-API-Key"
                {...register("auth_header_name")}
                className={cn(
                  "font-mono text-sm",
                  errors.auth_header_name &&
                    "border-destructive focus-visible:ring-destructive",
                )}
              />
              {errors.auth_header_name && (
                <p className="text-xs text-destructive">
                  {errors.auth_header_name.message}
                </p>
              )}
            </div>
          )}

          {/* Buttons */}
          <div className="flex items-center gap-3 pt-1">
            <Button
              type="button"
              variant="outline"
              onClick={handleSubmit(handleTest)}
              disabled={isTesting || isSaving}
              className="flex-1 sm:flex-none"
            >
              {isTesting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Testing...
                </>
              ) : (
                "Test Connection"
              )}
            </Button>
            <Button
              type="submit"
              disabled={isTesting || isSaving}
              className="flex-1 sm:flex-none"
            >
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4" />
                  Save Credential
                </>
              )}
            </Button>
          </div>
        </form>

        {/* Test result */}
        {(testResult || testError || isTesting) && (
          <>
            <Separator />
            <CredentialTestResult
              result={testResult}
              loading={isTesting}
              error={testError}
            />
          </>
        )}
      </div>
    );
  },
);
CredentialInput.displayName = "CredentialInput";

export { CredentialInput };
export type { CredentialInputProps };
