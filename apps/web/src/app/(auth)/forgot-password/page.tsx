import type { Metadata } from "next";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";

export const metadata: Metadata = {
  title: "Reset your password",
  description: "Enter your email to receive a password reset link",
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}
