"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { InviteForm } from "@/components/team/invite-form";

export default function InvitePage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Link
        href="/dashboard/team"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to team
      </Link>

      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Invite team member
        </h1>
        <p className="text-sm text-muted-foreground">
          Add a new member to your team
        </p>
      </div>

      <InviteForm />
    </div>
  );
}
