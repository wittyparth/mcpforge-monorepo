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

// ── F7: Auth Flow Schemas ──────────────────────────────────────────

export const forgotPasswordSchema = z.object({
  email: z
    .string()
    .min(1, "Email is required")
    .email("Please enter a valid email address"),
});

export const resetPasswordSchema = z
  .object({
    password: z
      .string()
      .min(12, "Password must be at least 12 characters")
      .max(128, "Password must be less than 128 characters"),
    confirmPassword: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

export type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>;
export type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>;

// ── Build Schema ──────────────────────────────────────────────────

export const buildStartSchema = z.object({
  spec_source_id: z.string().uuid("Must be a valid UUID"),
  transport_mode: z.enum(["sse", "streamable_http", "both"]),
});

export type BuildStartInput = z.infer<typeof buildStartSchema>;

// ── F7: Team Schemas ──────────────────────────────────────────────

export const createTeamSchema = z.object({
  name: z
    .string()
    .min(1, "Team name is required")
    .max(200, "Team name must be less than 200 characters"),
});

export const inviteMemberSchema = z.object({
  email: z
    .string()
    .min(1, "Email is required")
    .email("Please enter a valid email address"),
  role: z.enum(["admin", "editor", "viewer"], {
    required_error: "Please select a role",
  }),
});

export const updateMemberRoleSchema = z.object({
  role: z.enum(["admin", "editor", "viewer"], {
    required_error: "Please select a role",
  }),
});

export const updateTeamSchema = z.object({
  name: z
    .string()
    .min(1, "Team name is required")
    .max(200, "Team name must be less than 200 characters"),
});

export type CreateTeamFormData = z.infer<typeof createTeamSchema>;
export type InviteMemberFormData = z.infer<typeof inviteMemberSchema>;
export type UpdateMemberRoleFormData = z.infer<typeof updateMemberRoleSchema>;
export type UpdateTeamFormData = z.infer<typeof updateTeamSchema>;

// ── F7: API Key Schemas ────────────────────────────────────────────

export const API_KEY_SCOPES = [
  "servers:read",
  "servers:write",
  "analytics:read",
  "admin",
] as const;

export type ApiKeyScopeOption = (typeof API_KEY_SCOPES)[number];

export const API_KEY_SCOPE_DESCRIPTIONS: Record<ApiKeyScopeOption, string> = {
  "servers:read": "View servers and their configuration",
  "servers:write": "Create, update, and delete servers",
  "analytics:read": "View analytics and usage data",
  admin: "Full access to all resources (includes all other scopes)",
};

export const EXPIRATION_OPTIONS = [
  { label: "Never", value: null },
  { label: "30 days", value: 30 },
  { label: "90 days", value: 90 },
  { label: "1 year", value: 365 },
] as const;

export const createApiKeySchema = z.object({
  name: z
    .string()
    .min(1, "Key name is required")
    .max(100, "Key name must be less than 100 characters"),
  scopes: z
    .array(z.enum(API_KEY_SCOPES))
    .min(1, "Select at least one scope"),
  expires_in_days: z.number().nullable(),
});

export type CreateApiKeyFormData = z.infer<typeof createApiKeySchema>;

// ── F7: Billing Schemas ──────────────────────────────────────────

export const subscribeSchema = z.object({
  plan: z.enum(["pro", "team"], {
    required_error: "Please select a plan",
  }),
  billing_period: z.enum(["monthly", "yearly"], {
    required_error: "Please select a billing period",
  }),
  seats: z
    .number()
    .int("Must be a whole number")
    .min(1, "At least 1 seat required")
    .max(100, "Maximum 100 seats")
    .optional(),
});

export type SubscribeFormData = z.infer<typeof subscribeSchema>;

// ── F7: Server Management Schemas ───────────────────────────────

export const duplicateServerSchema = z.object({
  new_name: z
    .string()
    .min(1, "Server name is required")
    .max(200, "Server name must be less than 200 characters"),
  new_slug: z
    .string()
    .min(3, "Slug must be at least 3 characters")
    .max(50, "Slug must be less than 50 characters")
    .regex(
      /^[a-z0-9]+(-[a-z0-9]+)*$/,
      "Slug must be lowercase alphanumeric with hyphens (e.g., my-server)",
    )
    .optional()
    .or(z.null()),
});

export const rollbackSchema = z.object({
  version: z.number().int("Must be a whole number").min(1, "Version must be at least 1"),
});

export type DuplicateServerFormData = z.infer<typeof duplicateServerSchema>;
export type RollbackFormData = z.infer<typeof rollbackSchema>;
