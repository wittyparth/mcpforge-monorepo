"use client";

import { ApiKeysManager } from "@/components/api-keys/api-keys-manager";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Info } from "lucide-react";

export default function ApiKeysPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">API Keys</h1>
        <p className="text-sm text-muted-foreground">
          Manage API keys for programmatic access to MCPForge
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Info className="h-4 w-4" />
            About API Keys
          </CardTitle>
          <CardDescription>
            API keys allow you to authenticate with the MCPForge API
            programmatically. Use them in CI/CD pipelines, scripts, or
            third-party integrations.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <ul className="list-inside list-disc space-y-1">
            <li>
              Keys have the format{" "}
              <code className="rounded bg-muted px-1 font-mono text-xs">
                mcpforge_live_...
              </code>
            </li>
            <li>
              The full key is shown only once at creation. Store it securely.
            </li>
            <li>
              Keys can be revoked but not recovered. A revoked key cannot be
              re-enabled.
            </li>
            <li>
              Use the{" "}
              <code className="rounded bg-muted px-1 font-mono text-xs">
                Authorization: Bearer mcpforge_live_...
              </code>{" "}
              header to authenticate requests.
            </li>
          </ul>
        </CardContent>
      </Card>

      <ApiKeysManager />
    </div>
  );
}
