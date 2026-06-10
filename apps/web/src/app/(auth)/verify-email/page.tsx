"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, AlertTriangle, Loader2, MailWarning } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useVerifyEmail, useResendVerification } from "@/hooks/use-auth";
import { toast } from "sonner";

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const verifyEmail = useVerifyEmail();
  const resendVerification = useResendVerification();
  const [attempted, setAttempted] = useState(false);

  useEffect(() => {
    if (token && !attempted) {
      setAttempted(true);
      verifyEmail.mutate(token);
    }
  }, [token, attempted, verifyEmail]);

  if (!token) {
    return (
      <div className="w-full max-w-sm mx-auto space-y-6 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
          <AlertTriangle className="h-6 w-6 text-destructive" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            Invalid or missing verification token
          </h1>
          <p className="text-sm text-muted-foreground">
            The email verification link is invalid or has expired. Please check
            your inbox for a new link.
          </p>
        </div>
      </div>
    );
  }

  if (verifyEmail.isPending) {
    return (
      <div className="w-full max-w-sm mx-auto space-y-6 text-center">
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">
          Verifying your email address...
        </p>
      </div>
    );
  }

  if (verifyEmail.isSuccess) {
    return (
      <div className="w-full max-w-sm mx-auto space-y-6 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <CheckCircle2 className="h-6 w-6 text-primary" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            Email verified!
          </h1>
          <p className="text-sm text-muted-foreground">
            Your email address has been verified successfully.
          </p>
        </div>
        <Button asChild className="w-full">
          <Link href="/dashboard">Go to dashboard</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-sm mx-auto space-y-6 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
        <MailWarning className="h-6 w-6 text-destructive" />
      </div>
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          Verification failed
        </h1>
        <p className="text-sm text-muted-foreground">
          {verifyEmail.error instanceof Error
            ? verifyEmail.error.message
            : "We couldn't verify your email. The link may have expired."}
        </p>
      </div>
      <Button
        variant="outline"
        className="w-full"
        onClick={() => {
          resendVerification.mutate(undefined, {
            onSuccess: () => {
              toast.success("Verification email sent. Check your inbox.");
            },
            onError: (error: unknown) => {
              toast.error(
                error instanceof Error
                  ? error.message
                  : "Failed to resend verification email.",
              );
            },
          });
        }}
        disabled={resendVerification.isPending}
      >
        {resendVerification.isPending
          ? "Sending..."
          : "Resend verification email"}
      </Button>
    </div>
  );
}
