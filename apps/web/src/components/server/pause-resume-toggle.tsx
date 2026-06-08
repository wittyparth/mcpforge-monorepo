"use client";

import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { usePauseServer, useResumeServer } from "@/hooks/use-gateway";

interface PauseResumeToggleProps {
  serverId: string;
  status: "active" | "paused";
}

export function PauseResumeToggle({ serverId, status }: PauseResumeToggleProps) {
  const pause = usePauseServer(serverId);
  const resume = useResumeServer(serverId);

  const isPaused = status === "paused";
  const isPending = pause.isPending || resume.isPending;

  const handleToggle = (checked: boolean) => {
    if (checked) {
      resume.mutate();
    } else {
      pause.mutate();
    }
  };

  return (
    <div className="flex items-center gap-3">
      <Switch
        id="server-status"
        checked={!isPaused}
        onCheckedChange={handleToggle}
        disabled={isPending}
      />
      <Label htmlFor="server-status" className="text-sm">
        Server Status:{" "}
        <span className={isPaused ? "text-muted-foreground" : "text-emerald-500"}>
          {isPaused ? "Paused" : "Active"}
        </span>
      </Label>
    </div>
  );
}
