"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { FileText, Globe, Hash, Loader2, Server } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { TransportMode } from "@/types/api";

// ── Zod schema ────────────────────────────────────────────────────

const serverConfigSchema = z.object({
  name: z
    .string()
    .min(1, "Server name is required")
    .max(200, "Name must be less than 200 characters"),
  slug: z
    .string()
    .min(3, "Slug must be at least 3 characters")
    .max(50, "Slug must be less than 50 characters")
    .regex(
      /^[a-z0-9-]+$/,
      "Slug must be lowercase alphanumeric with hyphens (e.g., my-server)",
    ),
  description: z
    .string()
    .max(1000, "Description must be less than 1000 characters")
    .optional()
    .default(""),
  base_url: z
    .string()
    .min(1, "Base URL is required")
    .url("Must be a valid URL (e.g., https://api.example.com)"),
  transport_mode: z.enum(["sse", "streamable_http", "both"], {
    required_error: "Please select a transport mode",
  }),
});

export type ServerConfigFormData = z.infer<typeof serverConfigSchema>;

// ── Helpers ───────────────────────────────────────────────────────

function deriveSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 50);
}

const TRANSPORT_OPTIONS: {
  value: TransportMode;
  label: string;
  description: string;
}[] = [
  {
    value: "sse",
    label: "Server-Sent Events",
    description: "Standard SSE transport for persistent connections",
  },
  {
    value: "streamable_http",
    label: "Streamable HTTP",
    description: "HTTP-based transport (stateless, fire-and-forget)",
  },
  {
    value: "both",
    label: "Both SSE + HTTP",
    description: "Support both transport modes simultaneously",
  },
];

// ── Component ─────────────────────────────────────────────────────

interface ServerConfigFormProps {
  /** Pre-populate form with existing server values (for edit mode) */
  defaultValues?: Partial<ServerConfigFormData>;
  /** Called with validated form data on submit */
  onSubmit: (data: ServerConfigFormData) => void;
  /** Whether the form is submitting (disables button) */
  isSubmitting?: boolean;
  className?: string;
}

/**
 * Server identity and connection configuration form.
 *
 * Fields: name, slug (auto-derived from name with edit-override toggle),
 * description, base URL, and transport mode. Validation via Zod.
 */
const ServerConfigForm = React.forwardRef<
  HTMLFormElement,
  ServerConfigFormProps
