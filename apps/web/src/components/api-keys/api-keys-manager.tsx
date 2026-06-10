"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Plus, KeyRound } from "lucide-react";
import { useApiKeys } from "@/hooks/use-api-keys";
import { ApiKeysTable } from "@/components/api-keys/api-keys-table";
import { CreateKeyDialog } from "@/components/api-keys/create-key-dialog";
import { KeyDisplayOnce } from "@/components/api-keys/key-display-once";
import type { ApiKeyCreateResponse } from "@/types/api";

export function ApiKeysManager() {
  const [showRevoked, setShowRevoked] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [newKey, setNewKey] = useState<ApiKeyCreateResponse | null>(null);

  const { data, isLoading } = useApiKeys({ include_revoked: showRevoked });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <KeyRound className="h-5 w-5 text-muted-foreground" />
          <div>
            <h2 className="text-lg font-medium">API Keys</h2>
            <p className="text-sm text-muted-foreground">
              {data?.total ?? 0} key{(data?.total ?? 0) !== 1 ? "s" : ""}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Switch
              id="show-revoked"
              checked={showRevoked}
              onCheckedChange={setShowRevoked}
            />
            <Label htmlFor="show-revoked" className="text-sm text-muted-foreground">
              Show revoked
            </Label>
          </div>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create API Key
          </Button>
        </div>
      </div>

      <ApiKeysTable keys={data?.items ?? []} showRevoked={showRevoked} />

      <CreateKeyDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onKeyCreated={setNewKey}
      />

      <KeyDisplayOnce
        response={newKey}
        onDismiss={() => setNewKey(null)}
      />
    </div>
  );
}
