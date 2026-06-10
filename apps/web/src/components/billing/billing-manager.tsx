"use client";

import { useRef } from "react";
import { CurrentPlanBanner } from "./current-plan-banner";
import { PlanCards } from "./plan-cards";
import { InvoiceHistory } from "./invoice-history";

export function BillingManager() {
  const planCardsRef = useRef<HTMLDivElement>(null);

  function scrollToPlans() {
    planCardsRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <div className="space-y-8">
      <CurrentPlanBanner onUpgradeClick={scrollToPlans} />
      <PlanCards scrollToRef={planCardsRef} />
      <InvoiceHistory />
    </div>
  );
}
