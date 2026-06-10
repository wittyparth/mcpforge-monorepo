import type { Metadata } from "next";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { ResetPasswordForm } from "@/components/auth/reset-password-form";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Set a new password",
  description: "Create a new password for your account",
};

interface ResetPasswordPageProps {
  searchParams: Promise<{ token?: string }>;
}

export default async function ResetPasswordPage({
  searchParams,
}: ResetPasswordPageProps) {
  const params = await searchParams;
  const token = params.token;

  if (!token) {
    return (
      <div className="w-full max-w-sm mx-auto space-y-6 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
          <AlertTriangle className="h-6 w-6 text-destructive" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            Invalid or missing reset token
          </h1>
          <p className="text-sm text-muted-foreground">
            The password reset link is invalid or has expired. Please request a
            new one.
          </p>
        </div>
        <Button asChild>
          <Link href="/forgot-password">Request a new link</Link>
        </Button>
      </div>
    );
  }

  return <ResetPasswordForm token={token} />;
}
