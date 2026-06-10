"use client";

import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { AlertCircle, CheckCircle, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAcceptInvitation } from "@/hooks/use-team";

function AcceptInvitationContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const acceptInvitation = useAcceptInvitation();

  useEffect(() => {
    if (token && !acceptInvitation.isSuccess && !acceptInvitation.isError && !acceptInvitation.isPending) {
      acceptInvitation.mutate({ token });
    }
  }, [token, acceptInvitation]);

  if (!token) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 text-center">
          <AlertCircle className="h-12 w-12 text-destructive/50" />
          <h3 className="mt-4 text-lg font-medium">Invalid invitation</h3>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            This invitation link is invalid or missing a token. Please ask your
            team admin to send a new invitation.
          </p>
          <Button asChild className="mt-6">
            <Link href="/dashboard/team">Go to team</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (acceptInvitation.isPending) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 text-center">
          <Loader2 className="h-12 w-12 animate-spin text-muted-foreground" />
          <h3 className="mt-4 text-lg font-medium">Accepting invitation...</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Please wait while we process your invitation.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (acceptInvitation.isError) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 text-center">
          <AlertCircle className="h-12 w-12 text-destructive/50" />
          <h3 className="mt-4 text-lg font-medium">
            Failed to accept invitation
          </h3>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            {acceptInvitation.error instanceof Error
              ? acceptInvitation.error.message
              : "This invitation may have expired or already been accepted."}
          </p>
          <Button asChild className="mt-6">
            <Link href="/dashboard/team">Go to team</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center py-16 text-center">
        <CheckCircle className="h-12 w-12 text-emerald-500" />
        <h3 className="mt-4 text-lg font-medium">
          You&apos;ve joined the team!
        </h3>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">
          You&apos;re now a member of this team. You can start collaborating on
          MCP servers.
        </p>
        <Button asChild className="mt-6">
          <Link href="/dashboard/team">Go to team</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

export default function AcceptPage() {
  return (
    <div className="mx-auto max-w-lg space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">
        Accept invitation
      </h1>
      <Suspense
        fallback={
          <Card>
            <CardContent className="flex items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </CardContent>
          </Card>
        }
      >
        <AcceptInvitationContent />
      </Suspense>
    </div>
  );
}
