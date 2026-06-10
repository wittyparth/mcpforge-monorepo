"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2 } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useCreateApiKey } from "@/hooks/use-api-keys";
import {
  createApiKeySchema,
  API_KEY_SCOPES,
  API_KEY_SCOPE_DESCRIPTIONS,
  EXPIRATION_OPTIONS,
  type CreateApiKeyFormData,
  type ApiKeyScopeOption,
} from "@/lib/validators";
import type { ApiKeyCreateResponse } from "@/types/api";

interface CreateKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onKeyCreated: (response: ApiKeyCreateResponse) => void;
}

export function CreateKeyDialog({
  open,
  onOpenChange,
  onKeyCreated,
}: CreateKeyDialogProps) {
  const createKey = useCreateApiKey();
  const [adminWarning, setAdminWarning] = useState(false);

  const form = useForm<CreateApiKeyFormData>({
    resolver: zodResolver(createApiKeySchema),
    defaultValues: {
      name: "",
      scopes: [],
      expires_in_days: null,
    },
  });

  const watchedScopes = form.watch("scopes");

  const handleScopeToggle = (scope: ApiKeyScopeOption) => {
    const current = form.getValues("scopes");
    const next = current.includes(scope)
      ? current.filter((s) => s !== scope)
      : [...current, scope];

    if (scope === "admin" && !current.includes("admin")) {
      setAdminWarning(true);
    }

    form.setValue("scopes", next, { shouldValidate: true });
  };

  const onSubmit = form.handleSubmit(async (data) => {
    try {
      const result = await createKey.mutateAsync({
        name: data.name,
        scopes: data.scopes,
        expires_in_days: data.expires_in_days,
      });
      form.reset();
      setAdminWarning(false);
      onOpenChange(false);
      onKeyCreated(result);
      toast.success("API key created");
    } catch {
      toast.error("Failed to create API key");
    }
  });

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset();
      setAdminWarning(false);
    }
    onOpenChange(nextOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create API Key</DialogTitle>
          <DialogDescription>
            Create a new key for programmatic access. You&apos;ll see the full
            key only once.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="key-name">Name</Label>
            <Input
              id="key-name"
              placeholder="e.g. CI/CD Pipeline"
              {...form.register("name")}
              aria-invalid={!!form.formState.errors.name}
            />
            {form.formState.errors.name && (
              <p className="text-sm text-destructive">
                {form.formState.errors.name.message}
              </p>
            )}
          </div>

          <div className="space-y-3">
            <Label>Scopes</Label>
            <div className="space-y-2">
              {API_KEY_SCOPES.map((scope) => (
                <label
                  key={scope}
                  className="flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors hover:bg-muted/50"
                >
                  <Checkbox
                    checked={watchedScopes.includes(scope)}
                    onCheckedChange={() => handleScopeToggle(scope)}
                    className="mt-0.5"
                  />
                  <div className="flex-1 space-y-0.5">
                    <span className="text-sm font-medium">{scope}</span>
                    <p className="text-xs text-muted-foreground">
                      {API_KEY_SCOPE_DESCRIPTIONS[scope]}
                    </p>
                  </div>
                </label>
              ))}
            </div>
            {form.formState.errors.scopes && (
              <p className="text-sm text-destructive">
                {form.formState.errors.scopes.message}
              </p>
            )}
            {adminWarning && watchedScopes.includes("admin") && (
              <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
                The <strong>admin</strong> scope grants full access to all
                resources, including all other scopes.
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label>Expiration</Label>
            <Controller
              control={form.control}
              name="expires_in_days"
              render={({ field }) => (
                <Select
                  value={String(field.value ?? "null")}
                  onValueChange={(val) =>
                    field.onChange(val === "null" ? null : Number(val))
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select expiration" />
                  </SelectTrigger>
                  <SelectContent>
                    {EXPIRATION_OPTIONS.map((opt) => (
                      <SelectItem
                        key={String(opt.value)}
                        value={String(opt.value)}
                      >
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createKey.isPending}>
              {createKey.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create Key"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
