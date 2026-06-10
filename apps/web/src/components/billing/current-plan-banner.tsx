"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentSubscription, useOpenPortal } from "@/hooks/use-billing";
import { formatDate } from "@/lib/format";
import { AlertTriangle, CreditCard, ExternalLink } from "lucide-react";

interface CurrentPlanBannerProps {
  onUpgradeClick: () => void;
}

function statusBadge(status: string) {
  switch (status) {
    case "active":
      return (
        <Badge variant="default" className="bg-green-600 hover:bg-green-600/80">
          Active
        </Badge>
      );
    case "trialing":
      return (
        <Badge variant="default" className="bg-blue-600 hover:bg-blue-600/80">
          Trialing
        </Badge>
      );
    case "past_due":
      return <Badge variant="destructive">Past Due</Badge>;
    case "canceled":
      return <Badge variant="secondary">Canceled</Badge>;
    case "incomplete":
      return <Badge variant="outline">Incomplete</Badge>;
    case "unpaid":
      return <Badge variant="destructive">Unpaid</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

export function CurrentPlanBanner({ onUpgradeClick }: CurrentPlanBannerProps) {
  const { data: subscription, isLoading } = useCurrentSubscription();
  const openPortal = useOpenPortal();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-40" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-4 w-64" />
        </CardContent>
      </Card>
    );
  }

  if (!subscription) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <CreditCard className="h-4 w-4" />
            Current Plan
          </CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">Free Plan</p>
            <p className="text-sm text-muted-foreground">
              Upgrade to unlock more features
            </p>
          </div>
          <Button onClick={onUpgradeClick}>Upgrade</Button>
        </CardContent>
      </Card>
    );
  }

  const isCanceling = subscription.cancel_at_period_end;
  const isPastDue = subscription.status === "past_due";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <CreditCard className="h-4 w-4" />
          Current Plan
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium capitalize">
                {subscription.plan} Plan
              </p>
              {statusBadge(subscription.status)}
            </div>
            <p className="text-sm text-muted-foreground">
              {subscription.seats > 1
                ? `${subscription.seats} seats`
                : "1 seat"}
              {" · "}
              Renews{" "}
              {formatDate(subscription.current_period_end)}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                openPortal.mutate({
                  return_url: window.location.href,
                })
              }
              disabled={openPortal.isPending}
            >
              <ExternalLink className="mr-2 h-4 w-4" />
              Manage Subscription
            </Button>
            {subscription.plan !== "team" && (
              <Button size="sm" onClick={onUpgradeClick}>
                Upgrade
              </Button>
            )}
          </div>
        </div>

        {isCanceling && (
          <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Your subscription will end on{" "}
              {formatDate(subscription.current_period_end)}. You will lose
              access to paid features on this date.
            </span>
          </div>
        )}

        {isPastDue && (
          <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Payment failed — please update your payment method in the
              billing portal to avoid service interruption.
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
