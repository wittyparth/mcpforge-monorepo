"use client";

import { useState } from "react";
import { Rocket } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { useDeployServer } from "@/hooks/use-gateway";

interface DeployButtonProps {
  serverId: string;
  status: string;
}

export function DeployButton({ serverId, status }: DeployButtonProps) {
  const [open, setOpen] = useState(false);
  const deploy = useDeployServer(serverId);

  if (status === "active") return null;

  if (status === "building") {
    return (
      <Button disabled size="sm">
        <Rocket className="mr-2 h-4 w-4" />
        Building...
      </Button>
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Rocket className="mr-2 h-4 w-4" />
          Deploy
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Deploy server</DialogTitle>
          <DialogDescription>
            This will start the build pipeline and deploy your MCP server gateway.
            The server will become available via the gateway URL once the build
            completes.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button
            onClick={() => {
              deploy.mutate();
              setOpen(false);
            }}
            disabled={deploy.isPending}
          >
            {deploy.isPending ? "Starting..." : "Deploy now"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
