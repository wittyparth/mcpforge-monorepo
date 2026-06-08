/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { DownloadCloud, KeyRound, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { specFetchSchema, type SpecFetchInput } from "@/lib/validators";
import { useFetchSpec } from "@/hooks/use-spec";
import type { SpecUploadResponse } from "@/types/api";

interface SpecUrlInputProps {
  onSuccess: (spec: SpecUploadResponse) => void;
  onError?: (error: string) => void;
  className?: string;
}

interface HeaderEntry {
  key: string;
  value: string;
}

/**
 * URL input for fetching an OpenAPI spec from a remote endpoint.
 * Supports custom request headers via a collapsible advanced section.
 */
const SpecUrlInput = React.forwardRef<HTMLDivElement, SpecUrlInputProps>(
  ({ onSuccess, onError, className }, ref) => {
    const [showHeaders, setShowHeaders] = React.useState(false);
    const [headers, setHeaders] = React.useState<HeaderEntry[]>([]);
    const fetchSpec = useFetchSpec();

    const {
      register,
      handleSubmit,
      formState: { errors },
      watch,
    } = useForm<SpecFetchInput>({
      resolver: zodResolver(specFetchSchema),
      mode: "onChange",
      defaultValues: {
        url: "",
        headers: {},
      },
    });

    const urlValue = watch("url");

    const addHeader = () => {
      setHeaders((prev) => [...prev, { key: "", value: "" }]);
    };

    const updateHeader = (
      index: number,
      field: "key" | "value",
      val: string,
    ) => {
      setHeaders((prev) =>
        prev.map((entry, i) => {
          if (i !== index) return entry;
          if (field === "key") return { ...entry, key: val };
          return { ...entry, value: val };
        }),
      );
    };

    const removeHeader = (index: number) => {
      setHeaders((prev) => prev.filter((_, i) => i !== index));
    };

    const buildHeadersObject = (): Record<string, string> | undefined => {
      const defined = headers.filter((h) => h.key.trim() !== "");
      if (defined.length === 0) return undefined;
      return Object.fromEntries(defined.map((h) => [h.key.trim(), h.value]));
    };

    const onSubmit = async (data: SpecFetchInput) => {
      try {
        const extraHeaders = buildHeadersObject();
        const result = await fetchSpec.mutateAsync({
          url: data.url,
          headers: extraHeaders ?? null,
        });
        onSuccess(result as any);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to fetch spec";
        onError?.(message);
      }
    };

    const isLoading = fetchSpec.isPending;

    return (
      <div ref={ref} className={cn("space-y-4", className)}>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* URL input */}
          <div className="space-y-2">
            <Label htmlFor="spec-url">OpenAPI Spec URL</Label>
            <Input
              id="spec-url"
              type="url"
              placeholder="https://api.example.com/openapi.json"
              className="h-11 text-base"
              {...register("url")}
            />
            {errors.url && (
              <p className="text-xs text-destructive">{errors.url.message}</p>
            )}
            <p className="text-xs text-muted-foreground">
              URL must be HTTPS and publicly accessible. Max 5MB.
            </p>
          </div>

          {/* Advanced headers section */}
          <div className="space-y-2">
            <button
              type="button"
              onClick={() => setShowHeaders((prev) => !prev)}
              className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-sm transition-colors"
            >
              <KeyRound className="h-4 w-4" />
              {showHeaders ? "Hide" : "Headers"}
            </button>

            {showHeaders && (
              <div className="space-y-2 rounded-lg border p-3">
                {headers.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    No custom headers. Add one to authenticate or customise the
                    request.
                  </p>
                )}
                {headers.map((header, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <div className="flex flex-1 gap-2">
                      <div className="flex-1">
                        <Input
                          placeholder="Header name"
                          value={header.key}
                          onChange={(e) =>
                            updateHeader(idx, "key", e.target.value)
                          }
                          className="h-9 text-xs font-mono"
                        />
                      </div>
                      <div className="flex-1">
                        <Input
                          placeholder="Value"
                          value={header.value}
                          onChange={(e) =>
                            updateHeader(idx, "value", e.target.value)
                          }
                          className="h-9 text-xs font-mono"
                        />
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-9 w-9 shrink-0"
                      onClick={() => removeHeader(idx)}
                      aria-label="Remove header"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addHeader}
                  className="w-full"
                >
                  Add header
                </Button>
              </div>
            )}
          </div>

          {/* Submit button */}
          <Button
            type="submit"
            size="lg"
            className="w-full gap-2"
            disabled={!urlValue || isLoading}
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Fetching...
              </>
            ) : (
              <>
                <DownloadCloud className="h-4 w-4" />
                Fetch Spec
              </>
            )}
          </Button>
        </form>
      </div>
    );
  },
);
SpecUrlInput.displayName = "SpecUrlInput";

export { SpecUrlInput };
export type { SpecUrlInputProps };
