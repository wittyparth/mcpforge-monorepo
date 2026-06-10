"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { useOpenPortal } from "@/hooks/use-billing";
import { toast } from "sonner";
import { AlertTriangle } from "lucide-react";

interface CancelSubscriptionDialogProps {
  children: React.ReactNode;
}

export function CancelSubscriptionDialog({
  children,
}: CancelSubscriptionDialogProps) {
  const [open, setOpen] = useState(false);
  const [cancelOption, setCancelOption] = useState<"period_end" | "immediately">(
    "period_end",
  );
  const openPortal = useOpenPortal();

  function handleCancel() {
    if (cancelOption === "immediately") {
      openPortal.mutate(
        { return_url: window.location.href },
        {
          onSuccess: () => {
            setOpen(false);
          },
          onError: (error: Error) => {
            toast.error(error.message || "Failed to open billing portal");
          },
        },
      );
    } else {
      openPortal.mutate(
        { return_url: window.location.href },
        {
          onSuccess: () => {
            setOpen(false);
          },
          onError: (error: Error) => {
            toast.error(error.message || "Failed to open billing portal");
          },
        },
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Cancel Subscription
          </DialogTitle>
          <DialogDescription>
            Are you sure you want to cancel your subscription? This action
            cannot be easily undone.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <RadioGroup
            value={cancelOption}
            onValueChange={(v) =>
              setCancelOption(v as "period_end" | "immediately")
            }
            className="space-y-3"
          >
            <div className="flex items-start gap-3 rounded-md border p-3">
              <RadioGroupItem value="period_end" id="cancel-period" />
              <div className="space-y-1">
                <Label htmlFor="cancel-period" className="cursor-pointer">
                  Cancel at end of billing period
                </Label>
                <p className="text-xs text-muted-foreground">
                  Keep access until the current period ends. No new charges.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-md border p-3">
              <RadioGroupItem value="immediately" id="cancel-now" />
              <div className="space-y-1">
                <Label htmlFor="cancel-now" className="cursor-pointer">
                  Cancel immediately
                </Label>
                <p className="text-xs text-muted-foreground">
                  Lose access right away. No refund for the remaining period.
                </p>
              </div>
            </div>
          </RadioGroup>

          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
            {cancelOption === "period_end"
              ? "You will retain access to all paid features until the end of your current billing period."
              : "Your access will be revoked immediately. You will be downgraded to the Free plan."}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Keep Subscription
          </Button>
          <Button
            variant="destructive"
            onClick={handleCancel}
            disabled={openPortal.isPending}
          >
            {openPortal.isPending ? "Opening portal..." : "Cancel Subscription"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
