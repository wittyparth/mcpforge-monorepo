"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  forgotPasswordSchema,
  type ForgotPasswordFormData,
} from "@/lib/validators";
import { useForgotPassword } from "@/hooks/use-auth";

export function ForgotPasswordForm() {
  const forgotPassword = useForgotPassword();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(forgotPasswordSchema),
  });

  const onSubmit = (data: ForgotPasswordFormData) => {
    forgotPassword.mutate(data.email);
  };

  if (forgotPassword.isSuccess) {
    return (
      <div className="w-full max-w-sm mx-auto space-y-6">
        <div className="space-y-2 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <CheckCircle2 className="h-6 w-6 text-primary" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Check your email
          </h1>
          <p className="text-sm text-muted-foreground">
            We sent a password reset link to your email address. Please check
            your inbox and follow the instructions.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-sm mx-auto space-y-6">
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">
          Reset your password
        </h1>
        <p className="text-sm text-muted-foreground">
          Enter your email and we&apos;ll send you a link to reset your
          password.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              autoComplete="email"
              className="pl-9"
              {...register("email")}
            />
          </div>
          {errors.email && (
            <p className="text-sm text-destructive" role="alert">
              {errors.email.message}
            </p>
          )}
        </div>

        {forgotPassword.isError && (
          <p className="text-sm text-destructive" role="alert">
            {forgotPassword.error instanceof Error
              ? forgotPassword.error.message
              : "Something went wrong. Please try again."}
          </p>
        )}

        <Button
          type="submit"
          className="w-full"
          disabled={forgotPassword.isPending}
        >
          {forgotPassword.isPending ? "Sending link..." : "Send reset link"}
        </Button>
      </form>
    </div>
  );
}
