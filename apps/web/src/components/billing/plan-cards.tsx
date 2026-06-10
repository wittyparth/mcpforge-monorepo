"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { usePlans, useCurrentSubscription, useCheckout } from "@/hooks/use-billing";
import { formatPrice, formatPeriod } from "@/lib/format";
import { PlanFeatures } from "./plan-features";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

interface PlanCardsProps {
  scrollToRef?: React.RefObject<HTMLDivElement | null>;
}

export function PlanCards({ scrollToRef }: PlanCardsProps) {
  const [period, setPeriod] = useState<"monthly" | "yearly">("monthly");
  const [seats, setSeats] = useState(2);

  const { data: plansData, isLoading } = usePlans();
  const { data: subscription } = useCurrentSubscription();
  const checkout = useCheckout();

  if (isLoading) {
    return (
      <div ref={scrollToRef} className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-6 md:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-96 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  const plans = plansData?.plans ?? [
    {
      id: "free",
      name: "Free",
      price_cents: 0,
      currency: "usd",
      period: "monthly" as const,
      features: [
        "2 MCP servers",
        "500 tool calls / month",
        "3 AI credits / month",
        "Community support",
      ],
      popular: false,
      min_seats: null,
    },
    {
      id: "pro",
      name: "Pro",
      price_cents: 1200,
      currency: "usd",
      period: "monthly" as const,
      features: [
        "10 MCP servers",
        "10,000 tool calls / month",
        "Unlimited AI credits",
        "Priority support",
        "Custom domains",
      ],
      popular: true,
      min_seats: null,
    },
    {
      id: "team",
      name: "Team",
      price_cents: 2900,
      currency: "usd",
      period: "monthly" as const,
      features: [
        "Unlimited MCP servers",
        "100,000 tool calls / month",
        "Unlimited AI credits",
        "Team collaboration",
        "Role-based access",
        "Audit log",
        "Priority support",
      ],
      popular: false,
      min_seats: 2,
    },
  ];

  const currentPlan = subscription?.plan ?? "free";

  const filteredPlans = plans.filter(
    (p) => p.period === period || p.price_cents === 0,
  );

  const displayPlans = filteredPlans.length > 0 ? filteredPlans : plans;

  function handleSubscribe(planId: string) {
    if (planId === "free") return;

    checkout.mutate(
      {
        plan: planId as "pro" | "team",
        billing_period: period,
        seats: planId === "team" ? seats : undefined,
      },
      {
        onError: (error: Error) => {
          toast.error(error.message || "Failed to start checkout");
        },
      },
    );
  }

  return (
    <div ref={scrollToRef} className="space-y-6">
      <div className="space-y-4">
        <h2 className="text-lg font-medium">Plans</h2>
        <div className="flex items-center gap-4">
          <ToggleGroup
            type="single"
            value={period}
            onValueChange={(v) => {
              if (v === "monthly" || v === "yearly") setPeriod(v);
            }}
            className="rounded-lg border p-1"
          >
            <ToggleGroupItem value="monthly" className="text-xs">
              Monthly
            </ToggleGroupItem>
            <ToggleGroupItem value="yearly" className="text-xs">
              Yearly
              <Badge variant="secondary" className="ml-1 text-[10px]">
                Save 20%
              </Badge>
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {displayPlans.map((plan) => {
          const isCurrentPlan = currentPlan === plan.name.toLowerCase();
          const isTeamPlan = plan.name.toLowerCase() === "team";
          const price =
            period === "yearly" && plan.price_cents > 0
              ? Math.round(plan.price_cents * 0.8)
              : plan.price_cents;

          return (
            <Card
              key={plan.id}
              className={`relative flex flex-col ${
                isCurrentPlan
                  ? "border-primary ring-2 ring-primary/20"
                  : plan.popular
                    ? "border-primary/50"
                    : ""
              }`}
            >
              {plan.popular && !isCurrentPlan && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge className="px-3">Most Popular</Badge>
                </div>
              )}
              {isCurrentPlan && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge variant="secondary" className="px-3">
                    Current Plan
                  </Badge>
                </div>
              )}

              <CardHeader className="text-center">
                <CardTitle className="text-lg">{plan.name}</CardTitle>
                <div className="mt-2">
                  {plan.price_cents === 0 ? (
                    <span className="text-3xl font-bold">Free</span>
                  ) : (
                    <div className="flex items-baseline justify-center gap-1">
                      <span className="text-3xl font-bold">
                        {formatPrice(price, plan.currency)}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        {formatPeriod(period)}
                      </span>
                    </div>
                  )}
                  {period === "yearly" && plan.price_cents > 0 && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      ${((price * 12) / 100).toFixed(0)}/year
                    </p>
                  )}
                </div>
              </CardHeader>

              <CardContent className="flex flex-1 flex-col space-y-6">
                <PlanFeatures features={plan.features} />

                {isTeamPlan && !isCurrentPlan && plan.price_cents > 0 && (
                  <div className="space-y-2">
                    <Label htmlFor="seats" className="text-sm">
                      Team seats
                    </Label>
                    <Input
                      id="seats"
                      type="number"
                      min={plan.min_seats ?? 2}
                      max={100}
                      value={seats}
                      onChange={(e) => {
                        const val = parseInt(e.target.value, 10);
                        if (!isNaN(val)) setSeats(val);
                      }}
                      className="h-9"
                    />
                    <p className="text-xs text-muted-foreground">
                      Minimum {plan.min_seats ?? 2} seats
                    </p>
                  </div>
                )}

                <div className="mt-auto">
                  {isCurrentPlan ? (
                    <Button variant="outline" className="w-full" disabled>
                      Current Plan
                    </Button>
                  ) : plan.price_cents === 0 ? (
                    <Button
                      variant="outline"
                      className="w-full"
                      disabled={isCurrentPlan}
                    >
                      Downgrade to Free
                    </Button>
                  ) : (
                    <Button
                      className="w-full"
                      onClick={() => handleSubscribe(plan.id)}
                      disabled={
                        checkout.isPending ||
                        (isTeamPlan && seats < (plan.min_seats ?? 2))
                      }
                    >
                      {checkout.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Redirecting...
                        </>
                      ) : (
                        `Upgrade to ${plan.name}`
                      )}
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
