"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Copy } from "lucide-react";

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
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { useDuplicateServer } from "@/hooks/use-servers";
import { duplicateServerSchema } from "@/lib/validators";
import { slugify } from "@/lib/format";
import type { DuplicateServerFormData } from "@/lib/validators";

interface DuplicateServerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  serverId: string;
  currentName: string;
  prefillName?: string;
}

export function DuplicateServerDialog({
  open,
  onOpenChange,
  serverId,
  currentName,
  prefillName,
}: DuplicateServerDialogProps) {
  const duplicate = useDuplicateServer();

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<DuplicateServerFormData>({
    resolver: zodResolver(duplicateServerSchema),
    defaultValues: {
      new_name: prefillName ?? `${currentName} (copy)`,
      new_slug: null,
    },
  });

  const newName = watch("new_name");
  const userEditedSlug = watch("new_slug");

  useEffect(() => {
    if (!open) return;
    reset({
      new_name: prefillName ?? `${currentName} (copy)`,
      new_slug: null,
    });
  }, [open, currentName, prefillName, reset]);

  useEffect(() => {
    if (!open) return;
    const suggested = slugify(newName ?? "");
    if (!userEditedSlug || userEditedSlug === slugify(prefillName ?? `${currentName} (copy)`)) {
      setValue("new_slug", suggested || null, { shouldValidate: false });
    }
  }, [newName, open, setValue, userEditedSlug, prefillName, currentName]);

  const onSubmit = (data: DuplicateServerFormData) => {
    duplicate.mutate(
      { id: serverId, data: { new_name: data.new_name, new_slug: data.new_slug ?? null } },
      { onSuccess: () => onOpenChange(false) },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Copy className="h-4 w-4" />
            Duplicate server
          </DialogTitle>
          <DialogDescription>
            Create a copy of <strong>{currentName}</strong> with a new name and slug.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="dup-name">New name</Label>
            <Input
              id="dup-name"
              placeholder="My Server (copy)"
              {...register("new_name")}
            />
            {errors.new_name && (
              <p className="text-xs text-destructive">{errors.new_name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="dup-slug">Slug (optional)</Label>
            <Input
              id="dup-slug"
              placeholder="my-server-copy"
              {...register("new_slug")}
            />
            <p className="text-xs text-muted-foreground">
              Lowercase, numbers, and hyphens only. Auto-generated from name if left empty.
            </p>
            {errors.new_slug && (
              <p className="text-xs text-destructive">{errors.new_slug.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={duplicate.isPending}>
              {duplicate.isPending ? (
                <>
                  <LoadingSpinner size="sm" />
                  Duplicating...
                </>
              ) : (
                "Duplicate server"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
