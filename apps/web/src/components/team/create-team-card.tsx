"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Users } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateTeam } from "@/hooks/use-team";
import { createTeamSchema, type CreateTeamFormData } from "@/lib/validators";

export function CreateTeamCard() {
  const createTeam = useCreateTeam();

  const form = useForm<CreateTeamFormData>({
    resolver: zodResolver(createTeamSchema),
    defaultValues: { name: "" },
  });

  const onSubmit = form.handleSubmit(async (data) => {
    try {
      await createTeam.mutateAsync(data);
      toast.success("Team created successfully!");
    } catch {
      toast.error("Failed to create team. Please try again.");
    }
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="h-5 w-5" />
          Create your team
        </CardTitle>
        <CardDescription>
          Teams let you collaborate with others on MCP servers. Create a team to
          get started.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="team-name">Team name</Label>
            <Input
              id="team-name"
              placeholder="e.g. Acme Engineering"
              {...form.register("name")}
              aria-invalid={!!form.formState.errors.name}
            />
            {form.formState.errors.name && (
              <p className="text-sm text-destructive">
                {form.formState.errors.name.message}
              </p>
            )}
          </div>
          <Button type="submit" disabled={createTeam.isPending}>
            {createTeam.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating...
              </>
            ) : (
              "Create team"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
