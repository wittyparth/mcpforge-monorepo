"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Copy, Loader2, Send } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RoleSelector } from "@/components/team/role-selector";
import { useInviteMember } from "@/hooks/use-team";
import { inviteMemberSchema, type InviteMemberFormData } from "@/lib/validators";
import type { TeamRole, TeamInvitationCreateResponse } from "@/types/api";

export function InviteForm() {
  const inviteMember = useInviteMember();
  const [invitation, setInvitation] = useState<TeamInvitationCreateResponse | null>(null);
  const [role, setRole] = useState<TeamRole>("viewer");

  const form = useForm<InviteMemberFormData>({
    resolver: zodResolver(inviteMemberSchema),
    defaultValues: { email: "", role: "viewer" },
  });

  const onSubmit = form.handleSubmit(async (data) => {
    try {
      const result = await inviteMember.mutateAsync({
        email: data.email,
        role,
      });
      setInvitation(result);
      form.reset();
      setRole("viewer");
      toast.success("Invitation sent!");
    } catch {
      toast.error("Failed to send invitation");
    }
  });

  const appUrl =
    process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
  const inviteLink = invitation
    ? `${appUrl}/dashboard/team/accept?token=${invitation.token}`
    : null;

  const handleCopyLink = async () => {
    if (!inviteLink) return;
    await navigator.clipboard.writeText(inviteLink);
    toast.success("Invite link copied to clipboard");
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Send className="h-5 w-5" />
            Invite team member
          </CardTitle>
          <CardDescription>
            Send an invitation to join your team. They&apos;ll receive an email
            with a link to accept.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="invite-email">Email address</Label>
              <Input
                id="invite-email"
                type="email"
                placeholder="colleague@example.com"
                {...form.register("email")}
                aria-invalid={!!form.formState.errors.email}
              />
              {form.formState.errors.email && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.email.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label>Role</Label>
              <RoleSelector value={role} onChange={setRole} />
              <p className="text-xs text-muted-foreground">
                Admins can manage members. Editors can edit servers. Viewers have
                read-only access.
              </p>
            </div>

            <Button type="submit" disabled={inviteMember.isPending}>
              {inviteMember.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Send className="mr-2 h-4 w-4" />
                  Send invitation
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {invitation && inviteLink && (
        <Card>
          <CardHeader>
            <CardTitle>Invitation sent</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              An invitation has been sent to{" "}
              <strong>{invitation.email}</strong> with the{" "}
              <strong>{invitation.role}</strong> role. You can also share this
              link directly:
            </p>
            <div className="flex items-center gap-2">
              <Input
                value={inviteLink}
                readOnly
                className="font-mono text-xs"
              />
              <Button variant="outline" size="icon" onClick={handleCopyLink}>
                <Copy className="h-4 w-4" />
                <span className="sr-only">Copy invite link</span>
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              This link expires on{" "}
              {new Date(invitation.expires_at).toLocaleDateString("en-US", {
                year: "numeric",
                month: "long",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
              .
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
