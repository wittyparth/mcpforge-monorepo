"use client";

import { AlertTriangle } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { useRollback } from "@/hooks/use-servers";

interface RollbackDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  serverId: string;
  targetVersion: number;
  changeNote: string | null;
}

export function RollbackDialog({
  open,
  onOpenChange,
  serverId,
  targetVersion,
  changeNote,
}: RollbackDialogProps) {
  const rollback = useRollback(serverId);

  const handleRollback = () => {
    rollback.mutate(
      { version: targetVersion },
      { onSuccess: () => onOpenChange(false) },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Rollback to version {targetVersion}
          </DialogTitle>
          <DialogDescription>
            This will create a new version with the current state, then restore
            version {targetVersion}&apos;s configuration. You can rollback again
            if needed.
          </DialogDescription>
        </DialogHeader>

        {changeNote && (
          <div className="rounded-md bg-muted/50 px-3 py-2">
            <p className="text-xs font-medium text-muted-foreground">Change note</p>
            <p className="mt-1 text-sm">{changeNote}</p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleRollback}
            disabled={rollback.isPending}
          >
            {rollback.isPending ? (
              <>
                <LoadingSpinner size="sm" />
                Rolling back...
              </>
            ) : (
              `Rollback to v${targetVersion}`
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
