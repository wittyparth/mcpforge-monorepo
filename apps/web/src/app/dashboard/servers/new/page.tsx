"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  Check,
  ChevronRight,
  FileJson,
  Flame,
  Play,
  RotateCcw,
  Server,
  Settings,
  Sparkles,
  Terminal,
  Wand2,
  XCircle,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

import { SpecInput } from "@/components/builder/spec-input";
import { ToolWorkspace } from "@/components/builder/tool-workspace";
import { ServerConfigForm } from "@/components/builder/server-config-form";
import type { ServerConfigFormData } from "@/components/builder/server-config-form";
import { AuthSchemeSelector } from "@/components/builder/auth-scheme-selector";
import { CredentialInput } from "@/components/builder/credential-input";
import { BuildStepIndicator } from "@/components/builder/build-step-indicator";

import { useSelectTools } from "@/hooks/use-spec";
import { useCreateCredential, useTestCredential } from "@/hooks/use-credentials";
import { useStartBuild, useBuildStatus } from "@/hooks/use-build-status";

import type {
  AuthScheme,
  BuildStatusEvent,
  CredentialCreateRequest,
  CredentialTestRequest,
  CredentialTestResponse,
  CredentialInfo,
  McpServer,
  SpecUploadResponse,
} from "@/types/api";

// ── Wizard step definitions ─────────────────────────────────────────

const WIZARD_STEPS = [
  { label: "Spec", icon: FileJson },
  { label: "Tools", icon: Settings },
  { label: "Configure", icon: Server },
  { label: "Build", icon: Play },
] as const;

interface WizardStepperProps {
  currentStep: number;
  onStepClick: (step: number) => void;
}

