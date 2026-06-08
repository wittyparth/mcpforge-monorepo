"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowLeft, Trash2, Sparkles, Search, Pencil, Plus, Play, Activity,
  BarChart3, Globe, Key, Check, X, AlertTriangle,
} from "lucide-react";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ToolRow } from "@/components/builder/tool-row";
import { CredentialInput } from "@/components/builder/credential-input";
import { CredentialTestResult } from "@/components/builder/credential-test-result";
import { CopyToClipboard } from "@/components/shared/copy-to-clipboard";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { useServer } from "@/hooks/use-servers";
import { useTools, useUpdateTool, useEnhanceTools } from "@/hooks/use-tools";
import { useCredentials, useCreateCredential, useTestCredential, useDeleteCredential } from "@/hooks/use-credentials";
import { api, ApiClientError } from "@/lib/api";
import type { McpServer, ToolDefinition, CredentialInfo, CredentialCreateRequest, CredentialTestResponse } from "@/types/api";

// ── Helpers ──

const statusVariant: Record<McpServer["status"], "default" | "secondary" | "destructive" | "outline"> = {
  building: "secondary", active: "default", paused: "outline", error: "destructive",
};

function fmt(raw: string | null): string {
  if (!raw) return "—";
  return new Date(raw).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function fmtT(raw: string | null | undefined): string {
  if (!raw) return "—";
  return new Date(raw).toLocaleString("en-US", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

// ── Page ──

export default function ServerDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const qc = useQueryClient();

  const { data: server, isLoading, isError, error } = useServer(id);
  const { data: toolsData, isLoading: toolsLoading } = useTools(id);
  const { data: credsData, isLoading: credsLoading } = useCredentials(id);

  const enhanceTools = useEnhanceTools(id);
  const updateTool = useUpdateTool(id);
  const createCred = useCreateCredential(id);
  const testCred = useTestCredential(id);
  const deleteCred = useDeleteCredential(id);

  const deleteSrv = useMutation({
    mutationFn: () => api.servers.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["servers"] }); toast.success("Server deleted"); router.push("/dashboard/servers"); },
    onError: (e: unknown) => { toast.error(e instanceof ApiClientError ? e.message : "Failed to delete server"); },
  });

  const [tab, setTab] = useState("overview");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [addCredOpen, setAddCredOpen] = useState(false);
  const [toolSearch, setToolSearch] = useState("");
  const [editingTool, setEditingTool] = useState<string | null>(null);
  const [editDesc, setEditDesc] = useState("");
  const [confirmDelCred, setConfirmDelCred] = useState<string | null>(null);
  const [testOpen, setTestOpen] = useState(false);
  const [testEnvVar, setTestEnvVar] = useState("");
  const [testVal, setTestVal] = useState("");
  const [testRes, setTestRes] = useState<CredentialTestResponse | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testErr, setTestErr] = useState<string | null>(null);
  const [selTools, setSelTools] = useState<Set<string>>(new Set());

  const tools: ToolDefinition[] = (toolsData?.tools as unknown as ToolDefinition[]) ?? [];
  const filtered = toolSearch.trim() ? tools.filter(t => t.name.toLowerCase().includes(toolSearch.toLowerCase())) : tools;
  const creds: CredentialInfo[] = credsData?.credentials ?? [];

  const handleEnhance = () => enhanceTools.mutate();
  const startEdit = (t: ToolDefinition) => { setEditingTool(t.name); setEditDesc(t.description ?? ""); };
  const saveEdit = (n: string) => { updateTool.mutate({ name: n, description: editDesc }); setEditingTool(null); };
  const addCred = async (c: CredentialCreateRequest) => { await createCred.mutateAsync(c); };
  const testExisting = async () => {
    setTestLoading(true); setTestErr(null); setTestRes(null);
    try { setTestRes(await testCred.mutateAsync({ env_var_name: testEnvVar, test_value: testVal })); }
    catch (e) { setTestErr(e instanceof Error ? e.message : "Connection test failed"); }
    finally { setTestLoading(false); }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-5 w-32" />
        <div className="flex items-center justify-between"><div className="space-y-2"><Skeleton className="h-8 w-64" /><Skeleton className="h-4 w-48" /></div><div className="flex gap-2"><Skeleton className="h-9 w-28" /><Skeleton className="h-9 w-28" /></div></div>
        <Skeleton className="h-10 w-96" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (isError || !server) {
    return (
      <div className="space-y-6">
        <Link href="/dashboard/servers" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Back to servers</Link>
        <Card><CardContent className="flex flex-col items-center justify-center py-16 text-center">
          <AlertTriangle className="h-12 w-12 text-destructive/50" />
          <h3 className="mt-4 text-lg font-medium">Failed to load server</h3>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">{error instanceof Error ? error.message : "An unexpected error occurred"}</p>
          <Button variant="outline" className="mt-6" onClick={() => router.refresh()}>Try again</Button>
        </CardContent></Card>
      </div>
    );
  }

  const authScheme = server.auth_scheme ?? "none";
  const mcpUrl = `${process.env.NEXT_PUBLIC_APP_URL ?? ""}/mcp/v1/${server.slug}/sse`;

  return (
    <div className="space-y-6">
      <Link href="/dashboard/servers" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Back to servers</Link>

      {/* ── Header ── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{server.name}</h1>
            <Badge variant={statusVariant[server.status]}>{server.status}</Badge>
          </div>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{server.slug}</code>
            <span>Created {fmt(server.created_at)}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <CopyToClipboard value={mcpUrl} label="MCP endpoint URL" />
          <Button variant="outline" size="sm" disabled><Play className="h-4 w-4" />Open in Playground</Button>
          <Button variant="destructive" size="sm" onClick={() => setDeleteOpen(true)}><Trash2 className="h-4 w-4" />Delete</Button>
        </div>
      </div>

      {/* ── Tabs ── */}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="w-full sm:w-auto">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="tools">Tools</TabsTrigger>
          <TabsTrigger value="credentials">Credentials</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        {/* ══ Overview ══ */}
        <TabsContent value="overview" className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Server Information</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
                {[{ l: "Name", v: server.name },
                  { l: "Slug", v: <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{server.slug}</code> },
                  { l: "Base URL", v: <span className="inline-flex items-center gap-1"><Globe className="h-3.5 w-3.5 text-muted-foreground" />{server.base_url}</span> },
                  { l: "Auth Scheme", v: server.auth_scheme },
                  { l: "Transport Mode", v: server.transport_mode },
                  { l: "Version", v: `v${server.version}` },
                  { l: "Total Calls", v: server.total_calls?.toLocaleString() ?? "0" },
                  { l: "Monthly Calls", v: server.monthly_calls?.toLocaleString() ?? "0" },
                  { l: "Last Called", v: fmtT(server.last_call_at) },
                  { l: "Created", v: fmtT(server.created_at) },
                ].map(r => (
                  <div key={r.l} className="flex flex-col gap-0.5">
                    <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{r.l}</span>
                    <span className="text-sm">{r.v}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div><CardTitle>AI Description Engine</CardTitle><CardDescription>Rewrite tool descriptions to maximize LLM selection probability</CardDescription></div>
              <Sparkles className="h-5 w-5 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <p className="mb-4 text-sm text-muted-foreground">Enhance all tool descriptions with AI-optimized language for better LLM tool selection (260% lift vs. mechanical descriptions).</p>
              <Button onClick={handleEnhance} disabled={enhanceTools.isPending}>
                {enhanceTools.isPending ? <><LoadingSpinner size="sm" />Enhancing...</> : <><Sparkles className="h-4 w-4" />Enhance descriptions</>}
              </Button>
            </CardContent>
          </Card>

          <Card className="border-destructive/30">
            <CardHeader><CardTitle className="text-destructive">Danger Zone</CardTitle><CardDescription>Irreversible actions affecting this server</CardDescription></CardHeader>
            <CardContent>
              <div className="flex items-center justify-between rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-3">
                <div><p className="text-sm font-medium">Delete this server</p><p className="text-xs text-muted-foreground">Permanently remove this MCP server and all associated data</p></div>
                <Button variant="destructive" size="sm" onClick={() => setDeleteOpen(true)}><Trash2 className="h-4 w-4" />Delete server</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ══ Tools ══ */}
        <TabsContent value="tools" className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <Button onClick={handleEnhance} disabled={enhanceTools.isPending} size="sm">
              {enhanceTools.isPending ? <><LoadingSpinner size="sm" />Enhancing...</> : <><Sparkles className="h-4 w-4" />Enhance all descriptions</>}
            </Button>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input placeholder="Search tools..." value={toolSearch} onChange={e => setToolSearch(e.target.value)} className="h-9 w-full pl-8 sm:w-64" />
            </div>
          </div>

          {toolsLoading ? (
            <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-md" />)}</div>
          ) : filtered.length === 0 ? (
            <EmptyState title={toolSearch.trim() ? "No matching tools" : "No tools generated yet"}
              description={toolSearch.trim() ? "Try a different search term" : "Tools will appear here after generating from an OpenAPI spec"} icon={Search} />
          ) : (
            <ScrollArea className="max-h-[600px]">
              <div className="space-y-1 pr-4">
                {filtered.map(tool => (
                  <div key={tool.name} className="rounded-lg border bg-card">
                    <ToolRow tool={tool} selected={selTools.has(tool.name)} onToggle={() => {
                      const next = new Set(selTools);
                      if (next.has(tool.name)) { next.delete(tool.name); } else { next.add(tool.name); }
                      setSelTools(next);
                    }} />
                    <div className="flex items-center justify-between border-t border-border/50 px-3 py-2">
                      <div className="flex items-center gap-2">
                        {editingTool === tool.name ? (
                          <div className="flex items-center gap-2">
                            <Input value={editDesc} onChange={e => setEditDesc(e.target.value)} className="h-7 w-64 text-xs" placeholder="Tool description..." />
                            <button onClick={() => saveEdit(tool.name)} className="rounded p-0.5 text-emerald-500 hover:text-emerald-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" aria-label="Save"><Check className="h-3.5 w-3.5" /></button>
                            <button onClick={() => setEditingTool(null)} className="rounded p-0.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" aria-label="Cancel"><X className="h-3.5 w-3.5" /></button>
                          </div>
                        ) : (
                          <>
                            <span className="text-xs text-muted-foreground line-clamp-1">{tool.description || <span className="italic">No description</span>}</span>
                            <button onClick={() => startEdit(tool)} className="rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" aria-label={`Edit ${tool.name}`}><Pencil className="h-3 w-3" /></button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </TabsContent>

        {/* ══ Credentials ══ */}
        <TabsContent value="credentials" className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">API keys and tokens for authenticating tool calls</p>
            <Dialog open={addCredOpen} onOpenChange={setAddCredOpen}>
              <DialogTrigger asChild><Button size="sm"><Plus className="h-4 w-4" />Add credential</Button></DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader><DialogTitle>Add credential</DialogTitle><DialogDescription>Add an API key or token for <code className="rounded bg-muted px-1 font-mono text-xs">{server.slug}</code>. Values are encrypted at rest.</DialogDescription></DialogHeader>
                <CredentialInput authScheme={authScheme} existingCredentials={creds} onAdd={async c => { await addCred(c); setAddCredOpen(false); }} onTest={c => testCred.mutateAsync(c)} />
              </DialogContent>
            </Dialog>
          </div>

          {credsLoading ? (
            <div className="space-y-2">{Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-lg" />)}</div>
          ) : creds.length === 0 ? (
            <EmptyState title="No credentials added" description="Add credentials to enable authenticated tool calls. Values are encrypted at rest." icon={Key}
              action={<Button size="sm" onClick={() => setAddCredOpen(true)}><Plus className="h-4 w-4" />Add credential</Button>} />
          ) : (
            <div className="space-y-3">
              {creds.map(c => (
                <Card key={c.id}>
                  <CardContent className="flex items-center justify-between p-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm font-semibold">{c.env_var_name}</code>
                        <Badge variant="secondary" className="text-[10px]">{c.auth_scheme}</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">Created {fmt(c.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="sm" onClick={() => { setTestEnvVar(c.env_var_name); setTestVal(""); setTestRes(null); setTestErr(null); setTestOpen(true); }}>Test</Button>
                      <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setConfirmDelCred(c.env_var_name)}><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
          <p className="text-center text-xs text-muted-foreground">Values are encrypted at rest and never returned by the API.</p>
        </TabsContent>

        {/* ══ Analytics ══ */}
        <TabsContent value="analytics" className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[{ i: Activity, l: "Total Calls", v: server.total_calls?.toLocaleString() ?? "0" },
              { i: BarChart3, l: "Monthly Calls", v: server.monthly_calls?.toLocaleString() ?? "0" },
              { i: Globe, l: "Last Called", v: fmtT(server.last_call_at) },
              { i: Activity, l: "Version", v: `v${server.version}` },
            ].map(s => (
              <Card key={s.l}>
                <CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">{s.l}</CardTitle><s.i className="h-4 w-4 text-muted-foreground" /></CardHeader>
                <CardContent><p className="text-2xl font-semibold">{s.v}</p></CardContent>
              </Card>
            ))}
          </div>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div><CardTitle>Usage Analytics</CardTitle><CardDescription>Detailed metrics and charts for tool usage</CardDescription></div>
              <BarChart3 className="h-5 w-5 text-muted-foreground" />
            </CardHeader>
            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
              <BarChart3 className="h-12 w-12 text-muted-foreground/30" />
              <h3 className="mt-4 text-lg font-medium">Analytics coming in Phase 7</h3>
              <p className="mt-2 max-w-md text-sm text-muted-foreground">Detailed usage analytics, request logs, and performance metrics will be available in a future release.</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ── Delete server dialog ── */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>Delete server</DialogTitle><DialogDescription>Are you sure you want to delete <strong>{server.name}</strong>? This action cannot be undone.</DialogDescription></DialogHeader>
          <DialogFooter>
            <DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose>
            <Button variant="destructive" onClick={() => { deleteSrv.mutate(); setDeleteOpen(false); }} disabled={deleteSrv.isPending}>{deleteSrv.isPending ? "Deleting..." : "Delete server"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Delete credential dialog ── */}
      <Dialog open={!!confirmDelCred} onOpenChange={o => { if (!o) setConfirmDelCred(null); }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader><DialogTitle>Delete credential</DialogTitle><DialogDescription>Are you sure you want to delete <code className="rounded bg-muted px-1 font-mono text-xs">{confirmDelCred}</code>? This action cannot be undone.</DialogDescription></DialogHeader>
          <DialogFooter>
            <DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose>
            <Button variant="destructive" onClick={() => { if (confirmDelCred) { deleteCred.mutate(confirmDelCred); setConfirmDelCred(null); } }} disabled={deleteCred.isPending}>{deleteCred.isPending ? "Deleting..." : "Delete credential"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Test credential dialog ── */}
      <Dialog open={testOpen} onOpenChange={setTestOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>Test credential</DialogTitle><DialogDescription>Enter the value for <code className="rounded bg-muted px-1 font-mono text-xs">{testEnvVar}</code> to test the connection. The value is not stored.</DialogDescription></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2"><Label htmlFor="test-val">Credential value</Label><Input id="test-val" type="password" placeholder="Enter credential value to test" value={testVal} onChange={e => setTestVal(e.target.value)} /></div>
            <Button onClick={testExisting} disabled={testLoading || !testVal.trim()} className="w-full">{testLoading ? <><LoadingSpinner size="sm" />Testing...</> : "Test Connection"}</Button>
            {(testRes || testLoading || testErr) && <CredentialTestResult result={testRes} loading={testLoading} error={testErr} />}
          </div>
          <DialogFooter className="sm:justify-start"><DialogClose asChild><Button variant="outline">Close</Button></DialogClose></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