>(({ defaultValues, onSubmit, isSubmitting = false, className }, ref) => {
  const slugEditedRef = React.useRef(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<ServerConfigFormData>({
    resolver: zodResolver(serverConfigSchema),
    defaultValues: {
      name: "",
      slug: "",
      description: "",
      base_url: "",
      transport_mode: "sse",
      ...defaultValues,
    },
  });

  const watchedName = watch("name");
  const watchedSlug = watch("slug");

  // Auto-derive slug from name unless user has manually edited slug
  React.useEffect(() => {
    if (!slugEditedRef.current && watchedName) {
      const derived = deriveSlug(watchedName);
      if (derived !== watchedSlug) {
        setValue("slug", derived, { shouldValidate: false });
      }
    }
  }, [watchedName, watchedSlug, setValue]);

  const handleSlugChange = React.useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      slugEditedRef.current = true;
      const { onChange } = register("slug");
      onChange(e);
    },
    [register],
  );

  // ── Render ──────────────────────────────────────────────────────

  return (
    <form
      ref={ref}
      onSubmit={handleSubmit(onSubmit)}
      className={cn("space-y-6", className)}
    >
      {/* ── Server Identity ── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Server className="h-5 w-5 text-primary" />
            Server Identity
          </CardTitle>
          <CardDescription>
            Choose a name and unique URL slug for your MCP server.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Name */}
          <div className="space-y-2">
            <Label htmlFor="server-name">
              Server name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="server-name"
              placeholder="My API Server"
              {...register("name")}
              className={cn(
                errors.name && "border-destructive focus-visible:ring-destructive",
              )}
              aria-invalid={!!errors.name}
            />
            {errors.name && (
              <p className="text-xs text-destructive">{errors.name.message}</p>
            )}
          </div>

          {/* Slug */}
          <div className="space-y-2">
            <Label htmlFor="server-slug">
              Server slug <span className="text-destructive">*</span>
            </Label>
            <div className="flex items-center gap-1.5">
              <span className="shrink-0 text-xs text-muted-foreground font-mono whitespace-nowrap">
                mcpforge.io/mcp/v1/
              </span>
              <div className="relative flex-1">
                <Input
                  id="server-slug"
                  placeholder="my-api-server"
                  {...register("slug", {
                    onChange: handleSlugChange,
                  })}
                  className={cn(
                    "font-mono text-sm",
                    errors.slug &&
                      "border-destructive focus-visible:ring-destructive",
                  )}
                  aria-invalid={!!errors.slug}
                />
                <Hash className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/50" />
              </div>
            </div>
            {errors.slug && (
              <p className="text-xs text-destructive">{errors.slug.message}</p>
            )}
            <p className="text-xs text-muted-foreground">
              Auto-derived from name. Type to override.
            </p>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="server-description">
              Description{" "}
              <span className="font-normal text-muted-foreground">
                (optional)
              </span>
            </Label>
            <div className="relative">
              <textarea
                id="server-description"
                {...register("description")}
                placeholder="A brief description of what this API does..."
                rows={3}
                className={cn(
                  "flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 min-h-[60px]",
                  errors.description &&
                    "border-destructive focus-visible:ring-destructive",
                )}
              />
              <FileText className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-muted-foreground/50" />
            </div>
            {errors.description && (
              <p className="text-xs text-destructive">
                {errors.description.message}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ── Connection ── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Globe className="h-5 w-5 text-primary" />
            Connection
          </CardTitle>
          <CardDescription>
            Where is your API hosted and how should MCP clients connect?
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Base URL */}
          <div className="space-y-2">
            <Label htmlFor="server-base-url">
              Base URL <span className="text-destructive">*</span>
            </Label>
            <Input
              id="server-base-url"
              type="url"
              placeholder="https://api.example.com"
              {...register("base_url")}
              className={cn(
                errors.base_url &&
                  "border-destructive focus-visible:ring-destructive",
              )}
              aria-invalid={!!errors.base_url}
            />
            {errors.base_url && (
              <p className="text-xs text-destructive">
                {errors.base_url.message}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              The root URL of your API. All tool calls will be relative to this
              URL.
            </p>
          </div>

          <Separator />

          {/* Transport Mode */}
          <div className="space-y-2">
            <Label htmlFor="server-transport">
              Transport mode <span className="text-destructive">*</span>
            </Label>
            <Select
              defaultValue="sse"
              onValueChange={(v) =>
                setValue("transport_mode", v as TransportMode)
              }
            >
              <SelectTrigger id="server-transport" className="w-full">
                <SelectValue placeholder="Select transport mode" />
              </SelectTrigger>
              <SelectContent>
                {TRANSPORT_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    <div className="flex flex-col items-start">
                      <span>{opt.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {opt.description}
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.transport_mode && (
              <p className="text-xs text-destructive">
                {errors.transport_mode.message}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              MCP supports Server-Sent Events (persistent) and Streamable HTTP
              (stateless).
            </p>
          </div>
        </CardContent>
      </Card>

      {/* ── Hidden description field (react-hook-form needs it registered) ── */}
      {/* Already registered above as textarea */}

      {/* ── Submit ── */}
      <Button
        type="submit"
        size="lg"
        className="w-full gap-2"
        disabled={isSubmitting}
      >
        {isSubmitting ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Saving...
          </>
        ) : (
          <>
            <Globe className="h-4 w-4" />
            Save and Continue
          </>
        )}
      </Button>
    </form>
  );
});
ServerConfigForm.displayName = "ServerConfigForm";

export { ServerConfigForm };
export type { ServerConfigFormProps };
