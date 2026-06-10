"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import {
  Copy,
  Edit,
  Loader2,
  Plus,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useUpdateTeam } from "@/hooks/use-team";
import { updateTeamSchema, type UpdateTeamFormData } from "@/lib/validators";
import type { TeamResponse } from "@/types/api";

interface TeamInfoCardProps {
  team: TeamResponse;
}

export function TeamInfoCard({ team }: TeamInfoCardProps) {
  const router = useRouter();
  const updateTeam = useUpdateTeam();
  const [editOpen, setEditOpen] = useState(false);

  const form = useForm<UpdateTeamFormData>({
    resolver: zodResolver(updateTeamSchema),
    defaultValues: { name: team.name },
  });

  const isAdmin = team.current_user_role === "admin";

  const handleCopyId = async () => {
    await navigator.clipboard.writeText(team.id);
    toast.success("Team ID copied to clipboard");
  };

  const handleEditSubmit = form.handleSubmit(async (data) => {
    try {
      await updateTeam.mutateAsync(data);
      setEditOpen(false);
      toast.success("Team updated");
    } catch {
      toast.error("Failed to update team");
    }
  });

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Team Details
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Team Name
              </span>
              <p className="text-sm font-medium">{team.name}</p>
            </div>
            <div className="space-y-1">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Members
              </span>
              <p className="text-sm font-medium">{team.member_count}</p>
            </div>
            <div className="space-y-1">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Your Role
              </span>
              <p className="text-sm font-medium capitalize">
                {team.current_user_role}
              </p>
            </div>
            <div className="space-y-1">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Plan
              </span>
              <p className="text-sm font-medium capitalize">{team.plan}</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={handleCopyId}>
              <Copy className="mr-1.5 h-3.5 w-3.5" />
              Copy Team ID
            </Button>
            {isAdmin && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditOpen(true)}
                >
                  <Edit className="mr-1.5 h-3.5 w-3.5" />
                  Edit Name
                </Button>
                <Button
                  size="sm"
                  onClick={() => router.push("/dashboard/team/invite")}
                >
                  <Plus className="mr-1.5 h-3.5 w-3.5" />
                  Invite Member
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit team name</DialogTitle>
            <DialogDescription>
              Update your team&apos;s display name.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleEditSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-team-name">Team name</Label>
              <Input
                id="edit-team-name"
                {...form.register("name")}
                aria-invalid={!!form.formState.errors.name}
              />
              {form.formState.errors.name && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.name.message}
                </p>
              )}
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={updateTeam.isPending}>
                {updateTeam.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  "Save"
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
