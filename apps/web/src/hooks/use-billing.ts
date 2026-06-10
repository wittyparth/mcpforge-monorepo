"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  PlansResponse,
  SubscriptionResponse,
  InvoicesListResponse,
  CheckoutResponse,
  PortalResponse,
} from "@/types/api";

const PLANS_KEY = ["plans"] as const;
const SUBSCRIPTION_KEY = ["subscription"] as const;
const invoicesKey = (params?: { skip?: number; limit?: number }) =>
  ["invoices", params] as const;

export function usePlans() {
  return useQuery({
    queryKey: PLANS_KEY,
    queryFn: () => api.billing.listPlans() as Promise<PlansResponse>,
    staleTime: 1000 * 60 * 60,
  });
}

export function useCurrentSubscription() {
  return useQuery({
    queryKey: SUBSCRIPTION_KEY,
    queryFn: () =>
      api.billing.getSubscription() as Promise<SubscriptionResponse | null>,
  });
}

export function useInvoices(params?: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: invoicesKey(params),
    queryFn: () => api.billing.listInvoices(params) as Promise<InvoicesListResponse>,
  });
}

export function useCheckout() {
  return useMutation({
    mutationFn: (data: {
      plan: "pro" | "team";
      billing_period: "monthly" | "yearly";
      seats?: number;
    }) => api.billing.subscribe(data) as Promise<CheckoutResponse>,
    onSuccess: (response) => {
      // In litigated mode (no real Stripe), the URL is a mock.
      // If it starts with "https://checkout.stripe.com/mock", show success in-app instead.
      if (response.checkout_url.includes("/mock/")) {
        window.location.href = "/dashboard/billing?checkout=success";
      } else {
        window.location.href = response.checkout_url;
      }
    },
  });
}

export function useOpenPortal() {
  return useMutation({
    mutationFn: (data?: { return_url?: string }) =>
      api.billing.openPortal(data) as Promise<PortalResponse>,
    onSuccess: (response) => {
      window.location.href = response.portal_url;
    },
  });
}
