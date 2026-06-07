import { z } from "zod";

export const loginSchema = z.object({
  email: z
    .string()
    .min(1, "Email is required")
    .email("Please enter a valid email address"),
  password: z
    .string()
    .min(1, "Password is required")
    .min(8, "Password must be at least 8 characters"),
});

export const registerSchema = z
  .object({
    email: z
      .string()
      .min(1, "Email is required")
      .email("Please enter a valid email address"),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters")
      .max(128, "Password must be less than 128 characters"),
    confirmPassword: z.string().min(1, "Please confirm your password"),
    display_name: z
      .string()
      .max(100, "Display name must be less than 100 characters")
      .optional(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

export const createServerSchema = z.object({
  name: z
    .string()
    .min(1, "Server name is required")
    .max(200, "Server name must be less than 200 characters"),
  slug: z
    .string()
    .min(3, "Slug must be at least 3 characters")
    .max(50, "Slug must be less than 50 characters")
    .regex(
      /^[a-z0-9]+(-[a-z0-9]+)*$/,
      "Slug must be lowercase alphanumeric with hyphens (e.g., my-server)",
    ),
  base_url: z
    .string()
    .min(1, "Base URL is required")
    .url("Please enter a valid URL (e.g., https://api.example.com)"),
  description: z
    .string()
    .max(1000, "Description must be less than 1000 characters")
    .optional(),
  auth_scheme: z.enum(["none", "api_key", "bearer", "basic", "oauth2"], {
    required_error: "Please select an authentication scheme",
  }),
});

export type LoginFormData = z.infer<typeof loginSchema>;
export type RegisterFormData = z.infer<typeof registerSchema>;
export type CreateServerFormData = z.infer<typeof createServerSchema>;

// ── F1: OpenAPI Spec Ingestion Schemas ───────────────────────────

export const specFetchSchema = z.object({
  url: z
    .string()
    .url("Must be a valid URL")
    .refine((u) => u.startsWith("https://"), "Only HTTPS URLs are allowed"),
  headers: z.record(z.string()).optional(),
});

export type SpecFetchInput = z.infer<typeof specFetchSchema>;

export const specUploadSchema = z.object({
  file: z.instanceof(File, { message: "File is required" }),
  type: z.enum(["json", "yaml"]),
});

export type SpecUploadInput = z.infer<typeof specUploadSchema>;

// ── Tool Selection Schema ─────────────────────────────────────────

export const toolSelectionSchema = z.object({
  slug: z
    .string()
    .min(3, "Slug must be at least 3 characters")
    .max(50, "Slug must be at most 50 characters")
    .regex(
      /^[a-z0-9]+(-[a-z0-9]+)*$/,
      "Slug must be lowercase alphanumeric with hyphens",
    ),
  name: z
    .string()
    .min(1, "Name is required")
    .max(200, "Name must be at most 200 characters"),
  base_url: z
    .string()
    .url("Must be a valid URL")
    .refine((u) => u.startsWith("https://"), "Only HTTPS base URLs are allowed"),
  description: z.string().max(2000).optional(),
  auth_scheme: z.enum(["none", "api_key", "bearer", "basic", "oauth2"]),
  auth_header_name: z.string().max(100).optional(),
  /** At least one tool must be selected */
  selected_tool_names: z
    .array(z.string())
    .nonempty("At least one tool must be selected"),
  transport_mode: z.enum(["sse", "streamable_http", "both"]),
});

export type ToolSelectionInput = z.infer<typeof toolSelectionSchema>;

// ── Credential Schemas ────────────────────────────────────────────

export const credentialCreateSchema = z.object({
  env_var_name: z
    .string()
    .regex(
      /^[A-Z][A-Z0-9_]*$/,
      "Must be uppercase letters, digits, underscores; start with a letter",
    ),
  value: z.string().min(1, "Value is required"),
  auth_scheme: z.enum(["bearer", "api_key", "basic", "oauth2", "header"]),
  auth_header_name: z.string().max(100).optional(),
});

export type CredentialCreateInput = z.infer<typeof credentialCreateSchema>;

// ── Build Schema ──────────────────────────────────────────────────

export const buildStartSchema = z.object({
  spec_source_id: z.string().uuid("Must be a valid UUID"),
  transport_mode: z.enum(["sse", "streamable_http", "both"]),
});

export type BuildStartInput = z.infer<typeof buildStartSchema>;
