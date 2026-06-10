"use client";

import { useState } from "react";
import { X, MailWarning } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useResendVerification } from "@/hooks/use-auth";
import { toast } from "sonner";

export function VerifyEmailBanner() {
  const [dismissed, setDismissed] = useState(false);
  const resendVerification = useResendVerification();

  if (dismissed) return null;

  const handleResend = () => {
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
  };

  return (
    <div
      className="flex items-center gap-3 border-b border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-200"
      role="alert"
    >
      <MailWarning className="h-4 w-4 shrink-0" />
      <p className="flex-1">
        Please verify your email address. Check your inbox for a verification
        link.
      </p>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleResend}
        disabled={resendVerification.isPending}
        className="shrink-0 text-yellow-800 hover:bg-yellow-100 hover:text-yellow-900 dark:text-yellow-200 dark:hover:bg-yellow-900"
      >
        {resendVerification.isPending ? "Sending..." : "Resend email"}
      </Button>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="shrink-0 text-yellow-600 hover:text-yellow-800 dark:text-yellow-400 dark:hover:text-yellow-200"
        aria-label="Dismiss verification banner"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
