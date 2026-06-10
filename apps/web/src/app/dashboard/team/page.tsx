"use client";

import { useCurrentUser } from "@/hooks/use-auth";
import { useTeam } from "@/hooks/use-team";
import { Skeleton } from "@/components/ui/skeleton";
import { CreateTeamCard } from "@/components/team/create-team-card";
import { TeamInfoCard } from "@/components/team/team-info-card";
import { MembersTable } from "@/components/team/members-table";

export default function TeamPage() {
  const { data: user } = useCurrentUser();
  const { data: team, isLoading } = useTeam();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-8 w-32" />
          <Skeleton className="mt-2 h-4 w-48" />
        </div>
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (!team) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Team</h1>
          <p className="text-sm text-muted-foreground">
            Manage your team members and settings
          </p>
        </div>
        <CreateTeamCard />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Team</h1>
        <p className="text-sm text-muted-foreground">
          Manage your team members and settings
        </p>
      </div>

      <TeamInfoCard team={team} />

      <div>
        <h2 className="mb-4 text-lg font-medium">Members</h2>
        <MembersTable
          currentUserId={user?.id ?? ""}
          isAdmin={team.current_user_role === "admin"}
        />
      </div>
    </div>
  );
}
