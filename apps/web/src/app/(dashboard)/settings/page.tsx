"use client";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { useCurrentUser } from "@/hooks/use-auth";

export default function SettingsPage() {
  const { data: user } = useCurrentUser();

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your account settings
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <p className="text-sm font-medium">Email</p>
              <p className="text-sm text-muted-foreground">
                {user?.email ?? "Loading..."}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium">Plan</p>
              <p className="text-sm text-muted-foreground capitalize">
                {user?.plan ?? "Loading..."}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium">Display Name</p>
              <p className="text-sm text-muted-foreground">
                {user?.display_name ?? "Not set"}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium">Member Since</p>
              <p className="text-sm text-muted-foreground">
                {user?.created_at
                  ? new Date(user.created_at).toLocaleDateString()
                  : "Loading..."}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
