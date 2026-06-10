"use client";

import { useState } from "react";
import { MoreHorizontal, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { RemoveMemberDialog } from "@/components/team/remove-member-dialog";
import { RoleSelector } from "@/components/team/role-selector";
import { useTeamMembers, useUpdateMemberRole } from "@/hooks/use-team";
import type { TeamMemberResponse, TeamRole } from "@/types/api";
import { toast } from "sonner";

const ROLE_BADGE_VARIANT: Record<TeamRole, "default" | "secondary" | "outline" | "destructive"> = {
  admin: "destructive",
  editor: "default",
  viewer: "outline",
};

const ROLE_LABELS: Record<TeamRole, string> = {
  admin: "Admin",
  editor: "Editor",
  viewer: "Viewer",
};

interface MembersTableProps {
  currentUserId: string;
  isAdmin: boolean;
}

export function MembersTable({ currentUserId, isAdmin }: MembersTableProps) {
  const { data, isLoading } = useTeamMembers();
  const updateRole = useUpdateMemberRole();
  const [removingMember, setRemovingMember] = useState<TeamMemberResponse | null>(null);

  const members: TeamMemberResponse[] = Array.isArray(data) ? data : data?.members ?? [];

  const handleRoleChange = (member: TeamMemberResponse, role: TeamRole) => {
    updateRole.mutate(
      { userId: member.user_id, role },
      {
        onSuccess: () => {
          toast.success(`Updated ${member.email}'s role to ${ROLE_LABELS[role]}`);
        },
        onError: () => {
          toast.error("Failed to update role");
        },
      },
    );
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (members.length === 0) {
    return (
      <EmptyState
        title="No members yet"
        description="Invite team members to start collaborating."
      />
    );
  }

  return (
    <>
      <div className="rounded-lg border">
        <div className="divide-y divide-border/50">
          {members.map((member) => {
            const isSelf = member.user_id === currentUserId;
            return (
              <div
                key={member.user_id}
                className="flex items-center justify-between gap-4 px-4 py-3"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-medium">
                    {(member.display_name?.[0] ?? member.email[0] ?? "?").toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">
                        {member.display_name ?? member.email}
                      </span>
                      {isSelf && (
                        <Badge variant="secondary" className="text-[10px]">
                          You
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      {member.email}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Badge variant={ROLE_BADGE_VARIANT[member.role]}>
                    {ROLE_LABELS[member.role]}
                  </Badge>

                  {isAdmin && !isSelf && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          aria-label={`Actions for ${member.email}`}
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Actions</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem className="flex items-center gap-2" asChild>
                          <div>
                            <span className="text-xs text-muted-foreground">
                              Change role
                            </span>
                          </div>
                        </DropdownMenuItem>
                        <div className="px-2 py-1.5">
                          <RoleSelector
                            value={member.role}
                            onChange={(role) =>
                              handleRoleChange(member, role)
                            }
                            disabled={updateRole.isPending}
                          />
                        </div>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive focus:text-destructive"
                          onClick={() => setRemovingMember(member)}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Remove member
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <RemoveMemberDialog
        member={removingMember}
        open={removingMember !== null}
        onOpenChange={(open) => {
          if (!open) setRemovingMember(null);
        }}
      />
    </>
  );
}
