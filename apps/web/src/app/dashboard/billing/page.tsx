"use client";

import { BillingManager } from "@/components/billing/billing-manager";

export default function BillingPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Billing</h1>
        <p className="text-sm text-muted-foreground">
          Manage your subscription and view invoices
        </p>
      </div>

      <BillingManager />
    </div>
  );
}
