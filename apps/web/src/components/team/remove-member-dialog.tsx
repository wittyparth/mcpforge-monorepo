"use client";

import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useRemoveMember } from "@/hooks/use-team";
import type { TeamMemberResponse } from "@/types/api";

interface RemoveMemberDialogProps {
  member: TeamMemberResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RemoveMemberDialog({
  member,
  open,
  onOpenChange,
}: RemoveMemberDialogProps) {
  const removeMember = useRemoveMember();

  const handleRemove = async () => {
    if (!member) return;
    try {
      await removeMember.mutateAsync(member.user_id);
      toast.success(`Removed ${member.email} from the team`);
      onOpenChange(false);
    } catch {
      toast.error("Failed to remove member");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Remove team member</DialogTitle>
          <DialogDescription>
            Are you sure you want to remove{" "}
            <strong>{member?.email}</strong> from the team? This action cannot be
            undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleRemove}
            disabled={removeMember.isPending}
          >
            {removeMember.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Removing...
              </>
            ) : (
              "Remove member"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
