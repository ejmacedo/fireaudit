import { apiClient } from "@/lib/api/client";

export type SubscriptionTier = "free" | "pro" | "premium";
export type SubscriptionStatus = "active" | "past_due" | "canceled";

export interface Subscription {
  tier: SubscriptionTier;
  status: SubscriptionStatus;
  current_period_end: string | null;
}

export interface CheckoutSessionResponse {
  url: string;
}

export interface BillingPortalSessionResponse {
  url: string;
}

export async function getSubscription(): Promise<Subscription> {
  const { data } = await apiClient.get<Subscription>("/v1/subscription");
  return data;
}

export async function createCheckoutSession(): Promise<CheckoutSessionResponse> {
  const { data } = await apiClient.post<CheckoutSessionResponse>(
    "/v1/subscription/checkout-session"
  );
  return data;
}

/**
 * Opens Stripe's hosted Customer Portal so a Pro customer can change their
 * card or cancel the subscription without emailing support. Only works once
 * the account has completed at least one checkout (has a Stripe customer).
 */
export async function createBillingPortalSession(): Promise<BillingPortalSessionResponse> {
  const { data } = await apiClient.post<BillingPortalSessionResponse>(
    "/v1/subscription/billing-portal-session"
  );
  return data;
}