function WizardStepper({ currentStep, onStepClick }: WizardStepperProps) {
  return (
    <div className="flex items-center justify-center gap-0 mb-8">
      {WIZARD_STEPS.map((step, idx) => {
        const stepNum = idx + 1;
        const state =
          stepNum < currentStep
            ? "complete"
            : stepNum === currentStep
              ? "current"
              : "upcoming";
        const Icon = state === "complete" ? Check : step.icon;

        return (
          <React.Fragment key={step.label}>
            <div className="flex flex-col items-center gap-2">
              <button
                type="button"
                onClick={() => onStepClick(stepNum)}
                disabled={stepNum > currentStep}
                className={cn(
                  "flex flex-col items-center gap-2 transition-opacity",
                  stepNum > currentStep && "cursor-default",
                  state === "complete" && "cursor-pointer",
                )}
                aria-current={state === "current" ? "step" : undefined}
              >
                <div
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all duration-300",
                    state === "complete" &&
                      "border-emerald-500 bg-emerald-500 text-white",
                    state === "current" &&
                      "border-primary bg-primary/10 text-primary",
                    state === "upcoming" &&
                      "border-muted-foreground/30 text-muted-foreground/50",
                  )}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <span
                  className={cn(
                    "text-xs font-medium transition-colors duration-200",
                    state === "complete" &&
                      "text-emerald-600 dark:text-emerald-400",
                    state === "current" && "text-primary font-semibold",
                    state === "upcoming" && "text-muted-foreground/50",
                  )}
                >
                  {step.label}
                </span>
              </button>
            </div>
            {idx < WIZARD_STEPS.length - 1 && (
              <div className="flex items-center pt-5 px-2">
                <div
                  className={cn(
                    "h-0.5 w-12 sm:w-16 transition-colors duration-300 rounded-full",
                    state === "complete"
                      ? "bg-emerald-500"
                      : "bg-muted-foreground/20",
                  )}
                />
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ── Page component ──────────────────────────────────────────────────

export default function NewServerWizardPage() {
  const router = useRouter();

  // Wizard state
  const [step, setStep] = React.useState<1 | 2 | 3 | 4>(1);
  const [specResponse, setSpecResponse] = React.useState<SpecUploadResponse | null>(null);
  const [selectedToolSet, setSelectedToolSet] = React.useState<Set<string>>(new Set());
  const customizationsRef = React.useRef<Record<string, Record<string, unknown>>>({});
  const [server, setServer] = React.useState<McpServer | null>(null);
  const [authScheme, setAuthScheme] = React.useState<AuthScheme>("none");
  const [isCreatingServer, setIsCreatingServer] = React.useState(false);
  const [createServerError, setCreateServerError] = React.useState<string | null>(null);

  // Build state
  const [buildKey, setBuildKey] = React.useState(0);
  const [buildEvents, setBuildEvents] = React.useState<BuildStatusEvent[]>([]);

  // Hooks — created unconditionally with fallback values
  const selectTools = useSelectTools(specResponse?.spec_id ?? "");
  const createCredential = useCreateCredential(server?.id ?? "");
  const testCredential = useTestCredential(server?.id ?? "");
  const startBuild = useStartBuild(server?.id ?? "");
  const buildStatus = useBuildStatus(server?.id ?? "");

  // Step navigation — clicking a completed step goes back
  const handleStepClick = React.useCallback(
    (targetStep: number) => {
      if (targetStep < step) {
        setStep(targetStep as 1 | 2 | 3 | 4);
      }
    },
    [step],
  );

  // ── Step 1 handlers ──────────────────────────────────────────────

  const handleSpecSuccess = React.useCallback((spec: SpecUploadResponse) => {
    setSpecResponse(spec);
    setSelectedToolSet(new Set((spec.tools ?? []).filter((t) => t.selected).map((t) => t.name)));
    setStep(2);
  }, []);

  const handleSpecError = React.useCallback((error: string) => {
    toast.error(error);
  }, []);

  // ── Step 2 handlers ──────────────────────────────────────────────

  const handleToolToggle = React.useCallback((name: string) => {
    setSelectedToolSet((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }, []);

  const handleSelectAll = React.useCallback((names: string[]) => {
    setSelectedToolSet((prev) => {
      const next = new Set(prev);
      for (const name of names) next.add(name);
      return next;
    });
  }, []);

  const handleDeselectAll = React.useCallback((names: string[]) => {
    setSelectedToolSet((prev) => {
      const next = new Set(prev);
      for (const name of names) next.delete(name);
      return next;
    });
  }, []);

  const handleToolsConfirm = React.useCallback(() => {
    if (selectedToolSet.size === 0) return;
    setStep(3);
  }, [selectedToolSet]);

  // ── Step 3 handlers ──────────────────────────────────────────────

  const handleServerConfigSubmit = React.useCallback(
    async (formData: ServerConfigFormData) => {
      if (!specResponse) return;

      setIsCreatingServer(true);
      setCreateServerError(null);

      try {
        const createdServer = await selectTools.mutateAsync({
          slug: formData.slug,
          name: formData.name,
          base_url: formData.base_url,
          description: formData.description || null,
          auth_scheme: authScheme,
          selected_tool_names: Array.from(selectedToolSet),
          customizations:
            Object.keys(customizationsRef.current).length > 0
              ? customizationsRef.current
              : null,
          transport_mode: formData.transport_mode,
        });
        setServer(createdServer);
        toast.success("Server created! You can now add credentials.");
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to create server";
        setCreateServerError(message);
      } finally {
        setIsCreatingServer(false);
      }
    },
    [specResponse, selectTools, authScheme, selectedToolSet],
  );

  const handleAddCredential = React.useCallback(
    async (cred: CredentialCreateRequest): Promise<void> => {
      if (!server) return;
      await createCredential.mutateAsync(cred);
    },
    [server, createCredential],
  );

  const handleTestCredential = React.useCallback(
    async (cred: CredentialTestRequest): Promise<CredentialTestResponse> => {
      if (!server) {
        throw new Error("Server not created yet");
      }
      return testCredential.mutateAsync(cred);
    },
    [server, testCredential],
  );

  // ── Step 4 — build pipeline ──────────────────────────────────────

  const currentStage = buildStatus.status?.stage;

  // Start build when entering step 4 or when buildKey changes (retry)
  React.useEffect(() => {
    if (step !== 4 || !server) return;

    const aborted = { current: false };

    startBuild
      .mutateAsync()
      .then(() => {
        if (!aborted.current) {
          buildStatus.start();
        }
      })
      .catch(() => {
        // Error is surfaced via hook onError toast
      });

    return () => {
      aborted.current = true;
      buildStatus.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, server?.id, buildKey]);

  // Accumulate SSE events
  React.useEffect(() => {
    const latest = buildStatus.status;
    if (latest) {
      setBuildEvents((prev) => [...prev, latest]);
    }
  }, [buildStatus.status]);

  const isBuildComplete = currentStage === "complete";
  const isBuildError =
    currentStage === "error" || (buildStatus.error !== null && !isBuildComplete);

  const handleRetryBuild = React.useCallback(() => {
    setBuildEvents([]);
    setBuildKey((prev) => prev + 1);
  }, []);

  // Redirect on build complete (with brief delay so user sees final state)
  React.useEffect(() => {
    if (isBuildComplete && server) {
      const timer = setTimeout(() => {
        router.push(`/dashboard/servers/${server.id}`);
      }, 1200);
      return () => clearTimeout(timer);
    }
  }, [isBuildComplete, server, router]);

  // ── Derived values ───────────────────────────────────────────────

  const isServerCreated = server !== null;

  // ── Render ───────────────────────────────────────────────────────

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {step < 4 && (
        <Link
          href={step === 1 ? "/dashboard/servers" : "#"}
          onClick={(e) => {
            if (step > 1) {
              e.preventDefault();
              setStep((prev) => (prev - 1) as 1 | 2 | 3);
            }
          }}
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          {step === 1 ? "Back to servers" : "Back"}
        </Link>
      )}

      <WizardStepper currentStep={step} onStepClick={handleStepClick} />

      {step === 1 && (
        <section aria-label="Step 1: Import OpenAPI Spec">
          <SpecInput
            onSuccess={handleSpecSuccess}
            onError={handleSpecError}
          />
        </section>
      )}

      {step === 2 && specResponse && (
        <section aria-label="Step 2: Select Tools">
          <ToolWorkspace
            tools={specResponse.tools ?? []}
            selected={selectedToolSet}
            onToggle={handleToolToggle}
            onSelectAll={handleSelectAll}
            onDeselectAll={handleDeselectAll}
            onConfirm={handleToolsConfirm}
            onConfirmDisabled={selectedToolSet.size === 0}
          />
        </section>
      )}

      {step === 3 && specResponse && (
        <section aria-label="Step 3: Configure Server" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Settings className="h-5 w-5 text-primary" />
                Authentication
              </CardTitle>
              <CardDescription>
                Choose how your API authenticates requests.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AuthSchemeSelector
                value={authScheme}
                onChange={setAuthScheme}
              />
            </CardContent>
          </Card>

          <ServerConfigForm
            onSubmit={handleServerConfigSubmit}
            isSubmitting={isCreatingServer}
            defaultValues={{
              base_url: specResponse.tools?.[0]?.base_url_override ?? "",
            }}
          />

          {createServerError && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/50 p-3 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>{createServerError}</p>
            </div>
          )}

          {isServerCreated && (
            <>
              <Separator className="my-2" />

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Server className="h-5 w-5 text-primary" />
                    Credentials
                  </CardTitle>
                  <CardDescription>
                    Add API credentials so your server can authenticate
                    requests to the upstream API.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <CredentialInput
                    onAdd={handleAddCredential}
                    onTest={handleTestCredential}
                    existingCredentials={[] as CredentialInfo[]}
                    authScheme={authScheme}
                  />
                </CardContent>
              </Card>

              <Button
                size="lg"
                className="w-full gap-2"
                onClick={() => setStep(4)}
              >
                <Play className="h-4 w-4" />
                Continue to Build
              </Button>
            </>
          )}
        </section>
      )}

      {step === 4 && server && (
        <section aria-label="Step 4: Build Progress" className="space-y-6">
          <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-card via-card to-muted/50 shadow-xl">
            <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary via-purple-500 to-emerald-500 opacity-80" />

            <div className="p-6 space-y-6">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <div className="relative">
                      <div className={cn(
                        "flex h-10 w-10 items-center justify-center rounded-xl",
                        isBuildComplete
                          ? "bg-emerald-500/10 text-emerald-500"
                          : isBuildError
                            ? "bg-destructive/10 text-destructive"
                            : "bg-primary/10 text-primary"
                      )}>
                        {isBuildComplete ? (
                          <Check className="h-5 w-5" />
                        ) : isBuildError ? (
                          <XCircle className="h-5 w-5" />
                        ) : (
                          <Sparkles className="h-5 w-5 animate-pulse" />
                        )}
                      </div>
                      {!isBuildComplete && !isBuildError && (
                        <span className="absolute -top-1 -right-1 flex h-3 w-3">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                          <span className="relative inline-flex rounded-full h-3 w-3 bg-primary" />
                        </span>
                      )}
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold tracking-tight">
                        {isBuildComplete
                          ? "Build Complete"
                          : isBuildError
                            ? "Build Failed"
                            : "Building MCP Server"}
                      </h2>
                      <p className="text-sm text-muted-foreground">
                        {isBuildComplete
                          ? "Your server is ready to use"
                          : isBuildError
                            ? "Something went wrong"
                            : "AI-enhancing tool descriptions…"}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold tabular-nums tracking-tight">
                    {buildStatus.status?.progress ?? 0}%
                  </div>
                  <div className="text-xs text-muted-foreground font-medium">
                    {buildEvents.length} event{buildEvents.length !== 1 ? "s" : ""}
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-foreground flex items-center gap-2">
                    {currentStage === "parsing" && <Zap className="h-3.5 w-3.5 text-blue-500" />}
                    {currentStage === "generating" && <Wand2 className="h-3.5 w-3.5 text-purple-500" />}
                    {currentStage === "testing" && <Flame className="h-3.5 w-3.5 text-amber-500" />}
                    {currentStage === "deploying" && <Server className="h-3.5 w-3.5 text-cyan-500" />}
                    {currentStage === "complete" && <Check className="h-3.5 w-3.5 text-emerald-500" />}
                    {currentStage === "error" && <AlertCircle className="h-3.5 w-3.5 text-destructive" />}
                    {currentStage
                      ? currentStage === "complete"
                        ? "Complete"
                        : currentStage === "error"
                          ? "Error"
                          : currentStage.charAt(0).toUpperCase() + currentStage.slice(1)
                      : "Initializing…"}
                  </span>
                  {buildStatus.isStreaming && !isBuildComplete && !isBuildError && (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-primary">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
                      </span>
                      Live
                    </span>
                  )}
                </div>
                <div className="relative h-3 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-500 ease-out relative",
                      isBuildError
                        ? "bg-gradient-to-r from-destructive to-destructive/80"
                        : isBuildComplete
                          ? "bg-gradient-to-r from-emerald-500 to-emerald-400"
                          : "bg-gradient-to-r from-primary via-purple-500 to-emerald-500"
                    )}
                    style={{ width: `${buildStatus.status?.progress ?? 0}%` }}
                  >
                    {!isBuildComplete && !isBuildError && (
                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
                    )}
                  </div>
                </div>
              </div>

              <BuildStepIndicator currentStage={currentStage} />

              <div className="rounded-xl border bg-black/[0.03] dark:bg-white/[0.02] overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2.5 border-b bg-muted/40">
                  <div className="flex items-center gap-2">
                    <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Build log
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    {buildStatus.isStreaming && (
                      <span className="inline-flex items-center gap-1.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-400">
                        <span className="relative flex h-1.5 w-1.5">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75" />
                          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
                        </span>
                        Streaming
                      </span>
                    )}
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {buildEvents.length} lines
                    </span>
                  </div>
                </div>

                {buildEvents.length === 0 && !isBuildError && (
                  <div className="flex flex-col items-center justify-center gap-3 py-12 text-sm text-muted-foreground">
                    <div className="relative">
                      <div className="h-8 w-8 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
                    </div>
                    <p className="font-medium">Initializing build pipeline…</p>
                    <p className="text-xs">Waiting for the first event from the server</p>
                  </div>
                )}

                {buildEvents.length > 0 && (
                  <div className="divide-y divide-border/30 max-h-[400px] overflow-y-auto">
                    {buildEvents.map((event, idx) => {
                      const isToolEnhanced = event.event === "tool_enhanced";
                      const isToolFailed = event.event === "tool_failed";
                      const isComplete = event.event === "ai_complete" || event.event === "done";
                      const isError = event.stage === "error";

                      return (
                        <div
                          key={idx}
                          className={cn(
                            "flex items-start gap-3 px-4 py-3 text-sm transition-all duration-200",
                            isError && "bg-destructive/[0.03]",
                            isToolEnhanced && "bg-emerald-500/[0.02]",
                            isToolFailed && "bg-destructive/[0.02]",
                            idx === buildEvents.length - 1 && !isBuildComplete && "bg-primary/[0.02]"
                          )}
                        >
                          <span className="font-mono text-[10px] text-muted-foreground/50 w-6 text-right shrink-0 pt-1">
                            {String(idx + 1).padStart(2, "0")}
                          </span>

                          <div className="shrink-0 pt-0.5">
                            {isError ? (
                              <XCircle className="h-4 w-4 text-destructive" />
                            ) : isToolEnhanced ? (
                              <Check className="h-4 w-4 text-emerald-500" />
                            ) : isToolFailed ? (
                              <AlertCircle className="h-4 w-4 text-destructive" />
                            ) : isComplete ? (
                              <Sparkles className="h-4 w-4 text-amber-500" />
                            ) : (
                              <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
                            )}
                          </div>

                          <div className="flex-1 min-w-0 space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span
                                className={cn(
                                  "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border",
                                  event.stage === "parsing" &&
                                    "bg-blue-500/8 text-blue-600 dark:text-blue-400 border-blue-500/15",
                                  event.stage === "generating" &&
                                    "bg-purple-500/8 text-purple-600 dark:text-purple-400 border-purple-500/15",
                                  event.stage === "testing" &&
                                    "bg-amber-500/8 text-amber-600 dark:text-amber-400 border-amber-500/15",
                                  event.stage === "deploying" &&
                                    "bg-cyan-500/8 text-cyan-600 dark:text-cyan-400 border-cyan-500/15",
                                  event.stage === "complete" &&
                                    "bg-emerald-500/8 text-emerald-600 dark:text-emerald-400 border-emerald-500/15",
                                  event.stage === "error" &&
                                    "bg-destructive/8 text-destructive border-destructive/20",
                                )}
                              >
                                {event.stage}
                              </span>
                              {event.tool_name && (
                                <span className="inline-flex items-center gap-1 rounded-md bg-primary/5 px-2 py-0.5 text-[10px] font-medium text-primary border border-primary/10">
                                  <Wand2 className="h-3 w-3" />
                                  {event.tool_name}
                                </span>
                              )}
                              {event.progress != null && event.progress > 0 && (
                                <span className="text-[10px] font-mono text-muted-foreground tabular-nums">
                                  {event.progress}%
                                </span>
                              )}
                            </div>
                            <p className={cn(
                              "text-sm leading-relaxed",
                              isError ? "text-destructive" : "text-foreground/85"
                            )}>
                              {event.message}
                            </p>
                            <div className="flex items-center gap-3 pt-0.5">
                              {event.quality_score != null && (
                                <span className="inline-flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">
                                  <Sparkles className="h-3 w-3" />
                                  Quality {event.quality_score}
                                </span>
                              )}
                              {event.cost_cents != null && event.cost_cents > 0 && (
                                <span className="text-[10px] text-muted-foreground tabular-nums">
                                  ${(event.cost_cents / 100).toFixed(2)}
                                </span>
                              )}
                              {event.successful != null && (
                                <span className="text-[10px] text-muted-foreground">
                                  {event.successful} ok, {event.failed ?? 0} failed
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {buildEvents.length === 0 && isBuildError && (
                  <div className="flex flex-col items-center justify-center gap-2 py-12 text-sm text-destructive">
                    <XCircle className="h-8 w-8" />
                    <p className="font-medium">Build failed to start</p>
                    <p className="text-xs text-muted-foreground">
                      {buildStatus.error?.message}
                    </p>
                  </div>
                )}
              </div>

              {isBuildComplete && (
                <div className="relative overflow-hidden rounded-xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/[0.03] to-emerald-500/[0.01] p-5">
                  <div className="absolute top-0 right-0 p-3 opacity-10">
                    <Sparkles className="h-16 w-16 text-emerald-500" />
                  </div>
                  <div className="relative flex items-start gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/10 shrink-0">
                      <Sparkles className="h-5 w-5 text-emerald-500" />
                    </div>
                    <div className="space-y-1.5">
                      <p className="font-semibold text-emerald-600 dark:text-emerald-400">
                        Build complete
                      </p>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {(() => {
                          const last = buildEvents[buildEvents.length - 1];
                          if (last?.successful != null && last?.failed != null) {
                            return (
                              <>
                                <span className="font-medium text-foreground">{last.successful}</span> tool
                                {last.successful !== 1 ? "s" : ""} enhanced successfully
                                {last.failed > 0 && (
                                  <>, <span className="font-medium text-destructive">{last.failed}</span> failed</>
                                )}
                                . Your MCP server is ready.
                              </>
                            );
                          }
                          return "Your MCP server is deployed and ready to use.";
                        })()}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {isBuildError && !isBuildComplete && (
                <div className="relative overflow-hidden rounded-xl border border-destructive/20 bg-gradient-to-br from-destructive/[0.03] to-destructive/[0.01] p-5">
                  <div className="absolute top-0 right-0 p-3 opacity-10">
                    <AlertCircle className="h-16 w-16 text-destructive" />
                  </div>
                  <div className="relative flex items-start gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10 shrink-0">
                      <AlertCircle className="h-5 w-5 text-destructive" />
                    </div>
                    <div className="space-y-1.5">
                      <p className="font-semibold text-destructive">
                        Build failed
                      </p>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {currentStage === "error" && buildStatus.status
                          ? buildStatus.status.message
                          : buildStatus.error?.message ||
                            "An unknown error occurred during the build."}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-3">
            {isBuildError && (
              <Button onClick={handleRetryBuild} variant="outline" className="gap-2">
                <RotateCcw className="h-4 w-4" />
                Retry Build
              </Button>
            )}

            {isBuildComplete && (
              <Button
                onClick={() => router.push(`/dashboard/servers/${server.id}`)}
                className="gap-2 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white border-0"
              >
                <Sparkles className="h-4 w-4" />
                View Server
              </Button>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
