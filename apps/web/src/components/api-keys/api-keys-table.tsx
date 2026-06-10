"use client";

import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { MoreHorizontal, Trash2, KeyRound } from "lucide-react";
import { RevokeKeyDialog } from "@/components/api-keys/revoke-key-dialog";
import type { ApiKeyResponse } from "@/types/api";

interface ApiKeysTableProps {
  keys: ApiKeyResponse[];
  showRevoked: boolean;
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "Never";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 30) return `${diffDays} days ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
}

function formatExpiration(expiresAt: string | null): string {
  if (!expiresAt) return "Never";
  const date = new Date(expiresAt);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays <= 0) return "Expired";
  if (diffDays === 1) return "Expires tomorrow";
  if (diffDays <= 30) return `Expires in ${diffDays} days`;
  if (diffDays <= 365) return `Expires in ${Math.floor(diffDays / 30)} months`;
  return `Expires in ${Math.floor(diffDays / 365)} years`;
}

const SCOPE_VARIANTS: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  "servers:read": "secondary",
  "servers:write": "secondary",
  "analytics:read": "secondary",
  admin: "destructive",
};

export function ApiKeysTable({ keys, showRevoked }: ApiKeysTableProps) {
  const [revokeTarget, setRevokeTarget] = useState<ApiKeyResponse | null>(null);

  const displayKeys = showRevoked
    ? keys
    : keys.filter((k) => !k.revoked_at);

  if (displayKeys.length === 0) {
    return (
      <div className="rounded-md border p-8 text-center">
        <KeyRound className="mx-auto h-10 w-10 text-muted-foreground/50" />
        <p className="mt-3 text-sm text-muted-foreground">
          You haven&apos;t created any API keys yet.
        </p>
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Key</TableHead>
              <TableHead>Scopes</TableHead>
              <TableHead className="hidden md:table-cell">Last Used</TableHead>
              <TableHead className="hidden md:table-cell">Created</TableHead>
              <TableHead className="hidden md:table-cell">Expires</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayKeys.map((key) => {
              const isRevoked = !!key.revoked_at;
              return (
                <TableRow
                  key={key.id}
                  className={isRevoked ? "opacity-50" : ""}
                >
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span
                        className={
                          isRevoked
                            ? "font-medium line-through"
                            : "font-medium"
                        }
                      >
                        {key.name}
                      </span>
                      {isRevoked && (
                        <Badge variant="destructive" className="text-xs">
                          Revoked
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                      {key.key_prefix}...
                    </code>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {key.scopes.map((scope) => (
                        <Tooltip key={scope}>
                          <TooltipTrigger>
                            <Badge
                              variant={SCOPE_VARIANTS[scope] ?? "secondary"}
                              className="text-xs"
                            >
                              {scope}
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>{scope === "admin" ? "Full access to all resources" : scope}</p>
                          </TooltipContent>
                        </Tooltip>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                    {formatRelativeTime(key.last_used_at)}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                    {formatRelativeTime(key.created_at)}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                    {formatExpiration(key.expires_at)}
                  </TableCell>
                  <TableCell>
                    {!isRevoked && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                            <span className="sr-only">Actions</span>
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() => setRevokeTarget(key)}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Revoke
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {revokeTarget && (
        <RevokeKeyDialog
          open={!!revokeTarget}
          onOpenChange={(open) => {
            if (!open) setRevokeTarget(null);
          }}
          keyId={revokeTarget.id}
          keyName={revokeTarget.name}
        />
      )}
    </TooltipProvider>
  );
}
