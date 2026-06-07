"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  Check,
  FileJson,
  Loader2,
  Play,
  RotateCcw,
  Server,
  Settings,
  Sparkles,
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
    setSelectedToolSet(new Set(spec.tools.filter((t) => t.selected).map((t) => t.name)));
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
      {/* Back / Cancel link */}
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

      {/* Wizard stepper */}
      <WizardStepper currentStep={step} onStepClick={handleStepClick} />

      {/* ════════════════ Step 1: Spec Input ════════════════ */}
      {step === 1 && (
        <section aria-label="Step 1: Import OpenAPI Spec">
          <SpecInput
            onSuccess={handleSpecSuccess}
            onError={handleSpecError}
          />
        </section>
      )}

      {/* ════════════════ Step 2: Tool Selection ════════════ */}
      {step === 2 && specResponse && (
        <section aria-label="Step 2: Select Tools">
          <ToolWorkspace
            tools={specResponse.tools}
            selected={selectedToolSet}
            onToggle={handleToolToggle}
            onSelectAll={handleSelectAll}
            onDeselectAll={handleDeselectAll}
            onConfirm={handleToolsConfirm}
            onConfirmDisabled={selectedToolSet.size === 0}
          />
        </section>
      )}

      {/* ════════════════ Step 3: Config + Credentials ══════ */}
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
              base_url: specResponse.tools[0]?.base_url_override ?? "",
            }}
          />

          {createServerError && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/50 p-3 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>{createServerError}</p>
            </div>
          )}

          {/* Post-creation: credentials + continue */}
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

      {/* ════════════════ Step 4: Build Progress ════════════ */}
      {step === 4 && server && (
        <section aria-label="Step 4: Build Progress" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Sparkles className="h-5 w-5 text-primary" />
                Building your MCP server
              </CardTitle>
              <CardDescription>
                {!isBuildComplete &&
                  !isBuildError &&
                  "Your server is being built. This usually takes a few seconds."}
                {isBuildComplete && "Your MCP server is ready to use!"}
                {isBuildError && "Something went wrong during the build."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Step indicator */}
              <BuildStepIndicator currentStage={currentStage} />

              {/* Event log */}
              <div className="rounded-lg border bg-muted/20">
                {buildEvents.length === 0 && !isBuildError && (
                  <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Starting build...
                  </div>
                )}

                {buildEvents.length > 0 && (
                  <div className="divide-y divide-border/50">
                    {buildEvents.map((event, idx) => (
                      <div
                        key={idx}
                        className={cn(
                          "flex items-center gap-3 px-4 py-2.5 text-sm transition-colors",
                          event.stage === "error" && "bg-destructive/5",
                        )}
                      >
                        <span className="font-mono text-[11px] text-muted-foreground/60 w-5 text-right shrink-0">
                          {idx + 1}
                        </span>
                        <span
                          className={cn(
                            "rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider border shrink-0",
                            event.stage === "parsing" &&
                              "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
                            event.stage === "generating" &&
                              "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
                            event.stage === "testing" &&
                              "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
                            event.stage === "deploying" &&
                              "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20",
                            event.stage === "complete" &&
                              "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
                            event.stage === "error" &&
                              "bg-destructive/10 text-destructive border-destructive/30",
                          )}
                        >
                          {event.stage}
                        </span>
                        <span className="flex-1 text-foreground/80">
                          {event.message}
                        </span>
                        <span className="font-mono text-xs tabular-nums text-muted-foreground shrink-0">
                          {event.progress}%
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {buildEvents.length === 0 && isBuildError && (
                  <div className="flex items-center justify-center gap-2 py-8 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4" />
                    {buildStatus.error?.message || "Build failed to start"}
                  </div>
                )}
              </div>

              {/* Completion success alert */}
              {isBuildComplete && (
                <div className="flex items-start gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
                  <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                  <div className="space-y-1">
                    <p className="font-semibold text-emerald-600 dark:text-emerald-400">
                      Build complete
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Your MCP server is deployed. Redirecting to the server
                      dashboard...
                    </p>
                  </div>
                </div>
              )}

              {/* Error alert */}
              {isBuildError && !isBuildComplete && (
                <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
                  <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
                  <div className="space-y-1">
                    <p className="font-semibold text-destructive">
                      Build failed
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {currentStage === "error" && buildStatus.status
                        ? buildStatus.status.message
                        : buildStatus.error?.message ||
                          "An unknown error occurred."}
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Actions */}
          <div className="flex justify-end gap-3">
            {isBuildError && (
              <Button onClick={handleRetryBuild} className="gap-2">
                <RotateCcw className="h-4 w-4" />
                Retry Build
              </Button>
            )}

            {isBuildComplete && (
              <Button
                onClick={() => router.push(`/dashboard/servers/${server.id}`)}
                className="gap-2"
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
