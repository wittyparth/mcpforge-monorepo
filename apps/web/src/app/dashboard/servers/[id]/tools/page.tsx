"use client";

import { use, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Sparkles,
  Search,
  Pencil,
  Check,
  X,
  AlertTriangle,
} from "lucide-react";

import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { ToolRow } from "@/components/builder/tool-row";
import { AiReviewPanel } from "@/components/builder/ai-review-panel";
import { useServer } from "@/hooks/use-servers";
import {
  useTools,
  useUpdateTool,
  useEnhanceTools,
} from "@/hooks/use-tools";
import type { ToolDefinition } from "@/types/api";

// ── Helpers ──

function fmt(raw: string | null | undefined): string {
  if (!raw) return "—";
  return new Date(raw).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// ── Page ──

export default function ServerToolsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();

  const {
    data: server,
    isLoading: serverLoading,
    isError: serverError,
    error: serverErr,
  } = useServer(id);
  const { data: toolsData, isLoading: toolsLoading } = useTools(id);

  const enhanceTools = useEnhanceTools(id);
  const updateTool = useUpdateTool(id);

  const [tab, setTab] = useState("ai-review");
  const [toolSearch, setToolSearch] = useState("");
  const [editingTool, setEditingTool] = useState<string | null>(null);
  const [editDesc, setEditDesc] = useState("");
  const [selTools, setSelTools] = useState<Set<string>>(new Set());

  const tools: ToolDefinition[] =
    (toolsData?.tools as unknown as ToolDefinition[]) ?? [];
  const filtered = toolSearch.trim()
    ? tools.filter((t) =>
        t.name.toLowerCase().includes(toolSearch.toLowerCase()),
      )
    : tools;

  const handleEnhance = useCallback(() => {
    enhanceTools.mutate();
  }, [enhanceTools]);

  const handleAcceptAll = useCallback(() => {
    // Accept all currently pending tools — future: send to API
  }, []);

  const startEdit = useCallback((t: ToolDefinition) => {
    setEditingTool(t.name);
    setEditDesc(t.description ?? "");
  }, []);

  const saveEdit = useCallback(
    (n: string) => {
      updateTool.mutate({ name: n, description: editDesc });
      setEditingTool(null);
    },
    [updateTool, editDesc],
  );

  const cancelEdit = useCallback(() => {
    setEditingTool(null);
    setEditDesc("");
  }, []);

  // ── Loading state ──
  if (serverLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-10 w-96" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  // ── Error state ──
  if (serverError || !server) {
    return (
      <div className="space-y-6">
        <Link
          href="/dashboard/servers"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to servers
        </Link>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <AlertTriangle className="h-12 w-12 text-destructive/50" />
            <h3 className="mt-4 text-lg font-medium">Failed to load server</h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              {serverErr instanceof Error
                ? serverErr.message
                : "An unexpected error occurred"}
            </p>
            <Button
              variant="outline"
              className="mt-6"
              onClick={() => router.refresh()}
            >
              Try again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link
        href={`/dashboard/servers/${id}`}
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to {server.name}
      </Link>

      {/* ── Header ── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            {server.name} — Tools
          </h1>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
              {server.slug}
            </code>
            <span>{tools.length} tools</span>
            <span>Updated {fmt(server.updated_at)}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={handleEnhance}
            disabled={enhanceTools.isPending}
          >
            {enhanceTools.isPending ? (
              <>
                <LoadingSpinner size="sm" />
                Enhancing...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Enhance all
              </>
            )}
          </Button>
        </div>
      </div>

      {/* ── Tabs ── */}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="w-full sm:w-auto">
          <TabsTrigger value="ai-review" className="gap-1.5">
            <Sparkles className="h-3.5 w-3.5" />
            AI Review
          </TabsTrigger>
          <TabsTrigger value="manual-edit" className="gap-1.5">
            <Pencil className="h-3.5 w-3.5" />
            Manual Edit
          </TabsTrigger>
        </TabsList>

        {/* ══ AI Review Tab ══ */}
        <TabsContent value="ai-review">
          {toolsLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="space-y-2 rounded-xl border p-4">
                  <Skeleton className="h-5 w-48" />
                  <Skeleton className="h-3 w-32" />
                  <Skeleton className="h-16 w-full" />
                </div>
              ))}
            </div>
          ) : tools.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                <Sparkles className="h-12 w-12 text-muted-foreground/30" />
                <h3 className="mt-4 text-lg font-medium">
                  No tools to review
                </h3>
                <p className="mt-2 max-w-md text-sm text-muted-foreground">
                  Generate tools from an OpenAPI spec first, then come back
                  to review AI-enhanced descriptions.
                </p>
                <Button
                  variant="outline"
                  className="mt-6"
                  onClick={() =>
                    router.push(`/dashboard/servers/${id}`)
                  }
                >
                  Go to server overview
                </Button>
              </CardContent>
            </Card>
          ) : (
            <AiReviewPanel
              serverId={id}
              tools={[]}
              onEnhanceAll={handleEnhance}
              onAcceptAll={handleAcceptAll}
              isEnhancing={enhanceTools.isPending}
            />
          )}
        </TabsContent>

        {/* ══ Manual Edit Tab ══ */}
        <TabsContent value="manual-edit" className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              Manually edit tool descriptions without AI enhancement.
            </p>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search tools..."
                value={toolSearch}
                onChange={(e) => setToolSearch(e.target.value)}
                className="h-9 w-full pl-8 sm:w-64"
              />
            </div>
          </div>

          {toolsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full rounded-md" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              title={
                toolSearch.trim() ? "No matching tools" : "No tools generated yet"
              }
              description={
                toolSearch.trim()
                  ? "Try a different search term"
                  : "Tools will appear here after generating from an OpenAPI spec"
              }
              icon={Search}
            />
          ) : (
            <div className="overflow-y-auto max-h-[600px] rounded-lg border bg-card">
              <div className="divide-y divide-border/50">
                {filtered.map((tool) => (
                  <div key={tool.name}>
                    <ToolRow
                      tool={tool}
                      selected={selTools.has(tool.name)}
                      onToggle={() => {
                        const next = new Set(selTools);
                        if (next.has(tool.name)) {
                          next.delete(tool.name);
                        } else {
                          next.add(tool.name);
                        }
                        setSelTools(next);
                      }}
                    />
                    <div className="flex items-center justify-between px-3 py-2 bg-muted/10">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        {editingTool === tool.name ? (
                          <div className="flex items-center gap-2 w-full">
                            <Input
                              value={editDesc}
                              onChange={(e) => setEditDesc(e.target.value)}
                              className="h-7 flex-1 text-xs"
                              placeholder="Tool description..."
                            />
                            <button
                              onClick={() => saveEdit(tool.name)}
                              className="shrink-0 rounded p-0.5 text-emerald-500 hover:text-emerald-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                              aria-label="Save"
                            >
                              <Check className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={cancelEdit}
                              className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                              aria-label="Cancel"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        ) : (
                          <>
                            <span className="text-xs text-muted-foreground line-clamp-1 flex-1">
                              {tool.description || (
                                <span className="italic">No description</span>
                              )}
                            </span>
                            <button
                              onClick={() => startEdit(tool)}
                              className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                              aria-label={`Edit ${tool.name}`}
                            >
                              <Pencil className="h-3 w-3" />
                            </button>
                          </>
                        )}
                      </div>
                      {tool.warnings && tool.warnings.length > 0 && (
                        <Badge variant="outline" className="text-[10px] shrink-0 ml-2">
                          {tool.warnings.length} warning
                          {tool.warnings.length > 1 ? "s" : ""}
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
