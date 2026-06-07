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
