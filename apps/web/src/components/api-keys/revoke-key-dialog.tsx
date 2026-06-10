"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useRevokeApiKey } from "@/hooks/use-api-keys";

interface RevokeKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  keyId: string;
  keyName: string;
}

export function RevokeKeyDialog({
  open,
  onOpenChange,
  keyId,
  keyName,
}: RevokeKeyDialogProps) {
  const revokeKey = useRevokeApiKey();

  const handleRevoke = async () => {
    try {
      await revokeKey.mutateAsync(keyId);
      onOpenChange(false);
      toast.success(`API key "${keyName}" revoked`);
    } catch {
      toast.error("Failed to revoke API key");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Revoke API Key</DialogTitle>
          <DialogDescription>
            Are you sure you want to revoke <strong>{keyName}</strong>? This
            action cannot be undone. Any applications using this key will stop
            working immediately.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={revokeKey.isPending}
            onClick={handleRevoke}
          >
            {revokeKey.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Revoking...
              </>
            ) : (
              "Revoke Key"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
