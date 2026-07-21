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
