"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { ArrowLeft, Shield } from "lucide-react";

import { useTeam } from "@/hooks/use-team";
import { Skeleton } from "@/components/ui/skeleton";
import { AuditLogTable } from "@/components/team/audit-log-table";

export default function AuditLogPage() {
  const router = useRouter();
  const { data: team, isLoading } = useTeam();

  const isAdmin = team?.current_user_role === "admin";

  useEffect(() => {
    if (!isLoading && team && !isAdmin) {
      router.push("/dashboard/team");
    }
  }, [isLoading, team, isAdmin, router]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (!isAdmin) {
    return null;
  }

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard/team"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to team
      </Link>

      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Shield className="h-6 w-6" />
          Team audit log
        </h1>
        <p className="text-sm text-muted-foreground">
          View all team activity and changes
        </p>
      </div>

      <AuditLogTable />
    </div>
  );
}
